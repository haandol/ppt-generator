"""Common utility functions.

Consolidates shared logic used across multiple services/controllers,
such as JSON extraction from LLM responses and SlideOutline parsing.
"""

from __future__ import annotations

import json
import logging
import re

from ppt_generator.interfaces.constants import COMPONENT_HINT_COMPLEXITY
from ppt_generator.interfaces.schemas import OutlineResponse, SlideOutline

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
    """Converts a complexity score (1-5) to a thinking budget_tokens value.

    5 → 4096 (high), 3-4 → 2048 (medium), 1-2 → 1024 (low).
    """
    if complexity >= 5:
        return 4096
    if complexity >= 3:
        return 2048
    return 1024


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


def complexity_to_qa_budget_tokens(complexity: int) -> int:
    """Visual QA fix용 budget_tokens. 생성 budget의 절반, low/medium 2단계.

    3+ → 2048 (medium), 1-2 → 1024 (low).
    """
    if complexity >= 3:
        return 2048
    return 1024


# Claude model pricing (USD / 1M tokens)
# https://www.anthropic.com/pricing
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "claude-opus-4-6": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "claude-haiku-3-5": {
        "input": 0.80,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_write": 1.0,
    },
    "claude-haiku-4-5": {
        "input": 0.80,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_write": 1.0,
    },
}

# model_id → pricing key mapping (strips Bedrock prefixes etc.)
_MODEL_ID_ALIASES: dict[str, str] = {
    "global.anthropic.claude-sonnet-4-6": "claude-sonnet-4-6",
    "anthropic.claude-sonnet-4-6-v1:0": "claude-sonnet-4-6",
    "global.anthropic.claude-opus-4-6": "claude-opus-4-6",
    "global.anthropic.claude-opus-4-6-v1": "claude-opus-4-6",
    "anthropic.claude-opus-4-6-v1:0": "claude-opus-4-6",
    "anthropic.claude-opus-4-6-v1": "claude-opus-4-6",
    "global.anthropic.claude-haiku-3-5": "claude-haiku-3-5",
    "anthropic.claude-3-5-haiku-20241022-v1:0": "claude-haiku-3-5",
    "global.anthropic.claude-haiku-4-5-20251001": "claude-haiku-4-5",
    "global.anthropic.claude-haiku-4-5-20251001-v1:0": "claude-haiku-4-5",
    "anthropic.claude-haiku-4-5-20251001-v1:0": "claude-haiku-4-5",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5",
}

_DEFAULT_PRICING_KEY = "claude-sonnet-4-6"


def _resolve_pricing_key(model_id: str) -> str:
    if model_id in _MODEL_PRICING:
        return model_id
    return _MODEL_ID_ALIASES.get(model_id, _DEFAULT_PRICING_KEY)


def estimate_cost(usage: dict[str, int], model_id: str = "") -> dict[str, float]:
    """Calculates estimated cost (USD) based on token usage and model ID.

    Args:
        usage: {inputTokens, outputTokens, cacheReadInputTokens, cacheWriteInputTokens, ...}
        model_id: Model ID (defaults to Sonnet 4.6 pricing if empty)

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
    """Converts a token usage dict into a cleaned dict suitable for response JSON."""
    if not usage:
        return {}
    result: dict[str, int] = {}
    for key in (
        "inputTokens",
        "outputTokens",
        "totalTokens",
        "cacheReadInputTokens",
        "cacheWriteInputTokens",
    ):
        val = usage.get(key, 0)
        if val:
            result[key] = val
    return result


def log_token_usage(result: object, label: str) -> dict[str, int]:
    """Logs token usage from an Agent call result.

    Args:
        result: strands Agent call result (AgentResult)
        label: Label for log identification (e.g., "outline", "script", "design_summary", "slide[0]")

    Returns:
        Token usage dict (inputTokens, outputTokens, totalTokens, etc.).
        Empty dict if metrics are unavailable.
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
            f"cache_read={cache_read:,}",
            f"cache_write={cache_write:,}",
        ]

        logger.info("[tokens] %s: %s", label, ", ".join(parts))
        return dict(usage)
    except (AttributeError, TypeError):
        logger.debug("토큰 사용량 추출 실패", exc_info=True)
        return {}
