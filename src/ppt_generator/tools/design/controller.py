import asyncio
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
            slide_indices: Slide indices to generate (0-based, comma-separated). E.g., "0,2,4". Empty string = generate all.

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
            indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
            for idx in indices:
                if idx < 0 or idx >= len(outline.slides):
                    raise ValueError(f"Invalid slide_index: {idx}")
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
    def modify_design_spec(
        project_id: str,
        action: str,
        slide_index: int = -1,
        color_theme: str = "dark",
    ) -> str:
        """Adds, updates, or deletes individual slides in the design spec.

        Performs slide-level CRUD on an existing project's design spec.
        For add/update, maintains consistent style based on the first slide's design.

        **Precondition (add/update):**
        Before calling this tool, you must first modify the outline/script JSONL file.
        - add: Pre-insert a new slide line at the insertion position
        - update: Pre-modify the line at the target slide_index
        This tool reads the outline at the specified slide_index from the file to generate the design spec.

        Args:
            project_id: Target project ID (required)
            action: Action to perform ("add" | "update" | "delete")
            slide_index: Insertion position for add (-1 = end), target index for update/delete
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

        slide_html_path: str | None = None
        token_usage: dict[str, int] = {}

        if action == "add":
            insert_idx = slide_index if 0 <= slide_index < slide_count else slide_count
            # Read slide at target index from outline/script JSONL
            outline_raw = project_service.load_script_or_outline_slide(project_dir, insert_idx)
            outline = parse_outline_json(outline_raw)
            slide_outline = outline.slides[0]
            complexity = estimate_slide_complexity(slide_outline)
            effort = complexity_to_thinking_effort(complexity)
            slide_type = slide_outline.slide_type or "content"
            svc = design_service_factory(effort, slide_type)
            new_spec = svc.generate_single_slide(
                slide_outline, design_summary, color_theme=color_theme,
            )
            token_usage = svc.last_token_usage
            project_service.insert_design_spec_slide(project_dir, insert_idx, new_spec)
            # Shift existing HTML files before saving new one
            project_service.shift_slide_htmls(project_dir, insert_idx)
            if slides_service is not None:
                html = slides_service.render_single_slide_html(insert_idx, new_spec)
                html_path = project_service.save_single_slide_html(
                    project_dir, insert_idx, html,
                )
                slide_html_path = str(html_path)

        elif action == "update":
            if slide_index < 0 or slide_index >= slide_count:
                raise ValueError(f"Invalid slide_index: {slide_index} (total {slide_count} slides)")
            # Read slide at target index from outline/script JSONL
            outline_raw = project_service.load_script_or_outline_slide(project_dir, slide_index)
            outline = parse_outline_json(outline_raw)
            slide_outline = outline.slides[0]
            complexity = estimate_slide_complexity(slide_outline)
            effort = complexity_to_thinking_effort(complexity)
            slide_type = slide_outline.slide_type or "content"
            svc = design_service_factory(effort, slide_type)
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
                raise ValueError(f"Invalid slide_index: {slide_index} (total {slide_count} slides)")
            project_service.delete_design_spec_slide(project_dir, slide_index)
            # Sync HTML slides
            project_service.delete_slide_html(project_dir, slide_index)
            # Sync outline/script JSONL
            project_service.delete_outline_slide(project_dir, slide_index)

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
