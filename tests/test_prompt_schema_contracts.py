"""프롬프트에 열거된 값과 구조화 응답 모델의 계약 검증."""

from __future__ import annotations

import json
import re
from typing import get_args

import pytest

from ppt_generator.interfaces.constants import (
    DESIGN_REVIEW_SYSTEM_PROMPT,
    DESIGN_SPEC_SYSTEM_PROMPTS,
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
)
from ppt_generator.interfaces.llm_output_models import (
    ContentSlideSpecOutput,
    DesignReviewIssue,
    SimpleSlideSpecOutput,
    VisualQAIssue,
)


def _literal_values(model, field_name: str) -> set[str]:
    return set(get_args(model.model_fields[field_name].annotation))


def test_visual_qa_issue_types_match_prompt() -> None:
    prompt_values = set(
        re.findall(r"^\| `([a-z0-9_]+)` \|", VISUAL_QA_ANALYSIS_SYSTEM_PROMPT, re.M)
    )
    assert prompt_values == _literal_values(VisualQAIssue, "issue_type")


def test_design_review_rule_ids_match_prompt() -> None:
    prompt_values = set(
        re.findall(r"^\d+\. \*\*([a-z0-9_]+)\*\*", DESIGN_REVIEW_SYSTEM_PROMPT, re.M)
    )
    assert prompt_values == _literal_values(DesignReviewIssue, "rule_id")


@pytest.mark.parametrize(
    ("slide_type", "model"),
    [
        ("content", ContentSlideSpecOutput),
        ("title", SimpleSlideSpecOutput),
        ("closing", SimpleSlideSpecOutput),
    ],
)
def test_prompt_examples_validate_against_response_model(
    slide_type: str,
    model: type[ContentSlideSpecOutput] | type[SimpleSlideSpecOutput],
) -> None:
    examples = re.findall(
        r"<layout_example[^>]*>\s*(\{.*?\})\s*</layout_example>",
        DESIGN_SPEC_SYSTEM_PROMPTS[slide_type],
        re.S,
    )
    assert examples
    for example in examples:
        model.model_validate(json.loads(example))
