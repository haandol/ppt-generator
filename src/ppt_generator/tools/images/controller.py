import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import ImageRequest, SlideElement, SlideOutline
from ppt_generator.tools.images.service import ImageService
from ppt_generator.tools.project.service import ProjectService


def register_image_tools(mcp: FastMCP, image_service: ImageService, project_service: ProjectService) -> None:
    @mcp.tool()
    def generate_images(outline_json: str, project_id: str = "") -> str:
        """슬라이드 아웃라인의 image_idea를 기반으로 슬라이드별 이미지를 생성합니다.

        각 슬라이드의 image_idea 필드를 사용하여 Gemini Image Generation으로 이미지를 생성합니다.
        image_idea가 없거나 layout_type이 title, text_only, closing인 슬라이드는 건너뜁니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            생성된 이미지 파일 경로 목록 JSON (project_id 포함)
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

        project_id, project_dir = project_service.resolve_project_dir(project_id)
        response = image_service.generate(request, output_dir=project_dir / "images")
        result = json.dumps(asdict(response), ensure_ascii=False, indent=2)

        project_service.save_images_meta(project_dir, result)
        project_service.update_step(project_dir, "images")

        return json.dumps(
            {**json.loads(result), "project_id": project_id},
            ensure_ascii=False,
            indent=2,
        )
