import json
from dataclasses import asdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import ImageRequest, SlideElement, SlideOutline
from ppt_generator.tools.images.service import ImageService
from ppt_generator.tools.project.service import ProjectService


def register_image_tools(mcp: FastMCP, image_service: ImageService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_images(outline_json: str, project_dir: str = "") -> str:
        """슬라이드 아웃라인의 image_idea를 기반으로 슬라이드별 이미지를 생성합니다.

        각 슬라이드의 image_idea 필드를 사용하여 Titan Image Generator v2로 이미지를 생성합니다.
        image_idea가 없거나 layout_type이 text_only인 슬라이드는 건너뜁니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열
            project_dir: 결과물 저장 디렉토리 (미지정 시 저장 안 함)

        Returns:
            생성된 이미지 파일 경로 목록 JSON
        """
        data = json.loads(outline_json)
        slides = [
            SlideOutline(
                title=s.get("title", ""),
                bullets=s.get("bullets", []),
                image_idea=s.get("image_idea", ""),
                layout_type=s.get("layout_type", "text_only"),
                speaker_notes=s.get("speaker_notes", ""),
                elements=[
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
                    for e in s.get("elements", [])
                ],
            )
            for s in data["slides"]
        ]
        request = ImageRequest(slides=slides)
        response = image_service.generate(request)
        result = json.dumps(asdict(response), ensure_ascii=False, indent=2)
        if project_dir:
            project_service.save_images(Path(project_dir), result)
            project_service.update_step(Path(project_dir), "images")
        return result
