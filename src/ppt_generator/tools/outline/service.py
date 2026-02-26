import logging

from strands import Agent
from strands.types.exceptions import ModelThrottledException

from ppt_generator.interfaces.constants import OUTLINE_USER_PROMPT_TEMPLATE
from ppt_generator.interfaces.schemas import OutlineRequest, OutlineResponse, SlideOutline
from ppt_generator.interfaces.utils import extract_json_from_response, log_token_usage

MAX_RETRIES = 3

logger = logging.getLogger(__name__)


class OutlineService:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._last_token_usage: dict[str, int] = {}

    @property
    def last_token_usage(self) -> dict[str, int]:
        """Token usage from the last LLM call."""
        return self._last_token_usage

    def generate(self, request: OutlineRequest) -> OutlineResponse:
        if not request.topic.strip():
            raise ValueError("Topic is empty.")

        prompt = OUTLINE_USER_PROMPT_TEMPLATE.format(
            topic=request.topic,
            num_slides=request.num_slides,
            audience_type=request.audience_type,
            presentation_minutes=request.presentation_minutes,
            purpose=request.purpose or "general presentation",
        )

        last_error: ValueError | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                agent_result = self._agent(prompt)
                self._last_token_usage = log_token_usage(agent_result, f"outline (attempt {attempt}/{MAX_RETRIES})")
                result = str(agent_result)
            except ModelThrottledException:
                logger.warning("Bedrock throttling during outline generation (attempt %d/%d)", attempt, MAX_RETRIES)
                if attempt == MAX_RETRIES:
                    raise
                continue
            try:
                data = self._parse_json(result)
            except ValueError as e:
                last_error = e
                logger.warning("Outline JSON parsing failed (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
                continue
            slides = self._build_slides(data)
            return OutlineResponse(slides=slides)

        raise last_error  # type: ignore[misc]

    def _parse_json(self, text: str) -> dict:
        data = extract_json_from_response(text)

        if "slides" not in data or not isinstance(data["slides"], list):
            raise ValueError("JSON does not contain a 'slides' array.")

        return data

    def _build_slides(self, data: dict) -> list[SlideOutline]:
        slides: list[SlideOutline] = []
        for i, item in enumerate(data["slides"]):
            component_hint = item.get("component_hint", "bullets")

            slides.append(
                SlideOutline(
                    title=item.get("title", ""),
                    content_summary=item.get("content_summary", ""),
                    component_hint=component_hint,
                    slide_type=item.get("slide_type", "content"),
                    slide_index=i,
                )
            )
        return slides
