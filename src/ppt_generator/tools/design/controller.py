import asyncio
import json
import logging
from dataclasses import replace
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
    design_service_factory: Callable[[str, str], DesignService],
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
        """Generates slide design specs (all or selective, with server-side parallel processing).

        Can generate all slides at once, or selectively generate specific slides via slide_indices.
        **Parallel processing is handled automatically inside the server**, so there is no need to call this tool multiple times in parallel.
        The DESIGN_SPEC_PARALLEL env var (default 8) controls the concurrency level.

        **Processing order:**
        1. If design_summary doesn't exist, pre-generates the design theme via LLM.
        2. Generates all slides in parallel (HTML preview for each slide is also auto-generated).
        3. If some slides fail, the rest are still saved normally.
           Failed slides can be retried by specifying only those slide_indices in this tool.

        **For individual slide modifications, use the update action in `modify_design_spec`.**

        **Precondition: After outline generation, you must confirm with the user that there are no outline modifications before calling.**

        Args:
            project_id: Project ID. If specified, automatically loads from saved script.json (or outline.json if unavailable).
            outline_json: Full outline JSON ({"slides": [...]}) - including all slides. Can be omitted if project_id is specified.
            total_slides: Total number of slides. 0 = auto-calculated from loaded outline.
            color_theme: Color theme ("dark" or "light", default: "dark")
            slide_indices: Slide indices to generate (1-based, comma-separated). E.g., "1,3,5". Empty string = generate all.

        Returns:
            JSON string containing design_spec_dir, slide_count, total_slides, project_id, success_count, error_count, results

        **IMPORTANT — Required follow-up action:**
        After this tool call succeeds, you must call `export_html(project_id=<project_id>)`
        to export HTML and share the slides_html_path with the user.
        """
        # --- Load outline ---
        if outline_json:
            outline = parse_outline_json(outline_json)
        elif project_id:
            _, proj_dir = project_service.resolve_project_dir(project_id)
            raw = project_service.load_script_or_outline(proj_dir)
            outline = parse_outline_json(raw)
        else:
            raise ValueError("Either outline_json or project_id must be provided.")

        if total_slides == 0:
            total_slides = len(outline.slides)

        # --- Parse and validate slide_indices ---
        if not slide_indices and len(outline.slides) != total_slides:
            raise ValueError(
                f"Number of slides in outline ({len(outline.slides)}) does not match "
                f"total_slides ({total_slides})."
            )

        if slide_indices:
            raw_indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
            for idx in raw_indices:
                if idx < 1 or idx > len(outline.slides):
                    raise ValueError(f"Invalid slide_index: {idx} (valid range: 1-{len(outline.slides)})")
            indices = [i - 1 for i in raw_indices]  # 1-based → 0-based
        else:
            indices = list(range(total_slides))

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        target_count = len(indices)

        # --- Step 1: Pre-generate design_summary ---
        existing_summary = project_service.load_design_summary(project_dir)
        if existing_summary is None:
            logger.info("Starting design_summary pre-generation (LLM call)")
            summary_svc = design_service_factory("medium", "content")
            summary = summary_svc.generate_design_summary(outline, color_theme)
            summary["color_theme"] = color_theme
            project_service.save_design_summary(project_dir, summary)
            logger.info("design_summary pre-generation completed")
            if ctx is not None:
                await ctx.report_progress(0, target_count, "Design theme generation completed")

        # --- Step 2: Parallel generation ---
        design_summary = project_service.load_design_summary(project_dir)

        # Wrap report_progress as sync callback (runner runs in sync thread)
        # Use call_soon_threadsafe to schedule on event loop for real-time progress
        loop = asyncio.get_running_loop()

        def sync_report(progress: int, message: str) -> None:
            if ctx is not None:
                loop.call_soon_threadsafe(
                    loop.create_task,
                    ctx.report_progress(progress, target_count, message),
                )

        parallel_result = await asyncio.to_thread(
            run_parallel_generation,
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

        # --- Token usage & estimated cost ---
        aggregated_usage: dict[str, int] = {}
        pr = parallel_result
        if pr.total_input_tokens or pr.total_output_tokens:
            aggregated_usage = {
                "inputTokens": pr.total_input_tokens,
                "outputTokens": pr.total_output_tokens,
                "totalTokens": pr.total_input_tokens + pr.total_output_tokens,
                "cacheReadInputTokens": pr.total_cache_read_tokens,
                "cacheWriteInputTokens": pr.total_cache_write_tokens,
            }

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
        if slides_html_path:
            resp["slides_html_path"] = slides_html_path
        if aggregated_usage:
            resp["token_usage"] = format_token_usage(aggregated_usage)
            resp["estimated_cost"] = estimate_cost(aggregated_usage, BEDROCK_DESIGN_MODEL_ID)

        return json.dumps(resp, ensure_ascii=False)

    @mcp.tool()
    def move_slide(
        project_id: str,
        from_index: int,
        to_index: int,
    ) -> str:
        """Moves a slide from one position to another. No LLM call — pure file reordering.

        Reorders all related files (outline/script, design_spec, slide HTML) atomically.
        After this call, you must call `export_html(project_id=<project_id>)` to refresh HTML.

        Args:
            project_id: Target project ID (required)
            from_index: Current slide position (1-based). E.g., 16 for the 16th slide.
            to_index: Desired slide position (1-based). E.g., 11 for the 11th position.

        Returns:
            JSON string containing project_id, slide_count, from_index, to_index
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        if from_index < 1 or from_index > slide_count:
            raise ValueError(f"Invalid from_index: {from_index} (valid range: 1-{slide_count})")
        if to_index < 1 or to_index > slide_count:
            raise ValueError(f"Invalid to_index: {to_index} (valid range: 1-{slide_count})")
        if from_index == to_index:
            return json.dumps({
                "project_id": project_id,
                "slide_count": slide_count,
                "from_index": from_index,
                "to_index": to_index,
                "message": "No move needed (same position)",
            }, ensure_ascii=False)

        from_idx = from_index - 1  # 1-based → 0-based
        to_idx = to_index - 1

        project_service.sync_outline_to_design_spec_count(project_dir)
        project_service.move_outline_slide(project_dir, from_idx, to_idx)
        project_service.move_design_spec_slide(project_dir, from_idx, to_idx)
        project_service.move_slide_html(project_dir, from_idx, to_idx)
        project_service.update_step(project_dir, "design_spec_modified")

        return json.dumps({
            "project_id": project_id,
            "slide_count": slide_count,
            "from_index": from_index,
            "to_index": to_index,
        }, ensure_ascii=False)

    @mcp.tool()
    def modify_design_spec(
        project_id: str,
        action: str,
        slide_index: int = -1,
        title: str = "",
        content_summary: str = "",
        component_hint: str = "bullets",
        slide_type: str = "content",
        speaker_notes: str = "",
        color_theme: str = "dark",
    ) -> str:
        """Adds, updates, or deletes individual slides in the design spec.

        Performs slide-level CRUD on an existing project's design spec.
        For add/update, maintains consistent style based on the first slide's design.

        **add: All file shifts are handled automatically.**
        Pass the new slide's outline (title, content_summary, etc.) directly.
        This tool shifts all files (outline/script/design_spec/HTML) at slide_index+1 onward by +1,
        saves the new outline, generates the design spec via LLM, and saves everything.
        No need to call save_outline_slide beforehand.

        **update: Pass the updated outline directly, or call save_outline_slide beforehand.**
        If title/content_summary are provided, the outline is updated automatically.
        Otherwise, reads the existing outline at slide_index.

        **delete: No precondition needed.**

        Args:
            project_id: Target project ID (required)
            action: Action to perform ("add" | "update" | "delete")
            slide_index: Slide position (1-based). Insertion position for add (-1 = end), target for update/delete.
            title: Slide title (required for add; required for update on imported projects, optional otherwise)
            content_summary: Slide content description for LLM (required for add; required for update on imported projects, optional otherwise)
            component_hint: Layout hint (default: "bullets")
            slide_type: Slide type - "title", "content", "closing", "agenda" (default: "content")
            speaker_notes: Optional speaker notes
            color_theme: Color theme ("dark" or "light", default: "dark")

        Returns:
            JSON string containing design_spec_path, project_id, slide_count

        **IMPORTANT — Required follow-up action:**
        After this tool call succeeds (when action is "add" or "update"),
        you must call `export_html(project_id=<project_id>)`
        to export HTML and share the slides_html_path with the user.
        """
        if action not in ("add", "update", "delete"):
            raise ValueError(f"action must be one of 'add', 'update', 'delete': {action}")

        _, project_dir = project_service.resolve_project_dir(project_id)
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        design_summary: dict | None = None
        if action in ("add", "update"):
            design_summary = project_service.load_design_summary(project_dir)
            # design_summary에 저장된 color_theme이 있으면 사용
            if design_summary and design_summary.get("color_theme"):
                color_theme = design_summary["color_theme"]

        slide_html_path: str | None = None
        token_usage: dict[str, int] = {}

        if action == "add":
            if not title or not content_summary:
                raise ValueError("title and content_summary are required for add action")
            # 1-based → 0-based; -1 means append
            insert_idx = (slide_index - 1) if 1 <= slide_index <= slide_count + 1 else slide_count
            # Step 0: Ensure outline count matches design_spec before insert
            project_service.sync_outline_to_design_spec_count(project_dir)
            # Step 1: Shift all files (outline/script, design_spec, HTML) at insert_idx onward by +1
            outline_json = json.dumps({
                "title": title, "content_summary": content_summary,
                "component_hint": component_hint, "slide_type": slide_type,
                "speaker_notes": speaker_notes,
            }, ensure_ascii=False)
            project_service.insert_outline_slide(project_dir, insert_idx, outline_json)
            project_service.shift_slide_htmls(project_dir, insert_idx)
            # Step 2: Use the outline we just built (avoids index mismatch on sparse outline)
            outline = parse_outline_json(outline_json)
            slide_outline = outline.slides[0]
            complexity = estimate_slide_complexity(slide_outline)
            effort = complexity_to_thinking_effort(complexity)
            svc = design_service_factory(effort, slide_outline.slide_type or "content")
            new_spec = svc.generate_single_slide(
                slide_outline, design_summary, color_theme=color_theme,
            )
            token_usage = svc.last_token_usage
            # Step 3: Insert design spec (shifts existing design_spec files)
            project_service.insert_design_spec_slide(project_dir, insert_idx, new_spec)
            # Step 4: Render and save HTML
            if slides_service is not None:
                html = slides_service.render_single_slide_html(insert_idx, new_spec, color_theme=color_theme)
                html_path = project_service.save_single_slide_html(
                    project_dir, insert_idx, html,
                )
                slide_html_path = str(html_path)

        elif action == "update":
            if slide_index < 1 or slide_index > slide_count:
                raise ValueError(f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})")
            idx = slide_index - 1  # 1-based → 0-based
            # Imported projects have no outline — title & content_summary are required
            metadata = project_service.load_metadata(project_dir)
            if metadata.source == "imported" and (not title or not content_summary):
                raise ValueError(
                    "title and content_summary are required for update action "
                    "on imported projects (no outline available)"
                )
            # Ensure outline count matches design_spec before update
            project_service.sync_outline_to_design_spec_count(project_dir)
            # If outline content is provided, update it first
            if title and content_summary:
                outline_json = json.dumps({
                    "title": title, "content_summary": content_summary,
                    "component_hint": component_hint, "slide_type": slide_type,
                    "speaker_notes": speaker_notes,
                }, ensure_ascii=False)
                project_service.save_outline_slide(project_dir, idx, outline_json)
            existing_spec = project_service.load_design_spec_slide(project_dir, idx)
            outline_raw = project_service.load_script_or_outline_slide(project_dir, idx)
            outline = parse_outline_json(outline_raw)
            slide_outline = outline.slides[0]
            complexity = estimate_slide_complexity(slide_outline)
            effort = complexity_to_thinking_effort(complexity)
            svc = design_service_factory(effort, slide_outline.slide_type or "content")
            new_spec = svc.generate_single_slide(
                slide_outline, design_summary, color_theme=color_theme,
            )
            token_usage = svc.last_token_usage
            if existing_spec.images:
                new_spec = replace(new_spec, images=existing_spec.images)
            project_service.save_design_spec_slide(project_dir, idx, new_spec)
            if slides_service is not None:
                html = slides_service.render_single_slide_html(idx, new_spec, color_theme=color_theme)
                html_path = project_service.save_single_slide_html(
                    project_dir, idx, html,
                )
                slide_html_path = str(html_path)

        elif action == "delete":
            if slide_index < 1 or slide_index > slide_count:
                raise ValueError(f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})")
            idx = slide_index - 1  # 1-based → 0-based
            project_service.sync_outline_to_design_spec_count(project_dir)
            project_service.delete_design_spec_slide(project_dir, idx)
            project_service.delete_slide_html(project_dir, idx)
            project_service.delete_outline_slide(project_dir, idx)

        project_service.update_step(project_dir, "design_spec_modified")
        project_service.sync_num_slides(project_dir)
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
