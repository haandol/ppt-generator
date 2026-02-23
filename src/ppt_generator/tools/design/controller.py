import json
import logging
from typing import Callable

from mcp.server.fastmcp import Context, FastMCP

from ppt_generator.interfaces.constants import BEDROCK_DESIGN_MODEL_ID
from ppt_generator.interfaces.utils import (
    complexity_to_thinking_effort,
    estimate_cost,
    estimate_slide_complexity,
    format_token_usage,
    parse_outline_json,
)
from ppt_generator.tools.design.parallel_runner import run_parallel_generation
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


def register_design_tools(
    mcp: FastMCP,
    project_service: ProjectService,
    design_service_factory: Callable[[str], DesignService],
    slides_service: SlidesService | None = None,
) -> None:
    @mcp.tool()
    async def generate_slides_design_spec(
        project_id: str = "",
        outline_json: str = "",
        total_slides: int = 0,
        color_theme: str = "dark",
        slide_indices: str = "",
        ctx: Context | None = None,
    ) -> str:
        """슬라이드 디자인 스펙을 생성합니다 (전체 또는 선택적, 서버 내부 병렬 처리).

        전체 슬라이드를 일괄 생성하거나, slide_indices로 특정 슬라이드만 선택적으로 생성할 수 있습니다.
        **병렬 처리는 서버 내부에서 자동으로 수행**되므로, 이 도구를 여러 번 병렬 호출할 필요가 없습니다.
        환경변수 DESIGN_SPEC_PARALLEL(기본 8)로 동시 생성 수를 제어합니다.

        **처리 순서:**
        1. design_summary가 없으면 LLM으로 디자인 테마를 사전 생성합니다.
        2. 모든 슬라이드를 병렬로 생성합니다 (각 슬라이드의 HTML 미리보기도 자동 생성).
        3. 일부 슬라이드가 실패해도 나머지는 정상 저장됩니다.
           실패한 슬라이드는 이 도구에 해당 slide_indices만 지정하여 재시도할 수 있습니다.

        **개별 슬라이드 수정은 `modify_design_spec`의 update action을 사용하세요.**

        **사전 조건: 아웃라인 생성 후 사용자에게 아웃라인 수정 사항이 없는지 반드시 확인을 받은 뒤 호출하세요.**

        Args:
            project_id: 프로젝트 ID. 지정하면 저장된 script.json(없으면 outline.json)에서 자동 로드합니다.
            outline_json: 전체 아웃라인 JSON ({"slides": [...]}) - 모든 슬라이드 포함. project_id를 지정하면 생략 가능합니다.
            total_slides: 전체 슬라이드 수. 0이면 로드된 아웃라인에서 자동 계산됩니다.
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")
            slide_indices: 생성할 슬라이드 인덱스 (0-based, 콤마 구분). 예: "0,2,4". 빈 문자열이면 전체 생성.

        Returns:
            design_spec_dir, slide_count, total_slides, project_id, success_count, error_count, results를 포함하는 JSON 문자열
        """
        # --- 아웃라인 로드 ---
        if outline_json:
            outline = parse_outline_json(outline_json)
        elif project_id:
            _, proj_dir = project_service.resolve_project_dir(project_id)
            raw = project_service.load_script_or_outline(proj_dir)
            outline = parse_outline_json(raw)
        else:
            raise ValueError("outline_json 또는 project_id 중 하나를 제공해야 합니다.")

        if total_slides == 0:
            total_slides = len(outline.slides)

        # --- slide_indices 파싱 및 검증 ---
        if not slide_indices and len(outline.slides) != total_slides:
            raise ValueError(
                f"outline의 slides 수({len(outline.slides)})와 "
                f"total_slides({total_slides})가 일치하지 않습니다."
            )

        if slide_indices:
            indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
            for idx in indices:
                if idx < 0 or idx >= len(outline.slides):
                    raise ValueError(f"유효하지 않은 slide_index: {idx}")
        else:
            indices = list(range(total_slides))

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        target_count = len(indices)

        # --- Step 1: design_summary 사전 생성 ---
        existing_summary = project_service.load_design_summary(project_dir)
        if existing_summary is None:
            logger.info("design_summary 사전 생성 시작 (LLM 호출)")
            summary_svc = design_service_factory("medium")
            summary = summary_svc.generate_design_summary(outline, color_theme)
            project_service.save_design_summary(project_dir, summary)
            logger.info("design_summary 사전 생성 완료")
            if ctx is not None:
                await ctx.report_progress(0, target_count, "디자인 테마 생성 완료")

        # --- Step 2: 병렬 생성 ---
        design_summary = project_service.load_design_summary(project_dir)

        async def _report(progress: int, message: str) -> None:
            if ctx is not None:
                await ctx.report_progress(progress, target_count, message)

        # report_progress를 동기 콜백으로 래핑 (runner는 동기)
        progress_calls: list[tuple[int, str]] = []

        def sync_report(progress: int, message: str) -> None:
            progress_calls.append((progress, message))

        parallel_result = run_parallel_generation(
            outline=outline,
            indices=indices,
            total_slides=total_slides,
            color_theme=color_theme,
            design_summary=design_summary,
            design_service_factory=design_service_factory,
            project_service=project_service,
            project_dir=project_dir,
            slides_service=slides_service,
            report_progress=sync_report,
        )

        # 비동기 진행 보고 전달
        for progress, message in progress_calls:
            await _report(progress, message)

        project_service.update_step(project_dir, "design_spec")
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        # --- Step 3: slides.html 컨테이너 생성 ---
        slides_html_path: str | None = None
        if slides_service is not None and slide_count > 0:
            container_html = SlidesService._build_container_html(slide_count)
            path = project_dir / "slides.html"
            path.write_text(container_html, encoding="utf-8")
            slides_html_path = str(path)
            logger.info("slides.html 컨테이너 생성 완료: %s", path)

        # --- 토큰 사용량 & 예상 비용 ---
        aggregated_usage: dict[str, int] = {}
        pr = parallel_result
        if pr.total_input_tokens or pr.total_output_tokens:
            aggregated_usage = {
                "inputTokens": pr.total_input_tokens,
                "outputTokens": pr.total_output_tokens,
                "totalTokens": pr.total_input_tokens + pr.total_output_tokens,
            }
            if pr.total_cache_read_tokens:
                aggregated_usage["cacheReadInputTokens"] = pr.total_cache_read_tokens
            if pr.total_cache_write_tokens:
                aggregated_usage["cacheWriteInputTokens"] = pr.total_cache_write_tokens

        resp: dict = {
            "design_spec_dir": str(project_dir / "design_spec"),
            "slide_count": slide_count,
            "total_slides": total_slides,
            "project_id": project_id,
            "success_count": pr.success_count,
            "error_count": pr.error_count,
            "results": pr.results,
        }
        if slides_html_path:
            resp["slides_html_path"] = slides_html_path
        if aggregated_usage:
            resp["token_usage"] = format_token_usage(aggregated_usage)
            resp["estimated_cost"] = estimate_cost(aggregated_usage, BEDROCK_DESIGN_MODEL_ID)

        return json.dumps(resp, ensure_ascii=False)

    @mcp.tool()
    def modify_design_spec(
        project_id: str,
        action: str,
        slide_index: int = -1,
        outline_json: str = "",
        color_theme: str = "dark",
    ) -> str:
        """디자인 스펙의 개별 슬라이드를 추가, 수정, 삭제합니다.

        기존 프로젝트의 디자인 스펙에서 슬라이드 단위 CRUD를 수행합니다.
        add/update 시 첫 슬라이드의 디자인을 기반으로 일관된 스타일을 유지합니다.

        Args:
            project_id: 대상 프로젝트 ID (필수)
            action: 수행할 작업 ("add" | "update" | "delete")
            slide_index: add일 때 삽입 위치(-1이면 끝), update/delete일 때 대상 인덱스
            outline_json: add/update 시 슬라이드 아웃라인 JSON (title, content_summary, component_hint)
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")

        Returns:
            design_spec_path, project_id, slide_count를 포함하는 JSON 문자열
        """
        if action not in ("add", "update", "delete"):
            raise ValueError(f"action은 'add', 'update', 'delete' 중 하나여야 합니다: {action}")

        _, project_dir = project_service.resolve_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        design_summary: dict | None = None
        if action in ("add", "update"):
            design_summary = project_service.load_design_summary(project_dir)

        slide_html_path: str | None = None
        token_usage: dict[str, int] = {}

        if action == "add":
            if not outline_json:
                raise ValueError("add 시 outline_json이 필수입니다.")
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
            complexity = estimate_slide_complexity(slide_outline)
            effort = complexity_to_thinking_effort(complexity)
            svc = design_service_factory(effort)
            new_spec = svc.generate_single_slide(
                slide_outline, design_summary, color_theme=color_theme,
            )
            token_usage = svc.last_token_usage
            insert_idx = slide_index if 0 <= slide_index < slide_count else slide_count
            project_service.insert_design_spec_slide(project_dir, insert_idx, new_spec)
            if slides_service is not None:
                html = slides_service.render_single_slide_html(insert_idx, new_spec)
                html_path = project_service.save_single_slide_html(
                    project_dir, insert_idx, html,
                )
                slide_html_path = str(html_path)

        elif action == "update":
            if not outline_json:
                raise ValueError("update 시 outline_json이 필수입니다.")
            if slide_index < 0 or slide_index >= slide_count:
                raise ValueError(f"유효하지 않은 slide_index: {slide_index} (전체 {slide_count}장)")
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
            complexity = estimate_slide_complexity(slide_outline)
            effort = complexity_to_thinking_effort(complexity)
            svc = design_service_factory(effort)
            new_spec = svc.generate_single_slide(
                slide_outline, design_summary, color_theme=color_theme,
            )
            token_usage = svc.last_token_usage
            project_service.save_design_spec_slide(project_dir, slide_index, new_spec)
            if slides_service is not None:
                html = slides_service.render_single_slide_html(slide_index, new_spec)
                html_path = project_service.save_single_slide_html(
                    project_dir, slide_index, html,
                )
                slide_html_path = str(html_path)

        elif action == "delete":
            if slide_index < 0 or slide_index >= slide_count:
                raise ValueError(f"유효하지 않은 slide_index: {slide_index} (전체 {slide_count}장)")
            project_service.delete_design_spec_slide(project_dir, slide_index)

        project_service.update_step(project_dir, "design_spec_modified")
        new_count = project_service.get_design_spec_slide_count(project_dir)

        result: dict = {
            "design_spec_dir": str(project_dir / "design_spec"),
            "project_id": project_id,
            "slide_count": new_count,
        }
        if slide_html_path:
            result["slide_html_path"] = slide_html_path
        if token_usage:
            result["token_usage"] = format_token_usage(token_usage)
            result["estimated_cost"] = estimate_cost(token_usage, BEDROCK_DESIGN_MODEL_ID)

        return json.dumps(result, ensure_ascii=False)
