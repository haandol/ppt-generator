import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import SlideOutline
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService


def register_slides_tools(mcp: FastMCP, slides_service: SlidesService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_slides(outline_json: str, project_id: str = "") -> str:
        """아웃라인을 기반으로 HTML/CSS 슬라이드를 생성합니다.

        슬라이드 아웃라인 JSON을 받아 Bedrock LLM이
        1280x720px 규격의 HTML/CSS 슬라이드를 생성합니다.
        반환되는 session_id를 사용하여 이후 슬라이드 수정이나
        PPTX 내보내기를 수행할 수 있습니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            session_id, html, project_id를 포함하는 JSON 문자열
        """
        outline_data = json.loads(outline_json)
        slides = [
            SlideOutline(
                title=s.get("title", ""),
                content_summary=s.get("content_summary", ""),
                layout_index=s.get("layout_index", 22),
                component_hint=s.get("component_hint", "bullets"),
                speaker_notes=s.get("speaker_notes", ""),
            )
            for s in outline_data["slides"]
        ]

        response = slides_service.generate(slides)

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_slides_html(
            project_dir, response.session_id, response.html,
        )
        project_service.update_step(project_dir, "slides")

        return json.dumps(
            {"session_id": response.session_id, "html": response.html, "project_id": project_id},
            ensure_ascii=False,
        )

    @mcp.tool()
    def modify_slides(
        session_id: str, modification_request: str,
        slide_index: int = -1, project_id: str = "",
    ) -> str:
        """세션의 HTML 슬라이드를 자연어 수정 요청에 따라 수정합니다.

        generate_slides로 생성된 세션의 슬라이드를 수정 요청에 따라 변경합니다.
        색상 변경, 텍스트 수정, 레이아웃 조정 등 다양한 수정이 가능합니다.
        동일한 session_id로 여러 번 호출하여 누적 수정할 수 있습니다.

        Args:
            session_id: generate_slides에서 반환된 세션 ID
            modification_request: 자연어 수정 요청 (예: "배경색을 파란색으로 변경해주세요")
            slide_index: 수정할 슬라이드 인덱스 (0부터, -1이면 전체)
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            session_id, html, project_id를 포함하는 JSON 문자열
        """
        response = slides_service.modify(session_id, modification_request, slide_index)

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_slides_html(
            project_dir, response.session_id, response.html,
        )
        project_service.update_step(project_dir, "slides_modified")

        return json.dumps(
            {"session_id": response.session_id, "html": response.html, "project_id": project_id},
            ensure_ascii=False,
        )
