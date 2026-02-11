import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import PptxRequest, SlideElement, SlideOutline
from ppt_generator.tools.pptx.service import PptxService


def register_pptx_tools(mcp: FastMCP, pptx_service: PptxService) -> None:
    @mcp.tool()
    def generate_pptx(outline_json: str, images_json: str = "{}") -> str:
        """아웃라인과 이미지를 결합하여 편집 가능한 PPTX 파일을 생성합니다.

        슬라이드 아웃라인 JSON과 이미지 경로 정보를 받아 python-pptx로
        텍스트/이미지가 개별 객체로 분리된 편집 가능한 PPTX 파일을 조립합니다.
        발표자 노트에 스크립트가 포함됩니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열
            images_json: generate_images로 생성된 이미지 경로 JSON 문자열

        Returns:
            생성된 .pptx 파일 경로
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

        request = PptxRequest(slides=slides, image_paths=image_paths)
        response = pptx_service.generate(request)
        return response.pptx_path
