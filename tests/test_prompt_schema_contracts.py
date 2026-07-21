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
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)
from ppt_generator.interfaces.llm_output_models import (
    ContentSlideSpecOutput,
    DesignReviewIssue,
    ShapeOutput,
    SimpleSlideSpecOutput,
    TextBoxOutput,
    VisualQAIssue,
    VisualQAContentSlideSpecOutput,
    VisualQASimpleSlideSpecOutput,
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


def test_visual_qa_fix_prompt_preserves_content_and_structure() -> None:
    assert "Do NOT modify slide content" in VISUAL_QA_FIX_SYSTEM_PROMPT
    assert "Preserve the number and array order" in VISUAL_QA_FIX_SYSTEM_PROMPT
    assert "move excess content to speaker_notes" not in VISUAL_QA_FIX_SYSTEM_PROMPT
    assert "trim text" not in VISUAL_QA_FIX_SYSTEM_PROMPT


def test_z_index_is_scoped_to_visual_qa_schemas() -> None:
    assert "z_index" not in TextBoxOutput.model_fields
    assert "z_index" not in ShapeOutput.model_fields
    for model in (ContentSlideSpecOutput, SimpleSlideSpecOutput):
        schema = json.dumps(model.model_json_schema())
        assert '"z_index"' not in schema
    for model in (
        VisualQAContentSlideSpecOutput,
        VisualQASimpleSlideSpecOutput,
    ):
        schema = json.dumps(model.model_json_schema())
        assert '"z_index"' in schema


@pytest.mark.parametrize(
    ("rule_id", "severity"),
    [
        ("font_size_floor", "medium"),
        ("vstack_overlap", "medium"),
        ("vstack_height_uniformity", "high"),
        ("vstack_gap_uniformity", "high"),
        ("lr_bottom_alignment", "high"),
        ("same_level_overlap", "medium"),
        ("peer_padding_consistency", "high"),
    ],
)
def test_design_review_rejects_invalid_rule_severity(
    rule_id: str, severity: str
) -> None:
    with pytest.raises(ValueError, match="does not allow severity"):
        DesignReviewIssue(
            rule_id=rule_id,
            severity=severity,
            description="invalid combination",
        )


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
