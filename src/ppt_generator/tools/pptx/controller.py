import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.spec_utils import parse_design_spec_json  # inline parameter용
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.project.service import ProjectService


def register_pptx_tools(mcp: FastMCP, export_service: ExportService, project_service: ProjectService) -> None:
    @mcp.tool()
    def export_pptx(design_spec_json: str = "", project_id: str = "") -> str:
        """디자인 스펙을 편집 가능한 PPTX 파일로 내보냅니다.

        두 가지 모드로 동작합니다:
        1. design_spec_json 제공 시: 디자인 스펙에서 직접 PPTX 생성 (빠르고 정확)
        2. project_id만 제공 시: 프로젝트 디렉토리에서 디자인 스펙을 자동 로드하여 PPTX 생성 (권장)

        Args:
            design_spec_json: generate_design_spec으로 생성된 디자인 스펙 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성). 단독 제공 시 디자인 스펙 자동 로드

        Returns:
            project_id와 pptx_path를 포함하는 JSON 문자열
        """
        project_id, project_dir = project_service.resolve_project_dir(project_id)

        if design_spec_json:
            design_spec = parse_design_spec_json(design_spec_json)
            response = export_service.export_from_design_spec(
                design_spec, output_dir=project_dir,
            )
        else:
            try:
                design_spec = project_service.load_design_spec(project_dir)
                response = export_service.export_from_design_spec(
                    design_spec, output_dir=project_dir,
                )
            except FileNotFoundError:
                raise ValueError(
                    "design_spec_json을 제공하거나, "
                    "generate_design_spec을 먼저 실행하여 프로젝트에 디자인 스펙을 저장하세요."
                )

        project_service.update_step(project_dir, "pptx")

        return json.dumps(
            {"project_id": project_id, "pptx_path": response.pptx_path},
            ensure_ascii=False,
        )
