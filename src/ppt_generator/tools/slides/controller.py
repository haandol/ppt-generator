import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import SlidesRequest, SlideElement, SlideOutline
from ppt_generator.tools.slides.service import SlidesService


def register_slides_tools(mcp: FastMCP, slides_service: SlidesService) -> None:
    @mcp.tool()
    def generate_slides(outline_json: str, images_json: str = "{}") -> str:
        """아웃라인과 이미지를 기반으로 HTML/CSS 슬라이드를 생성합니다.

        슬라이드 아웃라인 JSON과 이미지 경로 정보를 받아 Bedrock LLM이
        960x540px 규격의 HTML/CSS 슬라이드를 생성합니다.
        반환되는 session_id를 사용하여 이후 슬라이드 수정(F5)이나
        PPTX 내보내기(F6)를 수행할 수 있습니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열
            images_json: generate_images로 생성된 이미지 경로 JSON 문자열

        Returns:
            session_id와 html을 포함하는 JSON 문자열
        """
        outline_data = json.loads(outline_json)
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
            for s in outline_data["slides"]
        ]

        images_data = json.loads(images_json)
        image_paths: dict[int, str] = {}
        for img in images_data.get("images", []):
            image_paths[img["slide_index"]] = img["image_path"]

        request = SlidesRequest(slides=slides, image_paths=image_paths)
        response = slides_service.generate(request)
        return json.dumps(
            {"session_id": response.session_id, "html": response.html},
            ensure_ascii=False,
        )
