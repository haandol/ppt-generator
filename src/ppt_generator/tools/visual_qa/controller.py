"""Visual QA MCP tool 등록 (prepare/ingest).

스크린샷 캡처는 서버(Playwright), 비전 분석·수정 생성은 클라이언트가 담당한다.
iteration 루프(분석→수정→재캡처)는 클라이언트(스킬)가 오케스트레이션한다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.constants import VISUAL_QA_MAX_ITERATIONS
from ppt_generator.interfaces.index_validation import require_positive_slide_index
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_fingerprint
from ppt_generator.tools.design.edit_context import (
    ProjectSnapshot,
    decode_signed_context,
    encode_signed_context,
    project_edit_lock,
)
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService
from ppt_generator.tools.visual_qa.service import VisualQAService

logger = logging.getLogger(__name__)


def register_visual_qa_tools(
    mcp: FastMCP,
    project_service: ProjectService,
    visual_qa_service: VisualQAService,
    slides_service: SlidesService,
    export_service: ExportService | None = None,
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

    def _import_external_screenshot(
        source_path: str,
        target_path: Path,
    ) -> Path:
        """클라이언트 PNG를 검증해 프로젝트의 iteration 경로에 고정한다."""
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"external screenshot not found: {source}")
        with source.open("rb") as stream:
            png_header = stream.read(8)
        if source.suffix.lower() != ".png" or png_header != b"\x89PNG\r\n\x1a\n":
            raise ValueError("external screenshot must be a PNG file")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source != target_path.resolve():
            shutil.copyfile(source, target_path)
        return target_path

    def _spec_fingerprint(spec: PptxSlideSpec) -> str:
        """명세가 바뀐 뒤 이전 분석으로 수정하지 못하도록 내용을 식별한다."""
        return slide_spec_fingerprint(spec)

    def _analysis_snapshot(
        project_dir: Path, spec: PptxSlideSpec, slide_index: int, iteration: int
    ) -> dict:
        """분석에서 읽는 명세·의도·이미지를 하나의 검증 문맥으로 묶는다."""
        png_path = _screenshot_path(project_dir, slide_index - 1, iteration)
        return {
            "spec_fingerprint": _spec_fingerprint(spec),
            "design_directives": project_service.load_design_directives(
                project_dir, slide_index
            ),
            "iteration": iteration,
            "screenshot_fingerprint": (
                hashlib.sha256(png_path.read_bytes()).hexdigest()
                if png_path.is_file()
                else None
            ),
        }

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
        screenshot_path: str = "",
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
            screenshot_path: Optional client-captured PNG path. When supplied, it is
                validated and used instead of requiring Playwright capture.

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
        if screenshot_path:
            png_path = _import_external_screenshot(screenshot_path, png_path)
        if not png_path.is_file():
            raise ValueError(
                f"screenshot not found for slide {slide_index} (iteration {iteration}). "
                "Call capture_slides first."
            )
        spec = project_service.load_design_spec_slide(project_dir, idx)
        snapshot = _analysis_snapshot(project_dir, spec, slide_index, iteration)
        task = visual_qa_service.prepare_analysis(
            png_path,
            idx,
            spec,
            design_directives=snapshot["design_directives"],
        )
        task["prepared_context"] = encode_signed_context(
            {
                "kind": "visual_qa_analysis_prepared",
                "version": 1,
                "project_id": project_id,
                "slide_index": slide_index,
                **snapshot,
            },
            project_dir,
        )
        task["project_id"] = project_id
        task["slide_index"] = slide_index
        return json.dumps(task, ensure_ascii=False)

    @mcp.tool()
    def ingest_visual_qa_analysis(
        project_id: str,
        slide_index: int,
        analysis_json: str,
        prepared_context: str = "",
    ) -> str:
        """Ingests the client-generated analysis: validate, report issues. No fix applied.

        Call AFTER prepare_visual_qa_analysis and echo its prepared_context token.
        Missing or stale context is rejected; restart from prepare after upgrading
        an older client. If has_issues, pass analysis_context to prepare_visual_qa_fix.

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            analysis_json: The analysis JSON generated by the client.
            prepared_context: Opaque token from the same analysis prepare response.

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
        if not prepared_context:
            raise ValueError(
                "prepared_context is required; call prepare_visual_qa_analysis "
                "again and echo its prepared_context"
            )
        context = decode_signed_context(prepared_context, project_dir)
        if (
            context.get("kind") != "visual_qa_analysis_prepared"
            or context.get("version") != 1
            or context.get("project_id") != project_id
            or context.get("slide_index") != slide_index
            or not isinstance(context.get("iteration"), int)
        ):
            raise ValueError("prepared_context does not match analysis request")
        spec = project_service.load_design_spec_slide(project_dir, slide_index - 1)
        snapshot = _analysis_snapshot(
            project_dir, spec, slide_index, context["iteration"]
        )
        if any(context.get(key) != value for key, value in snapshot.items()):
            raise ValueError(
                "Stale prepared_context: analysis inputs changed after prepare"
            )
        analysis = visual_qa_service.ingest_analysis(analysis_json)
        visual_qa_service.validate_issue_targets(analysis, spec)
        issues = [i.model_dump() for i in analysis.issues]
        analysis_context = encode_signed_context(
            {
                "kind": "visual_qa_analysis",
                "version": 1,
                "project_id": project_id,
                "slide_index": slide_index,
                **snapshot,
                "issues": issues,
            },
            project_dir,
        )
        return json.dumps(
            {
                "project_id": project_id,
                "slide_index": slide_index,
                "has_issues": analysis.has_issues,
                "overall_quality": analysis.overall_quality,
                "issues": issues,
                "analysis_context": analysis_context,
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    def prepare_visual_qa_fix(
        project_id: str,
        slide_index: int,
        analysis_context: str,
        iteration: int = 0,
    ) -> str:
        """Prepares the fix task for a slide with detected issues. No LLM call.

        Returns the fix prompt, `response_schema`, and `images` (the screenshot).
        **Generate the minimal visual patch JSON, then call `ingest_visual_qa_fix`.**

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            analysis_context: Opaque context returned by ingest_visual_qa_analysis.
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
        if not png_path.is_file():
            raise ValueError(
                f"screenshot not found for slide {slide_index} (iteration {iteration})."
            )
        spec = project_service.load_design_spec_slide(project_dir, idx)
        context = decode_signed_context(analysis_context, project_dir)
        if (
            context.get("kind") != "visual_qa_analysis"
            or context.get("version") != 1
            or context.get("project_id") != project_id
            or context.get("slide_index") != slide_index
            or context.get("iteration") != iteration
        ):
            raise ValueError("analysis_context does not match fix request")
        if context.get("spec_fingerprint") != _spec_fingerprint(spec):
            raise ValueError("Stale analysis_context: slide changed after analysis")
        directives = project_service.load_design_directives(project_dir, slide_index)
        if context.get("design_directives", "") != directives:
            raise ValueError(
                "Stale analysis_context: design intent changed after analysis"
            )
        if (
            context.get("screenshot_fingerprint")
            != hashlib.sha256(png_path.read_bytes()).hexdigest()
        ):
            raise ValueError(
                "Stale analysis_context: screenshot changed after analysis"
            )
        issues = context.get("issues")
        if not isinstance(issues, list):
            raise ValueError("Invalid analysis_context issues")
        task = visual_qa_service.prepare_fix(
            png_path, spec, issues, design_directives=directives
        )
        task["project_id"] = project_id
        task["slide_index"] = slide_index
        task["fix_context"] = encode_signed_context(
            {
                "kind": "visual_qa_fix",
                "version": 1,
                "project_id": project_id,
                "slide_index": slide_index,
                "iteration": iteration,
                "design_directives": directives,
                "spec_fingerprint": _spec_fingerprint(spec),
                "screenshot_fingerprint": context["screenshot_fingerprint"],
                "issues": issues,
            },
            project_dir,
        )
        return json.dumps(task, ensure_ascii=False)

    @mcp.tool()
    def ingest_visual_qa_fix(
        project_id: str,
        slide_index: int,
        fix_json: str,
        fix_context: str,
    ) -> str:
        """Ingests the client-generated fix: validate, save, re-render HTML.

        Call AFTER prepare_visual_qa_fix. Restores images/slide_type the LLM can't
        produce. Re-run capture → analysis on this slide to verify (up to max_iterations).

        Args:
            project_id: Target project ID (required).
            slide_index: 1-based slide position.
            fix_json: The visual patch JSON generated by the client.
            fix_context: Opaque context returned by prepare_visual_qa_fix.

        Returns:
            JSON with status ("fixed" | "unfixed" | "unresolved"), slide_html_path.
        """
        require_positive_slide_index(slide_index)
        _, project_dir = project_service.resolve_existing_project_dir(project_id)
        with project_edit_lock(project_dir):
            slide_count = project_service.get_design_spec_slide_count(project_dir)
            if slide_index > slide_count:
                raise ValueError(
                    f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
                )
            idx = slide_index - 1
            current_spec = project_service.load_design_spec_slide(project_dir, idx)
            context = decode_signed_context(fix_context, project_dir)
            if (
                context.get("kind") != "visual_qa_fix"
                or context.get("version") != 1
                or context.get("project_id") != project_id
                or context.get("slide_index") != slide_index
            ):
                raise ValueError("fix_context does not match ingest request")
            if context.get("spec_fingerprint") != _spec_fingerprint(current_spec):
                raise ValueError("Stale fix_context: slide changed after fix prepare")
            if context.get(
                "design_directives", ""
            ) != project_service.load_design_directives(project_dir, slide_index):
                raise ValueError(
                    "Stale fix_context: design intent changed after fix prepare"
                )
            snapshot = _analysis_snapshot(
                project_dir, current_spec, slide_index, context.get("iteration", 0)
            )
            if (
                context.get("screenshot_fingerprint")
                != snapshot["screenshot_fingerprint"]
            ):
                raise ValueError(
                    "Stale fix_context: screenshot changed after fix prepare"
                )
            issues = context.get("issues")
            if not isinstance(issues, list):
                raise ValueError("Invalid fix_context issues")

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
            if fixed == current_spec:
                return json.dumps(
                    {
                        "project_id": project_id,
                        "slide_index": slide_index,
                        "status": "unresolved",
                        "remaining_issues": issues,
                    },
                    ensure_ascii=False,
                )

            design_summary = project_service.load_design_summary(project_dir)
            color_theme = (design_summary or {}).get("color_theme", "dark")
            bg_image_policy = project_service.load_bg_image_policy(project_dir)
            html = SlidesService.render_single_slide_html(
                idx, fixed, color_theme=color_theme, bg_image_policy=bg_image_policy
            )
            with ProjectSnapshot(project_dir) as snapshot:
                project_service.save_design_spec_slide(project_dir, idx, fixed)
                hp = project_service.save_single_slide_html(project_dir, idx, html)
                project_service.update_step(project_dir, "design_spec_modified")
                snapshot.commit()

            return json.dumps(
                {
                    "project_id": project_id,
                    "slide_index": slide_index,
                    "status": "fixed",
                    "slide_html_path": str(hp),
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
            JSON with project_id, slides_html_path, and pptx_path when export succeeds.
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
        pptx_path: str | None = None
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
            if export_service is not None:
                pptx_response = export_service.export_from_design_spec(
                    design_spec,
                    output_dir=project_dir,
                    skip_autofit=is_imported,
                    color_theme=color_theme,
                    bg_image_policy=bg_image_policy,
                )
                pptx_path = pptx_response.pptx_path
                project_service.update_step(project_dir, "pptx")
                logger.info("Visual QA 후 PPTX export 완료: %s", pptx_path)
        except Exception:
            logger.exception("Visual QA 후 최종 export 실패")

        result: dict = {"project_id": project_id}
        if slides_html_path:
            result["slides_html_path"] = slides_html_path
        if pptx_path:
            result["pptx_path"] = pptx_path
        return json.dumps(result, ensure_ascii=False)
