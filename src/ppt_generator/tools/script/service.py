import json
import re

from strands import Agent

from ppt_generator.interfaces.constants import SCRIPT_USER_PROMPT_TEMPLATE
from ppt_generator.interfaces.schemas import ScriptRequest, ScriptResponse, SlideOutline


class ScriptService:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def generate(self, request: ScriptRequest) -> ScriptResponse:
        if not request.outline.slides:
            raise ValueError("아웃라인에 슬라이드가 없습니다.")

        outline_json = self._build_outline_json(request.outline.slides)
        prompt = SCRIPT_USER_PROMPT_TEMPLATE.format(outline_json=outline_json)
        result = str(self._agent(prompt))

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
                )
            )
        return merged

    def _parse_scripts(self, text: str) -> dict[int, str]:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        raw = match.group(1) if match else text

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM이 유효하지 않은 JSON을 반환했습니다: {e}") from e

        if "scripts" not in data or not isinstance(data["scripts"], list):
            raise ValueError("JSON에 'scripts' 배열이 없습니다.")

        result: dict[int, str] = {}
        for item in data["scripts"]:
            idx = item.get("slide_index", -1)
            notes = item.get("speaker_notes", "")
            if isinstance(idx, int) and idx >= 0:
                result[idx] = notes
        return result
