import json
from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import OutlineRequest
from ppt_generator.tools.outline.service import OutlineService


def register_outline_tools(mcp: FastMCP, outline_service: OutlineService) -> None:
    @mcp.tool()
    def generate_outline(script: str) -> str:
        """발표 스크립트를 분석하여 슬라이드 아웃라인 JSON을 생성합니다.

        스크립트의 논리적 흐름을 분석하여 슬라이드별 제목, 본문 요점, 이미지 아이디어,
        레이아웃 타입, 발표자 노트를 포함한 구조화된 아웃라인을 생성합니다.

        Args:
            script: generate_script로 생성된 발표 스크립트 텍스트

        Returns:
            슬라이드 아웃라인 JSON 문자열
        """
        request = OutlineRequest(script=script)
        response = outline_service.generate(request)
        return json.dumps(asdict(response), ensure_ascii=False, indent=2)
