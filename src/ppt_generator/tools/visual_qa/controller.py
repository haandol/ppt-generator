"""Visual QA MCP tool 등록 (prepare/ingest).

스크린샷 캡처는 서버(Playwright), 비전 분석·수정 생성은 클라이언트가 담당한다.
iteration 루프(분석→수정→재캡처)는 클라이언트(스킬)가 오케스트레이션한다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.constants import VISUAL_QA_MAX_ITERATIONS
from ppt_generator.interfaces.index_validation import require_positive_slide_index
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService
from ppt_generator.tools.visual_qa.service import VisualQAService

logger = logging.getLogger(__name__)


def register_visual_qa_tools(
    mcp: FastMCP,
    project_service: ProjectService,
    visual_qa_service: VisualQAService,
    slides_service: SlidesService,
) -> None:
    def _parse_indices(project_dir: Path, slide_indices: str) -> list[int]:
        """1-based comma 문자열 → 0-based 인덱스. 빈 문자열이면 전체."""
        slide_count = project_service.get_design_spec_slide_count(project_dir)
        if slide_count == 0:
            raise ValueError("디자인 스펙이 없습니다. 먼저 슬라이드를 생성하세요.")
        if slide_indices:
            raw = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
            for idx in raw:
                if idx < 1 or idx > slide_count:
                    raise ValueError(
                        f"유효하지 않은 slide_index: {idx} (유효 범위: 1-{slide_count})"
                    )
            return [i - 1 for i in raw]
        return list(range(slide_count))

    def _screenshot_path(project_dir: Path, idx: int, iteration: int) -> Path:
        return project_dir / "screenshots" / f"slide_{idx + 1:02d}_v{iteration}.png"

    @mcp.tool()
    def capture_slides(
        project_id: str,
        slide_indices: str = "",
        iteration: int = 0,
    ) -> str:
        """Captures slide screenshots via Playwright (server-side). No LLM call.

        Phase 1 of visual QA. Renders the current slide HTML to PNG so the CLIENT can
        analyze them for visual defects. **Requires:** `playwright install chromium`.

        Args:
            project_id: Target project ID (required).
            slide_indices: 1-based comma-separated indices (e.g. "1,3,5"). Empty = all.
            iteration: Iteration counter (0-based) — screenshots are versioned per iteration.

        Returns:
            JSON with project_id, iteration, screenshots: [{slide_index, screenshot_path}].

        **Next:** for each captured slide, call `prepare_visual_qa_analysis`.
        """
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        indices = _parse_indices(project_dir, slide_indices)

        shots = visual_qa_service.capture_screenshots(project_dir, indices, iteration)
        return json.dumps(
            {
                "project_id": project_id,
                "iteration": iteration,
                "max_iterations": VISUAL_QA_MAX_ITERATIONS,
                "screenshots": [
                    {"slide_index": idx + 1, "screenshot_path": str(shots[idx])}
                    for idx in indices
                    if idx in shots
                ],
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    def prepare_visual_qa_analysis(
        project_id: str,
        slide_index: int,
        iteration: int = 0,
    ) -> str:
        """Prepares the vision analysis task for ONE captured slide. No LLM call.

        Returns the system prompt, user prompt, `response_schema`, and `images` (the
        screenshot path to read). **Read the screenshot, analyze it against the spec,
        generate the analysis JSON matching `response_schema`, then call
        `ingest_visual_qa_analysis`.** Analyze slides in parallel.

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            iteration: Iteration counter matching the capture (default 0).

        Returns:
            JSON with system_prompt, user_prompt, response_schema, images, project_id, slide_index.
        """
        require_positive_slide_index(slide_index)
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)
        if slide_index > slide_count:
            raise ValueError(
                f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
            )
        idx = slide_index - 1
        png_path = _screenshot_path(project_dir, idx, iteration)
        if not png_path.exists():
            raise ValueError(
                f"screenshot not found for slide {slide_index} (iteration {iteration}). "
                "Call capture_slides first."
            )
        spec = project_service.load_design_spec_slide(project_dir, idx)
        task = visual_qa_service.prepare_analysis(png_path, idx, spec)
        task["project_id"] = project_id
        task["slide_index"] = slide_index
        return json.dumps(task, ensure_ascii=False)

    @mcp.tool()
    def ingest_visual_qa_analysis(
        project_id: str,
        slide_index: int,
        analysis_json: str,
    ) -> str:
        """Ingests the client-generated analysis: validate, report issues. No fix applied.

        Call AFTER prepare_visual_qa_analysis. If has_issues, call
        `prepare_visual_qa_fix` with the returned issues to generate a fix.

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            analysis_json: The analysis JSON generated by the client.

        Returns:
            JSON with has_issues, issues (dicts to feed into the fix step), overall_quality.
        """
        require_positive_slide_index(slide_index)
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)
        if slide_index > slide_count:
            raise ValueError(
                f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
            )
        analysis = visual_qa_service.ingest_analysis(analysis_json)
        issues = [i.model_dump() for i in analysis.issues]
        return json.dumps(
            {
                "project_id": project_id,
                "slide_index": slide_index,
                "has_issues": analysis.has_issues,
                "overall_quality": analysis.overall_quality,
                "issues": issues,
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    def prepare_visual_qa_fix(
        project_id: str,
        slide_index: int,
        issues_json: str,
        iteration: int = 0,
    ) -> str:
        """Prepares the fix task for a slide with detected issues. No LLM call.

        Returns the fix prompt, `response_schema`, and `images` (the screenshot).
        **Generate the corrected full slide spec JSON, then call `ingest_visual_qa_fix`.**

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            issues_json: JSON array of issues from ingest_visual_qa_analysis.
            iteration: Iteration counter matching the capture (default 0).

        Returns:
            JSON with system_prompt, user_prompt, response_schema, images, project_id, slide_index.
        """
        require_positive_slide_index(slide_index)
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)
        if slide_index > slide_count:
            raise ValueError(
                f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
            )
        idx = slide_index - 1
        png_path = _screenshot_path(project_dir, idx, iteration)
        if not png_path.exists():
            raise ValueError(
                f"screenshot not found for slide {slide_index} (iteration {iteration})."
            )
        spec = project_service.load_design_spec_slide(project_dir, idx)
        try:
            issues = json.loads(issues_json) if issues_json else []
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid issues_json: {exc}") from exc
        task = visual_qa_service.prepare_fix(png_path, spec, issues)
        task["project_id"] = project_id
        task["slide_index"] = slide_index
        return json.dumps(task, ensure_ascii=False)

    @mcp.tool()
    def ingest_visual_qa_fix(
        project_id: str,
        slide_index: int,
        fix_json: str,
        issues_json: str = "",
    ) -> str:
        """Ingests the client-generated fix: validate, save, re-render HTML.

        Call AFTER prepare_visual_qa_fix. Restores images/slide_type the LLM can't
        produce. Re-run capture → analysis on this slide to verify (up to max_iterations).

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            fix_json: The corrected slide spec JSON generated by the client.
            issues_json: The same issue array passed to prepare_visual_qa_fix.

        Returns:
            JSON with status ("fixed" | "unfixed"), slide_html_path.
        """
        require_positive_slide_index(slide_index)
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)
        if slide_index > slide_count:
            raise ValueError(
                f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
            )
        idx = slide_index - 1
        current_spec = project_service.load_design_spec_slide(project_dir, idx)
        try:
            issues = json.loads(issues_json) if issues_json else []
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid issues_json: {exc}") from exc
        if not isinstance(issues, list) or any(
            not isinstance(issue, dict) for issue in issues
        ):
            raise ValueError("issues_json must be a JSON array of objects")

        fixed = visual_qa_service.ingest_fix(fix_json, current_spec, issues)
        if fixed is None:
            return json.dumps(
                {
                    "project_id": project_id,
                    "slide_index": slide_index,
                    "status": "unfixed",
                },
                ensure_ascii=False,
            )

        project_service.save_design_spec_slide(project_dir, idx, fixed)
        project_service.renumber_design_spec_image_srcs(project_dir)

        design_summary = project_service.load_design_summary(project_dir)
        color_theme = (design_summary or {}).get("color_theme", "dark")
        bg_image_policy = project_service.load_bg_image_policy(project_dir)

        slide_html_path: str | None = None
        html = SlidesService.render_single_slide_html(
            idx, fixed, color_theme=color_theme, bg_image_policy=bg_image_policy
        )
        hp = project_service.save_single_slide_html(project_dir, idx, html)
        slide_html_path = str(hp)

        return json.dumps(
            {
                "project_id": project_id,
                "slide_index": slide_index,
                "status": "fixed",
                "slide_html_path": slide_html_path,
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    def finalize_visual_qa(project_id: str) -> str:
        """Rebuilds the deck container HTML + full export after visual QA fixes. No LLM call.

        Call ONCE after all fix iterations are done.

        Args:
            project_id: Target project ID (required).

        Returns:
            JSON with project_id, slides_html_path.
        """
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)
        if slide_count == 0:
            raise ValueError("디자인 스펙이 없습니다.")

        project_service.renumber_design_spec_image_srcs(project_dir)
        container_html = SlidesService._build_container_html(slide_count)
        (project_dir / "slides.html").write_text(container_html, encoding="utf-8")

        design_summary = project_service.load_design_summary(project_dir)
        color_theme = (design_summary or {}).get("color_theme", "dark")
        bg_image_policy = project_service.load_bg_image_policy(project_dir)

        slides_html_path: str | None = None
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
                bg_image_policy=bg_image_policy,
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

        result: dict = {"project_id": project_id}
        if slides_html_path:
            result["slides_html_path"] = slides_html_path
        return json.dumps(result, ensure_ascii=False)
