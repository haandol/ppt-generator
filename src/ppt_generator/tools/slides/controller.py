import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.spec_utils import parse_design_spec_json  # inline parameter용
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService


def register_slides_tools(mcp: FastMCP, slides_service: SlidesService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_slides(design_spec_json: str = "", project_id: str = "") -> str:
        """디자인 스펙을 기반으로 슬라이드별 HTML 파일과 iframe 컨테이너를 생성합니다.

        두 가지 모드로 동작합니다:
        1. design_spec_json 제공 시: 디자인 스펙을 결정론적으로 HTML로 변환 (LLM 미사용, 빠르고 정확)
        2. project_id만 제공 시: 프로젝트 디렉토리에서 디자인 스펙을 자동 로드하여 HTML 변환 (권장)

        각 슬라이드는 slides/slide_NN.html로 개별 생성되며, slides.html은 iframe 컨테이너입니다.

        Args:
            design_spec_json: 디자인 스펙 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성). 단독 제공 시 디자인 스펙 자동 로드

        Returns:
            session_id, slides_html_path, slide_count, project_id를 포함하는 JSON 문자열
        """
        if design_spec_json:
            design_spec = parse_design_spec_json(design_spec_json)
            response = slides_service.generate_from_design_spec(design_spec)
        elif project_id:
            _, proj_dir = project_service.resolve_project_dir(project_id)
            design_spec = project_service.load_design_spec(proj_dir)
            response = slides_service.generate_from_design_spec(design_spec)
        else:
            raise ValueError(
                "design_spec_json, project_id 중 하나를 제공해야 합니다."
            )

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_slides_html(
            project_dir, response.session_id, response.slide_htmls, response.container_html,
        )
        project_service.update_step(project_dir, "slides")

        return json.dumps(
            {
                "session_id": response.session_id,
                "slides_html_path": str(project_dir / "slides.html"),
                "slide_count": len(response.slide_htmls),
                "project_id": project_id,
            },
            ensure_ascii=False,
        )
