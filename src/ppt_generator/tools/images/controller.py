import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import ImageRequest, SlideOutline
from ppt_generator.tools.images.service import ImageService


def register_image_tools(mcp: FastMCP, image_service: ImageService) -> None:
    @mcp.tool()
    def generate_images(outline_json: str) -> str:
        """슬라이드 아웃라인의 image_idea를 기반으로 슬라이드별 이미지를 생성합니다.

        각 슬라이드의 image_idea 필드를 사용하여 Titan Image Generator v2로 이미지를 생성합니다.
        image_idea가 없거나 layout_type이 text_only인 슬라이드는 건너뜁니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열

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
            )
            for s in data["slides"]
        ]
        request = ImageRequest(slides=slides)
        response = image_service.generate(request)
        return json.dumps(asdict(response), ensure_ascii=False, indent=2)
