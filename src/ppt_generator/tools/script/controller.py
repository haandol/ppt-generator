from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.constants import DEFAULT_NUM_SLIDES, MAX_NUM_SLIDES, MIN_NUM_SLIDES
from ppt_generator.interfaces.schemas import ScriptRequest
from ppt_generator.tools.script.service import ScriptService


def register_script_tools(mcp: FastMCP, script_service: ScriptService) -> None:
    @mcp.tool()
    def generate_script(topic: str, num_slides: int = DEFAULT_NUM_SLIDES) -> str:
        """주제와 슬라이드 수를 기반으로 자연스러운 발표 스크립트를 생성합니다.

        주어진 주제에 대해 도입-본론-결론 흐름을 갖춘 한국어 발표 스크립트를 생성합니다.
        슬라이드 구분 없이 연속적인 발표 스크립트가 반환됩니다.

        Args:
            topic: 발표 주제 (예: "2024년 클라우드 컴퓨팅 트렌드")
            num_slides: 슬라이드 수 (3~20, 기본값 5)

        Returns:
            생성된 발표 스크립트 텍스트
        """
        num_slides = max(MIN_NUM_SLIDES, min(MAX_NUM_SLIDES, num_slides))
        request = ScriptRequest(topic=topic, num_slides=num_slides)
        response = script_service.generate(request)
        return response.script
