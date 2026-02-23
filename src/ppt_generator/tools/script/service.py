import json
import logging

from strands import Agent
from strands.types.exceptions import ModelThrottledException

from ppt_generator.interfaces.constants import SCRIPT_USER_PROMPT_TEMPLATE
from ppt_generator.interfaces.schemas import ScriptRequest, ScriptResponse, SlideOutline
from ppt_generator.interfaces.utils import extract_json_from_response, log_token_usage

logger = logging.getLogger(__name__)


class ScriptService:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._last_token_usage: dict[str, int] = {}

    @property
    def last_token_usage(self) -> dict[str, int]:
        """직전 LLM 호출의 토큰 사용량."""
        return self._last_token_usage

    def generate(self, request: ScriptRequest) -> ScriptResponse:
        if not request.outline.slides:
            raise ValueError("아웃라인에 슬라이드가 없습니다.")

        outline_json = self._build_outline_json(request.outline.slides)
        num_slides = len(request.outline.slides)
        minutes_per_slide = round(request.presentation_minutes / max(num_slides, 1), 1)
        prompt = SCRIPT_USER_PROMPT_TEMPLATE.format(
            outline_json=outline_json,
            audience_level=request.audience_level,
            presentation_minutes=request.presentation_minutes,
            num_slides=num_slides,
            minutes_per_slide=minutes_per_slide,
        )
        try:
            agent_result = self._agent(prompt)
            self._last_token_usage = log_token_usage(agent_result, "script")
            result = str(agent_result)
        except ModelThrottledException:
            logger.warning("스크립트 생성 중 Bedrock 쓰로틀링 발생")
            raise

        scripts = self._parse_scripts(result)
        merged = self._merge_notes(request.outline.slides, scripts)
        return ScriptResponse(slides=merged)

    def _build_outline_json(self, slides: list[SlideOutline]) -> str:
        data = []
        for i, slide in enumerate(slides):
            data.append(
                {
                    "slide_index": i,
                    "title": slide.title,
                    "content_summary": slide.content_summary,
                }
            )
        return json.dumps({"slides": data}, ensure_ascii=False, indent=2)

    @staticmethod
    def _merge_notes(slides: list[SlideOutline], scripts: dict[int, str]) -> list[SlideOutline]:
        merged: list[SlideOutline] = []
        for i, slide in enumerate(slides):
            notes = scripts.get(i, "")
            merged.append(
                SlideOutline(
                    title=slide.title,
                    content_summary=slide.content_summary,
                    component_hint=slide.component_hint,
                    speaker_notes=notes,
                    slide_type=slide.slide_type,
                )
            )
        return merged

    def _parse_scripts(self, text: str) -> dict[int, str]:
        data = extract_json_from_response(text)

        if "scripts" not in data or not isinstance(data["scripts"], list):
            raise ValueError("JSON에 'scripts' 배열이 없습니다.")

        result: dict[int, str] = {}
        for item in data["scripts"]:
            idx = item.get("slide_index", -1)
            notes = item.get("speaker_notes", "")
            if isinstance(idx, int) and idx >= 0:
                result[idx] = notes
        return result
