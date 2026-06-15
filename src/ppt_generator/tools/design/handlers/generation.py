"""generate_slides_design_spec 핸들러."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from ppt_generator.interfaces.constants import BEDROCK_DESIGN_MODEL_ID
from ppt_generator.interfaces.spec_utils import lint_design_spec
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

    # --- Step 1: Pre-generate DESIGN.md draft (design intent source of truth) ---
    # DESIGN.md 가 없으면 outline 기반으로 초안을 자동 생성한다 (기존 머신
    # 디자인 요약을 LLM 으로 만들던 자리를 대체). 사용자가 이후 DESIGN.md 를
    # 편집해 톤·페이지별 요청을 반영할 수 있다.
    if not project_service.design_doc_md_exists(project_dir):
        if ctx is not None:
            await ctx.report_progress(0, target_count, "디자인 테마 생성 중...")
        logger.info("Starting DESIGN.md draft generation (LLM call)")
        summary_svc = deps.design_service_factory("content")
        summary = summary_svc.generate_design_summary(outline, color_theme)
        summary["color_theme"] = color_theme
        from ppt_generator.tools.design.design_doc_md import render_design_doc_md

        project_service.save_design_doc_md(project_dir, render_design_doc_md(summary))
        logger.info("DESIGN.md draft generation completed")
        if ctx is not None:
            await ctx.report_progress(0, target_count, "디자인 테마 생성 완료")

    # --- Step 2: Parallel generation ---
    design_doc = project_service.load_design_doc_md(project_dir)
    design_summary = project_service.load_design_summary(project_dir)
    bg_image_policy = project_service.load_bg_image_policy(project_dir)
    sync_report = _make_progress_reporter(ctx, target_count)

    parallel_result = await _run_with_heartbeat(
        asyncio.to_thread(
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
            design_doc=design_doc,
            bg_image_policy=bg_image_policy,
        ),
        ctx=ctx,
        target_count=target_count,
        message="디자인 스펙 생성 중...",
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

    # --- Step 4: Lint design spec ---
    # 결정 13b — 단계적 검증: layout(거시)부터 차례로 검사하다가 어느
    # layer 에 error 가 나면 다음 layer 검사를 스킵해 거시 위반을 미시 노이즈로
    # 가리지 않는다.
    lint_result_dict: dict | None = None
    cross_layer_errors: list[dict] = []
    if slide_count > 0:
        design_spec = project_service.load_design_spec(project_dir)
        lint_result = lint_design_spec(design_spec.slides, stop_on_layer_error=True)
        if lint_result.has_violations:
            lint_result_dict = lint_result.to_dict()
        # 결정 13e — cross-layer error 는 응답에 명시적으로 노출.
        for slide_result in lint_result.slides:
            for v in slide_result.violations:
                if v.severity == "error" and v.layer == "cross":
                    cross_layer_errors.append(
                        {
                            "slide_index": slide_result.slide_index,
                            "rule": v.rule,
                            "message": v.message,
                        }
                    )

    resp: dict = {
        "design_spec_dir": str(project_dir / "design_spec"),
        "design_doc_path": str(project_dir / "DESIGN.md"),
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
        "design_doc_suggestion": (
            "디자인 의도(전역 톤, 페이지별 특별 요청)는 DESIGN.md 에서 관리합니다. "
            "DESIGN.md 를 편집한 뒤 generate_slides_design_spec 또는 "
            "modify_design_spec 을 다시 호출하면 변경된 의도가 반영됩니다."
        ),
    }
    if lint_result_dict:
        resp["lint"] = lint_result_dict
        resp["lint_suggestion"] = (
            f"디자인 lint에서 {lint_result_dict['total_violations']}건의 위반이 발견되었습니다. "
            "위반 내용을 확인하고, 수정이 필요하면 해당 슬라이드를 "
            "modify_design_spec(action='update')로 수정하세요."
        )
    if cross_layer_errors:
        resp["cross_layer_errors"] = cross_layer_errors
        resp["cross_layer_errors_suggestion"] = (
            f"{len(cross_layer_errors)}건의 cross-layer error 가 발견되었습니다 "
            "(component_id 매칭 실패, GridPlan↔design_doc cell_id 불일치 등). "
            "modify_component 또는 modify_design_spec(action='update') 호출 전에 "
            "확인이 필요합니다 — 현재 상태에서 modify_component 가 "
            "ValueError 로 실패할 수 있습니다."
        )
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
        raw = deps.project_service.load_outline(proj_dir)
        return parse_outline_json(raw)
    logger.error(
        "generate_slides_design_spec validation failed: "
        "Either outline_json or project_id must be provided."
    )
    raise ValueError("Either outline_json or project_id must be provided.")


def _parse_slide_indices(outline, total_slides: int, slide_indices: str) -> list[int]:
    """slide_indices 문자열을 파싱하여 0-based 인덱스 리스트로 반환한다."""
    if not slide_indices and len(outline.slides) != total_slides:
        msg = (
            f"Number of slides in outline ({len(outline.slides)}) does not match "
            f"total_slides ({total_slides})."
        )
        logger.error("generate_slides_design_spec validation failed: %s", msg)
        raise ValueError(msg)
    if slide_indices:
        try:
            raw_indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
        except ValueError as exc:
            logger.error(
                "slide_indices parse failed: input=%r, error=%s",
                slide_indices,
                exc,
            )
            raise ValueError(
                f"Invalid slide_indices format: {slide_indices!r} "
                "(expected comma-separated integers)"
            ) from exc
        for idx in raw_indices:
            if idx < 1 or idx > len(outline.slides):
                msg = (
                    f"Invalid slide_index: {idx} (valid range: 1-{len(outline.slides)})"
                )
                logger.error("slide_indices validation failed: %s", msg)
                raise ValueError(msg)
        return [i - 1 for i in raw_indices]
    return list(range(total_slides))


async def _run_with_heartbeat(
    coro,
    ctx,
    target_count: int,
    message: str,
    interval: float = 15.0,
):
    """coro 실행 중 interval 간격으로 MCP progress heartbeat를 보낸다."""
    if ctx is None:
        return await coro

    done = asyncio.Event()

    async def _heartbeat() -> None:
        while not done.is_set():
            try:
                await ctx.report_progress(0, target_count, message)
            except Exception:
                logger.debug("heartbeat progress report 실패", exc_info=True)
            try:
                await asyncio.wait_for(done.wait(), timeout=interval)
            except TimeoutError:
                pass

    heartbeat_task = asyncio.create_task(_heartbeat())
    try:
        return await coro
    finally:
        done.set()
        await heartbeat_task


def _make_progress_reporter(ctx, target_count: int):
    """MCP Context의 async report_progress를 sync 콜백으로 래핑한다."""
    if ctx is None:
        return lambda progress, message: None
    loop = asyncio.get_running_loop()

    def sync_report(progress: int, message: str) -> None:
        try:
            loop.call_soon_threadsafe(
                loop.create_task,
                ctx.report_progress(progress, target_count, message),
            )
        except RuntimeError:
            logger.debug("event loop closed, skipping progress report")

    return sync_report
