"""Design 도구 MCP 등록."""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP

from ppt_generator.interfaces.protocols import (
    DesignServiceFactory,
    ReviewServiceFactory,
)
from ppt_generator.tools.design.handlers.deps import DesignDeps
from ppt_generator.tools.design.handlers.generation import handle_generate
from ppt_generator.tools.design.handlers.modification import handle_modify, handle_move
from ppt_generator.tools.design.handlers.review import handle_review
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService


def register_design_tools(
    mcp: FastMCP,
    project_service: ProjectService,
    design_service_factory: DesignServiceFactory,
    slides_service: SlidesService | None = None,
    review_service_factory: ReviewServiceFactory | None = None,
) -> None:
    deps = DesignDeps(
        project_service, design_service_factory, slides_service, review_service_factory
    )

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
        return await handle_generate(
            deps,
            ctx,
            project_id=project_id,
            outline_json=outline_json,
            total_slides=total_slides,
            color_theme=color_theme,
            slide_indices=slide_indices,
        )

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
        return handle_move(
            deps,
            project_id=project_id,
            from_index=from_index,
            to_index=to_index,
        )

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
        return handle_modify(
            deps,
            project_id=project_id,
            action=action,
            slide_index=slide_index,
            title=title,
            content_summary=content_summary,
            component_hint=component_hint,
            slide_type=slide_type,
            speaker_notes=speaker_notes,
            color_theme=color_theme,
        )

    @mcp.tool()
    def review_design_spec(
        project_id: str,
        slide_indices: str = "",
        auto_fix: bool = True,
        color_theme: str = "dark",
    ) -> str:
        """Reviews existing design spec slides using LLM without full regeneration.

        Checks each slide against 7 design rules (font size, overlap, alignment, etc.).
        When auto_fix is True and high-severity issues are found, regenerates only those slides
        with review feedback — much faster than regenerating all slides.

        Args:
            project_id: Target project ID (required)
            slide_indices: Slide indices to review (1-based, comma-separated). E.g., "1,3,5". Empty string = review all.
            auto_fix: If True, automatically regenerates slides with high-severity issues (default: True)
            color_theme: Color theme ("dark" or "light", default: "dark")

        Returns:
            JSON string containing project_id, reviewed_count, per-slide review results with issues

        **IMPORTANT — Required follow-up action:**
        If any slides were regenerated (auto_fix=True), you must call `export_html(project_id=<project_id>)`
        to export HTML and share the slides_html_path with the user.
        """
        return handle_review(
            deps,
            project_id=project_id,
            slide_indices=slide_indices,
            auto_fix=auto_fix,
            color_theme=color_theme,
        )
