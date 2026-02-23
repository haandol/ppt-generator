"""공통 유틸리티 함수.

LLM 응답에서 JSON 추출, SlideOutline 파싱 등
여러 서비스/컨트롤러에서 중복 사용되는 로직을 통합한 모듈.
"""

from __future__ import annotations

import json
import logging
import re

from ppt_generator.interfaces.constants import COMPONENT_HINT_COMPLEXITY
from ppt_generator.interfaces.schemas import OutlineResponse, SlideOutline

logger = logging.getLogger(__name__)


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


# Claude 모델별 가격 (USD / 1M tokens)
# https://www.anthropic.com/pricing
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-4-6": {"input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75},
    "claude-haiku-3-5": {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_write": 1.0},
}

# model_id → pricing key 매핑 (Bedrock 등 접두어 제거)
_MODEL_ID_ALIASES: dict[str, str] = {
    "global.anthropic.claude-sonnet-4-6": "claude-sonnet-4-6",
    "anthropic.claude-sonnet-4-6-v1:0": "claude-sonnet-4-6",
    "global.anthropic.claude-opus-4-6": "claude-opus-4-6",
    "anthropic.claude-opus-4-6-v1:0": "claude-opus-4-6",
    "global.anthropic.claude-haiku-3-5": "claude-haiku-3-5",
    "anthropic.claude-3-5-haiku-20241022-v1:0": "claude-haiku-3-5",
}

_DEFAULT_PRICING_KEY = "claude-sonnet-4-6"


def _resolve_pricing_key(model_id: str) -> str:
    if model_id in _MODEL_PRICING:
        return model_id
    return _MODEL_ID_ALIASES.get(model_id, _DEFAULT_PRICING_KEY)


def estimate_cost(usage: dict[str, int], model_id: str = "") -> dict[str, float]:
    """토큰 사용량과 모델 ID를 기반으로 예상 비용(USD)을 계산한다.

    Args:
        usage: {inputTokens, outputTokens, cacheReadInputTokens, cacheWriteInputTokens, ...}
        model_id: 모델 ID (빈 문자열이면 기본 Sonnet 4.6 가격 적용)

    Returns:
        {"input_cost": ..., "output_cost": ..., "cache_read_cost": ..., "cache_write_cost": ..., "total_cost": ...}
    """
    if not usage:
        return {"input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0}

    key = _resolve_pricing_key(model_id) if model_id else _DEFAULT_PRICING_KEY
    pricing = _MODEL_PRICING.get(key, _MODEL_PRICING[_DEFAULT_PRICING_KEY])

    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    cache_read = usage.get("cacheReadInputTokens", 0)
    cache_write = usage.get("cacheWriteInputTokens", 0)

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    cache_read_cost = (cache_read / 1_000_000) * pricing.get("cache_read", 0)
    cache_write_cost = (cache_write / 1_000_000) * pricing.get("cache_write", 0)
    total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost

    result: dict[str, float] = {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
    }
    if cache_read_cost:
        result["cache_read_cost"] = round(cache_read_cost, 6)
    if cache_write_cost:
        result["cache_write_cost"] = round(cache_write_cost, 6)
    return result


def format_token_usage(usage: dict[str, int]) -> dict[str, int]:
    """토큰 사용량 dict를 응답 JSON에 포함할 수 있는 정리된 dict로 변환."""
    if not usage:
        return {}
    result: dict[str, int] = {}
    for key in ("inputTokens", "outputTokens", "totalTokens", "cacheReadInputTokens", "cacheWriteInputTokens"):
        val = usage.get(key, 0)
        if val:
            result[key] = val
    return result


def log_token_usage(result: object, label: str) -> dict[str, int]:
    """Agent 호출 결과에서 토큰 사용량을 로깅한다.

    Args:
        result: strands Agent 호출 결과 (AgentResult)
        label: 로그 식별용 라벨 (예: "outline", "script", "design_summary", "slide[0]")

    Returns:
        토큰 사용량 dict (inputTokens, outputTokens, totalTokens 등).
        메트릭을 가져올 수 없는 경우 빈 dict.
    """
    try:
        metrics = result.metrics  # type: ignore[union-attr]
        usage = metrics.accumulated_usage
        if not usage:
            return {}

        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        total_tokens = usage.get("totalTokens", 0)
        cache_read = usage.get("cacheReadInputTokens", 0)
        cache_write = usage.get("cacheWriteInputTokens", 0)

        parts = [
            f"input={input_tokens:,}",
            f"output={output_tokens:,}",
            f"total={total_tokens:,}",
        ]
        if cache_read:
            parts.append(f"cache_read={cache_read:,}")
        if cache_write:
            parts.append(f"cache_write={cache_write:,}")

        logger.info("[tokens] %s: %s", label, ", ".join(parts))
        return dict(usage)
    except (AttributeError, TypeError):
        return {}
