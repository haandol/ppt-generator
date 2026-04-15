"""generate_slides_design_spec 핸들러."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from ppt_generator.interfaces.constants import BEDROCK_DESIGN_MODEL_ID
from ppt_generator.interfaces.utils import (
    estimate_cost,
    format_token_usage,
    parse_outline_json,
)
from ppt_generator.tools.design.parallel_runner import run_parallel_generation
from ppt_generator.tools.slides.service import SlidesService

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context

    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


async def handle_generate(
    deps: DesignDeps,
    ctx: Context | None,
    *,
    project_id: str,
    outline_json: str,
    total_slides: int,
    color_theme: str,
    slide_indices: str,
) -> str:
    """병렬 디자인 스펙 생성을 오케스트레이션한다."""
    project_service = deps.project_service
    slides_service = deps.slides_service

    # --- Load outline ---
    outline = _load_outline(deps, project_id=project_id, outline_json=outline_json)

    if total_slides == 0:
        total_slides = len(outline.slides)

    # --- Parse and validate slide_indices ---
    indices = _parse_slide_indices(outline, total_slides, slide_indices)
    project_id, project_dir = project_service.resolve_project_dir(project_id)
    target_count = len(indices)

    # --- Step 1: Pre-generate design_summary ---
    existing_summary = project_service.load_design_summary(project_dir)
    if existing_summary is None:
        if ctx is not None:
            await ctx.report_progress(0, target_count, "디자인 테마 생성 중...")
        logger.info("Starting design_summary pre-generation (LLM call)")
        summary_svc = deps.design_service_factory("medium", "content")
        summary = summary_svc.generate_design_summary(outline, color_theme)
        summary["color_theme"] = color_theme
        project_service.save_design_summary(project_dir, summary)
        logger.info("design_summary pre-generation completed")
        if ctx is not None:
            await ctx.report_progress(0, target_count, "디자인 테마 생성 완료")

    # --- Step 2: Parallel generation ---
    design_summary = project_service.load_design_summary(project_dir)
    sync_report = _make_progress_reporter(ctx, target_count)

    parallel_result = await asyncio.to_thread(
        run_parallel_generation,
        outline=outline,
        indices=indices,
        total_slides=total_slides,
        color_theme=color_theme,
        design_summary=design_summary,
        design_service_factory=deps.design_service_factory,
        project_service=project_service,
        project_dir=project_dir,
        slides_service=slides_service,
        report_progress=sync_report,
        review_service_factory=deps.review_service_factory,
    )

    # LLM이 src를 'images/' prefix 없이 생성할 수 있으므로 교정
    project_service.renumber_design_spec_image_srcs(project_dir)

    project_service.update_step(project_dir, "design_spec")
    slide_count = project_service.get_design_spec_slide_count(project_dir)

    # --- Step 3: Generate slides.html container ---
    slides_html_path: str | None = None
    if slides_service is not None and slide_count > 0:
        container_html = SlidesService._build_container_html(slide_count)
        path = project_dir / "slides.html"
        path.write_text(container_html, encoding="utf-8")
        slides_html_path = str(path)
        logger.info("slides.html container generated: %s", path)
        if ctx is not None:
            await ctx.report_progress(target_count, target_count, "HTML 내보내기 완료")

    # --- Token usage & estimated cost ---
    pr = parallel_result
    aggregated_usage: dict[str, int] = {}
    if pr.total_input_tokens or pr.total_output_tokens:
        aggregated_usage = {
            "inputTokens": pr.total_input_tokens,
            "outputTokens": pr.total_output_tokens,
            "totalTokens": pr.total_input_tokens + pr.total_output_tokens,
            "cacheReadInputTokens": pr.total_cache_read_tokens,
            "cacheWriteInputTokens": pr.total_cache_write_tokens,
        }

    # --- Collect overflow content from all slides ---
    all_overflow: list[dict] = []
    for slide_result in pr.results:
        if "overflow" in slide_result:
            all_overflow.extend(slide_result["overflow"])
    if all_overflow:
        overflow_path = project_dir / "overflow.json"
        overflow_path.write_text(
            json.dumps(all_overflow, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "overflow content saved: %d item(s) → %s",
            len(all_overflow),
            overflow_path,
        )

    resp: dict = {
        "design_spec_dir": str(project_dir / "design_spec"),
        "slide_count": slide_count,
        "total_slides": total_slides,
        "project_id": project_id,
        "success_count": pr.success_count,
        "error_count": pr.error_count,
        "results": pr.results,
        "visual_qa_suggestion": (
            "Visual QA를 실행하면 시각적 결함(줄바꿈, 겹침, 잘림 등)을 자동 감지하고 수정합니다. "
            f"실행하려면 visual_qa(project_id='{project_id}') 를 호출하세요."
        ),
    }
    if all_overflow:
        resp["overflow_suggestion"] = (
            f"{len(all_overflow)}개의 컨텐츠가 슬라이드 공간 부족으로 포함되지 못했습니다. "
            "아래 overflow 항목을 확인하고, modify_design_spec(action='add')로 "
            "새 슬라이드를 추가할 수 있습니다."
        )
        resp["overflow"] = all_overflow
    if slides_html_path:
        resp["slides_html_path"] = slides_html_path
    if aggregated_usage:
        resp["token_usage"] = format_token_usage(aggregated_usage)
        resp["estimated_cost"] = estimate_cost(
            aggregated_usage, BEDROCK_DESIGN_MODEL_ID
        )

    return json.dumps(resp, ensure_ascii=False)


# --- helpers ---


def _load_outline(deps: DesignDeps, *, project_id: str, outline_json: str):
    """아웃라인을 JSON 문자열 또는 프로젝트 디렉토리에서 로드한다."""
    if outline_json:
        return parse_outline_json(outline_json)
    if project_id:
        _, proj_dir = deps.project_service.resolve_project_dir(project_id)
        raw = deps.project_service.load_script_or_outline(proj_dir)
        return parse_outline_json(raw)
    raise ValueError("Either outline_json or project_id must be provided.")


def _parse_slide_indices(outline, total_slides: int, slide_indices: str) -> list[int]:
    """slide_indices 문자열을 파싱하여 0-based 인덱스 리스트로 반환한다."""
    if not slide_indices and len(outline.slides) != total_slides:
        raise ValueError(
            f"Number of slides in outline ({len(outline.slides)}) does not match "
            f"total_slides ({total_slides})."
        )
    if slide_indices:
        raw_indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
        for idx in raw_indices:
            if idx < 1 or idx > len(outline.slides):
                raise ValueError(
                    f"Invalid slide_index: {idx} (valid range: 1-{len(outline.slides)})"
                )
        return [i - 1 for i in raw_indices]
    return list(range(total_slides))


def _make_progress_reporter(ctx, target_count: int):
    """MCP Context의 async report_progress를 sync 콜백으로 래핑한다."""
    if ctx is None:
        return lambda progress, message: None
    loop = asyncio.get_running_loop()

    def sync_report(progress: int, message: str) -> None:
        loop.call_soon_threadsafe(
            loop.create_task,
            ctx.report_progress(progress, target_count, message),
        )

    return sync_report
