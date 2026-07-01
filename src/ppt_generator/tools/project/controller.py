import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.tools.project.service import ProjectService


def register_project_tools(mcp: FastMCP, project_service: ProjectService) -> None:
    @mcp.tool()
    def list_projects() -> str:
        """Retrieves the list of existing projects.

        Checks the ~/.ppt-generator/ directory and returns the list of saved projects.
        Includes each project's ID, topic, slide count, completed steps, source, and creation time.
        Most recent projects are listed first.

        The "source" field indicates how the project was created:
        - "generated": Created via the prepare_outline / ingest_outline pipeline (has outline)
        - "imported": Created via import_pptx (no outline — edit the design spec directly)

        **When to use**: Always call this tool first before starting the PPT generation pipeline.
        - If no projects exist: Start a new project (call prepare_outline).
        - If projects exist: Guide the user to choose whether to continue an existing project
          or start a new one.
        - For imported projects: Skip outline step and work directly with design spec.

        Returns:
            Project list JSON string. Empty array [] if no projects exist.
        """
        projects = project_service.list_projects()
        return json.dumps(
            {"total": len(projects), "projects": projects},
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def load_project_status(project_id: str) -> str:
        """Loads project status and metadata.

        Checks the saved project's topic, slide count, and completion status of each step.
        The "source" field indicates how the project was created:
        - "generated": Created via the prepare_outline / ingest_outline pipeline (has outline)
        - "imported": Created via import_pptx (no outline available)

        **For imported projects:** Since there is no outline, skip outline
        modification steps. Use prepare_slide_edit / ingest_slide_edit or
        prepare_design_slide / ingest_design_slide directly to modify slides.

        Args:
            project_id: Project ID

        Returns:
            Project metadata JSON string including source field
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        metadata = project_service.load_metadata(project_dir)
        return json.dumps(
            {
                "topic": metadata.topic,
                "num_slides": metadata.num_slides,
                "steps_completed": metadata.steps_completed,
                "audience_type": metadata.audience_type,
                "presentation_minutes": metadata.presentation_minutes,
                "source": metadata.source,
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    def load_outline(project_id: str, include_content: bool = False) -> str:
        """Loads the saved outline JSON.

        Retrieves the previously generated slide outline from the project directory.
        The loaded result can be used directly as input for prepare_design_slide or export_html.

        Args:
            project_id: Project ID
            include_content: If True, returns full slide outline content alongside path.
                Defaults to False (path and slide_count only).

        Returns:
            JSON string containing outline_path, slide_count, and optionally slides array
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        outline_json_str = project_service.load_outline(project_dir)
        outline_dir = project_dir / "outline"
        outline_path = (
            str(outline_dir)
            if outline_dir.exists()
            else str(project_dir / "outline.jsonl")
        )
        outline_data = json.loads(outline_json_str)
        slides = outline_data.get("slides", [])
        result: dict = {
            "outline_path": outline_path,
            "slide_count": len(slides),
        }
        if include_content:
            result["slides"] = slides
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    def save_outline_slide(
        project_id: str,
        slide_index: int,
        title: str,
        content_summary: str,
        component_hint: str = "bullets",
        slide_type: str = "content",
        speaker_notes: str = "",
        layout_plan: str = "",
    ) -> str:
        """Saves (overwrites) a single slide outline to the project.

        Creates or overwrites the outline file for a specific slide index.
        Use this before calling prepare_slide_edit(action="update") to provide
        the updated slide content that the LLM will use for design spec generation.

        **For adding new slides**: Use prepare_slide_edit(action="add") directly —
        it accepts outline parameters (title, content_summary, etc.) and handles
        all file shifts automatically. No need to call this tool first.

        **For updating existing slides**:
        1. Call save_outline_slide to overwrite the outline at slide_index.
        2. Call prepare_slide_edit(action="update", slide_index=...) to regenerate the design.
        (Or pass title/content_summary directly to the slide_edit update.)

        Args:
            project_id: Target project ID (required)
            slide_index: Target slide position (1-based). E.g., 1 for the first slide.
            title: Slide title
            content_summary: Detailed slide content description for the LLM
            component_hint: Layout hint ("bullets", "step_cards", "comparison_table", "arch_diagram", etc.)
            slide_type: Slide type ("title", "content", "closing", "agenda")
            speaker_notes: Optional speaker notes
            layout_plan: Content layout plan (arrangement direction, elements, relationships)

        Returns:
            JSON string containing project_id, slide_index, outline_path
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        idx = slide_index - 1  # 1-based → 0-based
        slide_data = json.dumps(
            {
                "title": title,
                "content_summary": content_summary,
                "component_hint": component_hint,
                "slide_type": slide_type,
                "speaker_notes": speaker_notes,
                "layout_plan": layout_plan,
            },
            ensure_ascii=False,
        )
        project_service.save_outline_slide(project_dir, idx, slide_data)
        outline_dir = project_dir / "outline"
        return json.dumps(
            {
                "project_id": project_id,
                "slide_index": slide_index,
                "outline_path": str(outline_dir / f"slide_{slide_index:02d}.json"),
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    def load_design_spec(project_id: str) -> str:
        """Loads the saved design spec.

        Retrieves the previously generated design spec (PptxSlideSpec JSON) from the project directory.
        The project_id can be passed to export_html(project_id=...) or export_pptx(project_id=...).

        Args:
            project_id: Project ID

        Returns:
            JSON string containing design_spec_dir, slide_count, slide_files
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        # Verify existence (raises exception if not found)
        design_spec = project_service.load_design_spec(project_dir)
        spec_dir = project_dir / "design_spec"
        slide_files = sorted(str(f.name) for f in spec_dir.glob("slide_*.json"))
        return json.dumps(
            {
                "design_spec_dir": str(spec_dir),
                "slide_count": len(design_spec.slides),
                "slide_files": slide_files,
            },
            ensure_ascii=False,
        )
