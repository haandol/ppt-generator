import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.spec_utils import parse_design_spec_json  # inline parameter용
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.project.service import ProjectService


def register_pptx_tools(mcp: FastMCP, export_service: ExportService, project_service: ProjectService) -> None:
    @mcp.tool()
    def export_pptx(design_spec_json: str = "", project_id: str = "") -> str:
        """Exports the design spec as an editable PPTX file.

        Operates in two modes:
        1. When design_spec_json is provided: Generates PPTX directly from design spec (fast and accurate)
        2. When only project_id is provided: Auto-loads design spec from project directory to generate PPTX (recommended)

        Args:
            design_spec_json: Design spec JSON string
            project_id: Project ID (auto-generated if not specified). When provided alone, auto-loads the design spec

        Returns:
            JSON string containing project_id and pptx_path
        """
        project_id, project_dir = project_service.resolve_project_dir(project_id)

        if design_spec_json:
            design_spec = parse_design_spec_json(design_spec_json)
            response = export_service.export_from_design_spec(
                design_spec, output_dir=project_dir,
            )
        else:
            try:
                design_spec = project_service.load_design_spec_with_images(project_dir)
                metadata = project_service.load_metadata(project_dir)
                is_imported = "import" in metadata.steps_completed
                response = export_service.export_from_design_spec(
                    design_spec, output_dir=project_dir,
                    skip_autofit=is_imported,
                )
            except FileNotFoundError:
                raise ValueError(
                    "Either provide design_spec_json, or "
                    "run generate_slides_design_spec first to save a design spec to the project."
                )

        project_service.update_step(project_dir, "pptx")

        return json.dumps(
            {"project_id": project_id, "pptx_path": response.pptx_path},
            ensure_ascii=False,
        )
