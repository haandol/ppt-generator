import logging

from strands import Agent

from ppt_generator.interfaces.constants import OUTLINE_USER_PROMPT_TEMPLATE
from ppt_generator.interfaces.schemas import OutlineRequest, OutlineResponse, SlideOutline
from ppt_generator.interfaces.utils import extract_json_from_response

MAX_RETRIES = 3

logger = logging.getLogger(__name__)


class OutlineService:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def generate(self, request: OutlineRequest) -> OutlineResponse:
        if not request.topic.strip():
            raise ValueError("주제가 비어있습니다.")

        prompt = OUTLINE_USER_PROMPT_TEMPLATE.format(
            topic=request.topic, num_slides=request.num_slides
        )

        last_error: ValueError | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            result = str(self._agent(prompt))
            try:
                data = self._parse_json(result)
            except ValueError as e:
                last_error = e
                logger.warning("아웃라인 JSON 파싱 실패 (시도 %d/%d): %s", attempt, MAX_RETRIES, e)
                continue
            slides = self._build_slides(data)
            return OutlineResponse(slides=slides)

        raise last_error  # type: ignore[misc]

    def _parse_json(self, text: str) -> dict:
        data = extract_json_from_response(text)

        if "slides" not in data or not isinstance(data["slides"], list):
            raise ValueError("JSON에 'slides' 배열이 없습니다.")

        return data

    def _build_slides(self, data: dict) -> list[SlideOutline]:
        slides: list[SlideOutline] = []
        for item in data["slides"]:
            component_hint = item.get("component_hint", "bullets")

            slides.append(
                SlideOutline(
                    title=item.get("title", ""),
                    content_summary=item.get("content_summary", ""),
                    component_hint=component_hint,
                    slide_type=item.get("slide_type", "content"),
                )
            )
        return slides
