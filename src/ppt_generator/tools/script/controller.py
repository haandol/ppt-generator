import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import (
    OutlineResponse,
    ScriptRequest,
    SlideElement,
    SlideOutline,
)
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.script.service import ScriptService


def register_script_tools(mcp: FastMCP, script_service: ScriptService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_script(outline_json: str, project_id: str = "") -> str:
        """아웃라인을 기반으로 슬라이드별 발표자 노트(스크립트)를 생성합니다.

        generate_outline로 생성된 아웃라인 JSON을 입력받아, 각 슬라이드에 대한
        자연스러운 발표 스크립트를 생성하여 speaker_notes를 채운 아웃라인 JSON을 반환합니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            speaker_notes가 채워진 슬라이드 아웃라인 JSON 문자열 (project_id 포함)
        """
        outline = _parse_outline(outline_json)
        request = ScriptRequest(outline=outline)
        response = script_service.generate(request)
        result = json.dumps(
            {"slides": [asdict(s) for s in response.slides]},
            ensure_ascii=False,
            indent=2,
        )

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        project_service.save_script(project_dir, result)
        project_service.update_step(project_dir, "script")

        return json.dumps(
            {**json.loads(result), "project_id": project_id},
            ensure_ascii=False,
            indent=2,
        )


def _parse_outline(outline_json: str) -> OutlineResponse:
    data = json.loads(outline_json)
    slides: list[SlideOutline] = []
    for item in data["slides"]:
        elements = [
            SlideElement(
                type=e.get("type", "textbox"),
                left=float(e.get("left", 0)),
                top=float(e.get("top", 0)),
                width=float(e.get("width", 1)),
                height=float(e.get("height", 1)),
                content=e.get("content", ""),
                font_size_pt=int(e.get("font_size_pt", 16)),
                bold=bool(e.get("bold", False)),
            )
            for e in item.get("elements", [])
        ]
        slides.append(
            SlideOutline(
                title=item.get("title", ""),
                bullets=item.get("bullets", []),
                image_idea=item.get("image_idea", ""),
                layout_type=item.get("layout_type", "text_only"),
                speaker_notes=item.get("speaker_notes", ""),
                elements=elements,
            )
        )
    return OutlineResponse(slides=slides)
