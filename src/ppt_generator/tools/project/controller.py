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
        - "generated": Created via generate_outline pipeline (has outline and script)
        - "imported": Created via import_pptx (no outline or script — modify design spec directly)

        **When to use**: Always call this tool first before starting the PPT generation pipeline.
        - If no projects exist: Start a new project (call generate_outline).
        - If projects exist: Guide the user to choose whether to continue an existing project
          or start a new one.
        - For imported projects: Skip outline/script steps and work directly with design spec.

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
        - "generated": Created via generate_outline pipeline (has outline and script)
        - "imported": Created via import_pptx (no outline or script available)

        **For imported projects:** Since there is no outline or script, skip outline/script
        modification steps. Use modify_design_spec or generate_slides_design_spec directly
        to modify slides.

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
    def load_outline(project_id: str) -> str:
        """Loads the saved outline JSON.

        Retrieves the previously generated slide outline from the project directory.
        The loaded result can be used directly as input for generate_script or export_html.

        Args:
            project_id: Project ID

        Returns:
            JSON string containing outline_path
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        # Verify file exists (raises exception if not found)
        project_service.load_outline(project_dir)
        return json.dumps(
            {"outline_path": str(project_dir / "outline.jsonl")},
            ensure_ascii=False,
        )

    @mcp.tool()
    def load_script(project_id: str) -> str:
        """Loads the saved script JSON.

        Retrieves the previously generated script (outline with speaker_notes) from the project directory.
        The loaded result can be used directly as input for export_html.

        Args:
            project_id: Project ID

        Returns:
            JSON string containing script_path
        """
        _, project_dir = project_service.resolve_project_dir(project_id)
        # Verify file exists (raises exception if not found)
        project_service.load_script(project_dir)
        return json.dumps(
            {"script_path": str(project_dir / "script.jsonl")},
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
