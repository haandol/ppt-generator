import json
import re

from strands import Agent

from ppt_generator.interfaces.constants import (
    OUTLINE_FREEFORM_USER_PROMPT_TEMPLATE,
    OUTLINE_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.schemas import OutlineRequest, OutlineResponse, SlideElement, SlideOutline

VALID_LAYOUT_TYPES = {"title", "text_image", "text_only", "chart", "closing", "freeform"}


class OutlineService:
    def __init__(self, agent: Agent, freeform_agent: Agent | None = None) -> None:
        self._agent = agent
        self._freeform_agent = freeform_agent

    def generate(self, request: OutlineRequest, freeform: bool = False) -> OutlineResponse:
        if not request.topic.strip():
            raise ValueError("주제가 비어있습니다.")

        if freeform and self._freeform_agent is not None:
            prompt = OUTLINE_FREEFORM_USER_PROMPT_TEMPLATE.format(
                topic=request.topic, num_slides=request.num_slides
            )
            result = str(self._freeform_agent(prompt))
        else:
            prompt = OUTLINE_USER_PROMPT_TEMPLATE.format(
                topic=request.topic, num_slides=request.num_slides
            )
            result = str(self._agent(prompt))
        data = self._parse_json(result)
        slides = self._build_slides(data)
        return OutlineResponse(slides=slides)

    def _parse_json(self, text: str) -> dict:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        raw = match.group(1) if match else text

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM이 유효하지 않은 JSON을 반환했습니다: {e}") from e

        if "slides" not in data or not isinstance(data["slides"], list):
            raise ValueError("JSON에 'slides' 배열이 없습니다.")

        return data

    def _build_slides(self, data: dict) -> list[SlideOutline]:
        slides: list[SlideOutline] = []
        for item in data["slides"]:
            layout_type = item.get("layout_type", "text_only")
            if layout_type not in VALID_LAYOUT_TYPES:
                layout_type = "text_only"

            elements = [
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
                for e in item.get("elements", [])
            ]

            slides.append(
                SlideOutline(
                    title=item.get("title", ""),
                    bullets=item.get("bullets", []),
                    image_idea=item.get("image_idea", ""),
                    layout_type=layout_type,
                    speaker_notes=item.get("speaker_notes", ""),
                    elements=elements,
                )
            )
        return slides
