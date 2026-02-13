import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import DesignSpecRequest
from ppt_generator.interfaces.spec_utils import design_spec_to_json, parse_design_spec_json
from ppt_generator.interfaces.utils import parse_outline_json
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService


def register_design_tools(
    mcp: FastMCP,
    design_service: DesignService,
    project_service: ProjectService,
) -> None:
    @mcp.tool()
    def generate_design_spec(outline_json: str, project_id: str = "") -> str:
        """아웃라인을 기반으로 디자인 스펙(PptxSlideSpec JSON)을 생성합니다.

        슬라이드 아웃라인 JSON을 받아 각 슬라이드의 정밀한 시각적 레이아웃을
        PptxSlideSpec 형식으로 생성합니다. 생성된 디자인 스펙은
        generate_slides(design_spec_json=...)이나 export_pptx(design_spec_json=...)의
        입력으로 사용할 수 있습니다.

        Args:
            outline_json: generate_script로 생성된 슬라이드 아웃라인 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            design_spec_json, design_spec_path, project_id를 포함하는 JSON 문자열
        """
        outline = parse_outline_json(outline_json)
        request = DesignSpecRequest(slides=outline.slides)
        response = design_service.generate(request)

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        spec_json = design_spec_to_json(response.design_spec)
        project_service.save_design_spec(project_dir, spec_json)
        project_service.update_step(project_dir, "design_spec")

        return json.dumps(
            {
                "design_spec_json": spec_json,
                "design_spec_path": str(project_dir / "design_spec.json"),
                "project_id": project_id,
            },
            ensure_ascii=False,
        )
