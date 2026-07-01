import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces import bg_image_utils
from ppt_generator.interfaces.spec_utils import (
    parse_design_spec_json,
)  # inline parameter용
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.project.service import ProjectService


def register_pptx_tools(
    mcp: FastMCP, export_service: ExportService, project_service: ProjectService
) -> None:
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

        # 배경 이미지 선택을 프로젝트 단위로 고정 — 재export·경로(HTML/PPTX)와
        # 무관하게 같은 프로젝트는 같은 배경을 쓰도록 시드를 건다.
        bg_image_utils.set_project_seed(project_id)

        # design_summary에서 color_theme 로드
        design_summary = project_service.load_design_summary(project_dir)
        color_theme = (design_summary or {}).get("color_theme", "dark")
        bg_image_policy = project_service.load_bg_image_policy(project_dir)

        if design_spec_json:
            design_spec = parse_design_spec_json(design_spec_json)
            response = export_service.export_from_design_spec(
                design_spec,
                output_dir=project_dir,
                color_theme=color_theme,
                bg_image_policy=bg_image_policy,
            )
        else:
            try:
                design_spec = project_service.load_design_spec_with_images(project_dir)
                metadata = project_service.load_metadata(project_dir)
                is_imported = "import" in metadata.steps_completed
                response = export_service.export_from_design_spec(
                    design_spec,
                    output_dir=project_dir,
                    skip_autofit=is_imported,
                    color_theme=color_theme,
                    bg_image_policy=bg_image_policy,
                )
            except FileNotFoundError:
                raise ValueError(
                    "Either provide design_spec_json, or "
                    "run prepare_design_slide / ingest_design_slide first to save a design spec to the project."
                )

        project_service.update_step(project_dir, "pptx")

        return json.dumps(
            {"project_id": project_id, "pptx_path": response.pptx_path},
            ensure_ascii=False,
        )
