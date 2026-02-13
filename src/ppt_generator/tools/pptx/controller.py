import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import ExportPptxRequest
from ppt_generator.interfaces.spec_utils import parse_design_spec_json
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.project.service import ProjectService


def register_pptx_tools(mcp: FastMCP, export_service: ExportService, project_service: ProjectService) -> None:
    @mcp.tool()
    def export_pptx(session_id: str = "", design_spec_json: str = "", project_id: str = "") -> str:
        """세션의 HTML 슬라이드 또는 디자인 스펙을 편집 가능한 PPTX 파일로 내보냅니다.

        세 가지 모드로 동작합니다:
        1. design_spec_json 제공 시: 디자인 스펙에서 직접 PPTX 생성 (빠르고 정확)
        2. session_id 제공 시: HTML 세션을 파싱하여 PPTX 변환 (기존 방식)
        3. project_id만 제공 시: 프로젝트 디렉토리에서 디자인 스펙을 자동 로드하여 PPTX 생성 (권장)

        Args:
            session_id: generate_slides가 반환한 세션 ID
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
        elif session_id:
            request = ExportPptxRequest(session_id=session_id)
            response = export_service.export(request, output_dir=project_dir)
        else:
            try:
                spec_json = project_service.load_design_spec(project_dir)
                design_spec = parse_design_spec_json(spec_json)
                response = export_service.export_from_design_spec(
                    design_spec, output_dir=project_dir,
                )
            except FileNotFoundError:
                raise ValueError(
                    "session_id, design_spec_json 중 하나를 제공하거나, "
                    "generate_design_spec을 먼저 실행하여 프로젝트에 디자인 스펙을 저장하세요."
                )

        project_service.update_step(project_dir, "pptx")

        return json.dumps(
            {"project_id": project_id, "pptx_path": response.pptx_path},
            ensure_ascii=False,
        )
