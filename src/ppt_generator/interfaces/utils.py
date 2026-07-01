"""Common utility functions.

Consolidates shared logic used across multiple services/controllers,
such as JSON extraction from LLM responses and SlideOutline parsing.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from ppt_generator.interfaces.constants import COMPONENT_HINT_COMPLEXITY
from ppt_generator.interfaces.schemas import OutlineResponse, SlideOutline

if TYPE_CHECKING:
    from ppt_generator.interfaces.schemas import PptxSlideSpec

logger = logging.getLogger(__name__)


def extract_json_from_response(text: str) -> dict:
    """Extracts a JSON code block from the LLM response and returns it as a dict.

    If a markdown code block (```json ... ```) is found, parses the JSON inside it.
    Otherwise, attempts to parse the entire text as JSON.
    """
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    raw = match.group(1) if match else text

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}") from e


def parse_outline_json(outline_json: str) -> OutlineResponse:
    """Parses an outline JSON string into an OutlineResponse.

    Supports both {"slides": [...]} format and single slide object {"title": ...} format.
    """
    data = json.loads(outline_json)
    if "slides" not in data:
        data = {"slides": [data]}
    slides: list[SlideOutline] = []
    for i, item in enumerate(data["slides"]):
        slides.append(
            SlideOutline(
                title=item.get("title", ""),
                content_summary=item.get("content_summary", ""),
                component_hint=item.get("component_hint", "bullets"),
                speaker_notes=item.get("speaker_notes", ""),
                slide_type=item.get("slide_type", "content"),
                slide_index=item.get("slide_index", i),
                layout_plan=item.get("layout_plan", ""),
            )
        )
    return OutlineResponse(slides=slides)


def estimate_slide_complexity(slide: SlideOutline) -> int:
    """Estimates the design spec generation complexity of a slide (1-5 scale).

    Uses component_hint as base, then upgrades if layout_plan indicates many elements.
    """
    if slide.slide_type in ("title", "closing"):
        return 1
    if slide.component_hint == "agenda":
        return 1
    base = COMPONENT_HINT_COMPLEXITY.get(slide.component_hint, 2)
    if slide.layout_plan and _layout_plan_has_many_elements(slide.layout_plan):
        return max(base, 5)
    return base


def _layout_plan_has_many_elements(layout_plan: str) -> bool:
    """layout_plan 텍스트에서 요소 수가 6개 이상인지 휴리스틱으로 판단."""
    import re

    numbers = re.findall(
        r"(\d+)\s*(?:nodes?|cards?|items?|elements?|blocks?|columns?)",
        layout_plan,
        re.IGNORECASE,
    )
    for n in numbers:
        if int(n) >= 6:
            return True
    return False


def complexity_to_budget_tokens(complexity: int) -> int:
    """Complexity (1-5) → thinking budget_tokens 힌트 매핑.

    LLM 생성은 클라이언트가 수행하므로 서버가 예산을 강제하지는 않는다.
    prepare 응답에 권장 thinking budget 힌트로 실어 보내 클라이언트가
    복잡한 슬라이드에 더 많은 사고 예산을 쓰도록 안내한다.
    """
    if complexity <= 2:
        return 4096
    if complexity <= 4:
        return 8192
    return 12288


def estimate_spec_complexity(spec: "PptxSlideSpec") -> int:
    """PptxSlideSpec의 요소 수로 complexity를 추정한다 (1-5 scale).

    Visual QA fix 단계에서 outline 없이 complexity를 판단할 때 사용.
    """
    if spec.slide_type in ("title", "closing"):
        return 1
    total = len(spec.textboxes) + len(spec.shapes) + len(spec.images)
    if total >= 15:
        return 5
    if total >= 10:
        return 4
    if total >= 6:
        return 3
    if total >= 3:
        return 2
    return 1
