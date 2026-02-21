"""공통 유틸리티 함수.

LLM 응답에서 JSON 추출, SlideOutline 파싱 등
여러 서비스/컨트롤러에서 중복 사용되는 로직을 통합한 모듈.
"""

from __future__ import annotations

import json
import re

from ppt_generator.interfaces.constants import COMPONENT_HINT_COMPLEXITY
from ppt_generator.interfaces.schemas import OutlineResponse, SlideOutline


def extract_json_from_response(text: str) -> dict:
    """LLM 응답에서 JSON 코드블록을 추출하여 dict로 반환.

    마크다운 코드블록(```json ... ```)이 있으면 그 안의 JSON을 파싱하고,
    없으면 전체 텍스트를 JSON으로 파싱 시도한다.
    """
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    raw = match.group(1) if match else text

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM이 유효하지 않은 JSON을 반환했습니다: {e}") from e


def parse_outline_json(outline_json: str) -> OutlineResponse:
    """outline JSON 문자열을 OutlineResponse로 파싱.

    {"slides": [...]} 형식과 단일 슬라이드 객체 {"title": ...} 형식 모두 지원.
    """
    data = json.loads(outline_json)
    if "slides" not in data:
        data = {"slides": [data]}
    slides: list[SlideOutline] = []
    for item in data["slides"]:
        slides.append(
            SlideOutline(
                title=item.get("title", ""),
                content_summary=item.get("content_summary", ""),
                component_hint=item.get("component_hint", "bullets"),
                speaker_notes=item.get("speaker_notes", ""),
                slide_type=item.get("slide_type", "content"),
            )
        )
    return OutlineResponse(slides=slides)


def estimate_slide_complexity(slide: SlideOutline) -> int:
    """슬라이드의 디자인 스펙 생성 복잡도를 추정."""
    if slide.slide_type in ("title", "closing"):
        return 1
    base = COMPONENT_HINT_COMPLEXITY.get(slide.component_hint, 2)
    content_bonus = min(len(slide.content_summary) // 200, 3)
    return base + content_bonus


def complexity_to_thinking_effort(complexity: int) -> str:
    """복잡도 점수를 thinking effort 레벨로 변환."""
    if complexity >= 7:
        return "high"
    elif complexity >= 4:
        return "medium"
    else:
        return "low"
