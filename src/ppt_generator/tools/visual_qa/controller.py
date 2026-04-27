"""Visual QA MCP tool 등록."""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP

from ppt_generator.interfaces.constants import (
    BEDROCK_DESIGN_MODEL_ID,
    VISUAL_QA_MAX_ITERATIONS,
)
from ppt_generator.interfaces.protocols import VisualQAServiceFactory
from ppt_generator.interfaces.utils import estimate_cost, format_token_usage
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


def register_visual_qa_tools(
    mcp: FastMCP,
    project_service: ProjectService,
    visual_qa_service_factory: VisualQAServiceFactory,
    slides_service: SlidesService,
) -> None:
    @mcp.tool()
    async def visual_qa(
        project_id: str,
        slide_indices: str = "",
        max_iterations: int = VISUAL_QA_MAX_ITERATIONS,
        ctx: Context | None = None,
    ) -> str:
        """Checks visual quality of rendered slides and auto-fixes issues (opt-in).

        Uses Playwright screenshots + Claude Vision to detect visual defects
        (word breaks, text truncation, overlap, overflow, contrast, misalignment)
        and automatically fixes the design spec.

        **Requires one of:**
        - Playwright: `uv sync --group visual-qa && playwright install chromium`
        - Chrome DevTools MCP: If Playwright is not available, you can use Chrome DevTools MCP's
          `take_screenshot` tool to capture screenshots manually, then review them with the user.

        Args:
            project_id: Target project ID (required)
            slide_indices: Slide indices to check (1-based, comma-separated). E.g., "1,3,5". Empty = all slides.
            max_iterations: Maximum fix iterations per slide (default: 2)

        Returns:
            JSON with analysis results, fix status per slide, and token usage.
        """
        from ppt_generator.tools.visual_qa.service import VisualQAService

        _, project_dir = project_service.resolve_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        if slide_count == 0:
            raise ValueError(
                "디자인 스펙이 없습니다. 먼저 generate_slides_design_spec을 실행하세요."
            )

        # Parse indices (1-based → 0-based)
        if slide_indices:
            raw_indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
            for idx in raw_indices:
                if idx < 1 or idx > slide_count:
                    raise ValueError(
                        f"유효하지 않은 slide_index: {idx} (유효 범위: 1-{slide_count})"
                    )
            indices = [i - 1 for i in raw_indices]
        else:
            indices = list(range(slide_count))

        # Create service (lazy — Playwright check happens at capture time)
        service: VisualQAService = visual_qa_service_factory()

        # design_summary에서 color_theme 로드
        design_summary = project_service.load_design_summary(project_dir)
        color_theme = (design_summary or {}).get("color_theme", "dark")

        if ctx is not None:
            await ctx.report_progress(0, max_iterations, "Visual QA 시작")

        async def _report_progress(completed: int, total: int, message: str) -> None:
            if ctx is not None:
                await ctx.report_progress(completed, total, message)

        result = await service.run_qa(
            project_dir=project_dir,
            indices=indices,
            max_iterations=max_iterations,
            load_spec=project_service.load_design_spec_slide,
            save_spec=project_service.save_design_spec_slide,
            render_html=lambda idx, spec: SlidesService.render_single_slide_html(
                idx, spec, color_theme=color_theme
            ),
            save_html=project_service.save_single_slide_html,
            report_progress=_report_progress,
        )

        # 이미지 src prefix 교정
        if result.slides_fixed > 0:
            project_service.renumber_design_spec_image_srcs(project_dir)

        # Rebuild container HTML if any slides were fixed
        if result.slides_fixed > 0:
            new_count = project_service.get_design_spec_slide_count(project_dir)
            container_html = SlidesService._build_container_html(new_count)
            (project_dir / "slides.html").write_text(container_html, encoding="utf-8")

        # Auto export HTML after visual QA
        slides_html_path: str | None = None
        if result.slides_fixed > 0 or slide_count > 0:
            try:
                design_spec = project_service.load_design_spec(project_dir)
                design_spec = project_service.sync_image_paths(project_dir, design_spec)
                slide_image_srcs: list[list[str]] = []
                for idx, slide in enumerate(design_spec.slides):
                    if slide.images:
                        srcs = project_service.get_slide_image_srcs(
                            project_dir, idx, len(slide.images)
                        )
                        slide_image_srcs.append(srcs)
                    else:
                        slide_image_srcs.append([])
                metadata = project_service.load_metadata(project_dir)
                is_imported = "import" in metadata.steps_completed
                response = slides_service.generate_from_design_spec(
                    design_spec,
                    slide_image_srcs=slide_image_srcs,
                    skip_autofit=is_imported,
                    color_theme=color_theme,
                )
                project_service.save_slides_html(
                    project_dir,
                    response.session_id,
                    response.slide_htmls,
                    response.container_html,
                )
                slides_html_path = str(project_dir / "slides.html")
                logger.info("Visual QA 후 HTML export 완료: %s", slides_html_path)
            except Exception:
                logger.exception("Visual QA 후 HTML export 실패")

        if ctx is not None:
            await ctx.report_progress(max_iterations, max_iterations, "Visual QA 완료")

        # Build full response and save to file
        full_resp: dict = {
            "project_id": project_id,
            "slides_analyzed": result.slides_analyzed,
            "slides_with_issues": result.slides_with_issues,
            "slides_fixed": result.slides_fixed,
            "iterations_used": result.iterations_used,
            "screenshots_dir": result.screenshots_dir,
            "per_slide": [
                {
                    "slide_index": r.slide_index + 1,  # 0-based → 1-based
                    "status": r.status,
                    **({"issues_found": r.issues_found} if r.issues_found else {}),
                    **({"iterations": r.iterations} if r.iterations else {}),
                }
                for r in result.per_slide
            ],
        }

        aggregated_usage: dict[str, int] = {}
        if result.total_input_tokens or result.total_output_tokens:
            aggregated_usage = {
                "inputTokens": result.total_input_tokens,
                "outputTokens": result.total_output_tokens,
                "totalTokens": result.total_input_tokens + result.total_output_tokens,
                "cacheReadInputTokens": result.total_cache_read_tokens,
                "cacheWriteInputTokens": result.total_cache_write_tokens,
            }
        if aggregated_usage:
            full_resp["token_usage"] = format_token_usage(aggregated_usage)
            full_resp["estimated_cost"] = estimate_cost(
                aggregated_usage, BEDROCK_DESIGN_MODEL_ID
            )

        # Save detailed result to file
        result_path = project_dir / "visual_qa_result.json"
        result_path.write_text(
            json.dumps(full_resp, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Return compact summary (minimal response to avoid client issues)
        summary: dict = {
            "project_id": project_id,
            "slides_analyzed": result.slides_analyzed,
            "slides_with_issues": result.slides_with_issues,
            "slides_fixed": result.slides_fixed,
            "iterations_used": result.iterations_used,
            "result_detail_path": str(result_path),
        }
        if result.error:
            summary["error"] = result.error
        if slides_html_path:
            summary["slides_html_path"] = slides_html_path
        if aggregated_usage:
            summary["token_usage"] = full_resp["token_usage"]
            summary["estimated_cost"] = full_resp["estimated_cost"]

        return json.dumps(summary, ensure_ascii=False)
