from __future__ import annotations

import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import ImageRequest, SlideOutline
from ppt_generator.tools.images.service import ImageService
from ppt_generator.tools.project.service import ProjectService


def register_image_tools(
    mcp: FastMCP, image_service: ImageService | None, project_service: ProjectService
) -> None:
    @mcp.tool()
    def generate_images(outline_json: str, project_id: str = "") -> str:
        """슬라이드 아웃라인의 content_summary를 기반으로 슬라이드별 이미지를 생성합니다.

        layout_index가 28(text_image)인 슬라이드에 대해 content_summary를 사용하여
        Gemini Image Generation으로 이미지를 생성합니다.
        이미지가 불필요한 레이아웃(title, text_only, chart, closing, freeform)은 건너뜁니다.

        Args:
            outline_json: generate_outline로 생성된 슬라이드 아웃라인 JSON 문자열
            project_id: 프로젝트 ID (미지정 시 자동 생성)

        Returns:
            생성된 이미지 파일 경로 목록 JSON (project_id 포함)
        """
        if image_service is None:
            return json.dumps(
                {
                    "status": "skipped",
                    "message": "GEMINI_API_KEY 환경변수가 설정되지 않아 이미지 생성을 건너뜁니다. "
                    "이미지 생성을 사용하려면 GEMINI_API_KEY를 설정한 후 다시 시도하세요.",
                    "images": [],
                },
                ensure_ascii=False,
                indent=2,
            )

        data = json.loads(outline_json)
        slides = [
            SlideOutline(
                title=s.get("title", ""),
                content_summary=s.get("content_summary", ""),
                layout_index=s.get("layout_index", 22),
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
