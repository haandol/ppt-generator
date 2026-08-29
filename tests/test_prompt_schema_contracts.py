"""프롬프트에 열거된 값과 구조화 응답 모델의 계약 검증."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, get_args

import pytest

from ppt_generator.interfaces.constants import (
    DESIGN_REVIEW_SYSTEM_PROMPT,
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_SYSTEM_PROMPTS,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
    OUTLINE_SYSTEM_PROMPT,
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)
from ppt_generator.interfaces.llm_output_models import (
    ClosingSlideSpecOutput,
    ContentSlideSpecOutput,
    DesignReviewIssue,
    ShapeOutput,
    SimpleSlideSpecOutput,
    TextBoxOutput,
    TitleSlideSpecOutput,
    VisualQAIssue,
    VisualQAContentSlideSpecOutput,
    VisualQASimpleSlideSpecOutput,
)


def _literal_values(model, field_name: str) -> set[str]:
    return set(get_args(model.model_fields[field_name].annotation))


# 파라미터를 str 로 두면 타입 검사기가 Literal 필드 대입을 오류로 보므로,
# 응답 모델과 같은 Literal 로 좁힌다. 값이 어긋나면 아래 계약 테스트가 잡는다.
DesignReviewRuleId = Literal[
    "font_size_floor",
    "lr_font_consistency",
    "vstack_overlap",
    "vstack_height_uniformity",
    "vstack_gap_uniformity",
    "lr_bottom_alignment",
    "same_level_overlap",
    "peer_font_consistency",
    "peer_padding_consistency",
]
DesignReviewSeverity = Literal["high", "medium"]


def test_design_review_literal_aliases_match_model() -> None:
    """위 alias 가 응답 모델의 Literal 과 어긋나면 실패한다."""
    assert set(get_args(DesignReviewRuleId)) == _literal_values(
        DesignReviewIssue, "rule_id"
    )
    assert set(get_args(DesignReviewSeverity)) == _literal_values(
        DesignReviewIssue, "severity"
    )


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


def test_component_hint_docs_table_matches_outline_prompt() -> None:
    """component_hint 목록은 outline 프롬프트가 정본이다 — 문서 표가 뒤처지면 실패."""
    section = re.search(
        r"Available component_hint values:\n(.*?)(?:\n\s*\n|\n<)",
        OUTLINE_SYSTEM_PROMPT,
        re.S,
    )
    assert section, "outline 프롬프트의 component_hint 목록 섹션을 찾지 못했다"
    prompt_values = set(re.findall(r"^- ([a-z_]+):", section.group(1), re.M))
    schemas_md = (
        Path(__file__).resolve().parents[1] / "docs" / "harness" / "schemas.md"
    ).read_text(encoding="utf-8")
    doc_values = set(re.findall(r"^\| `([a-z_]+)`\s*\|", schemas_md, re.M))
    assert prompt_values, "outline 프롬프트에서 component_hint 목록을 찾지 못했다"
    assert doc_values == prompt_values


def test_slide_user_prompts_always_supply_region_bands() -> None:
    """시스템 프롬프트가 design_summary 의 region 을 읽으라고 지시하므로,
    design_summary 유무와 무관하게 두 user 템플릿 모두 region 값을 실어야 한다."""
    assert "come from design_summary" in DESIGN_SPEC_SYSTEM_PROMPTS["content"]
    for template in (
        DESIGN_SPEC_USER_PROMPT_TEMPLATE,
        DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    ):
        assert "<design_summary>" in template
    # 폴백 템플릿은 주입받을 값이 없으므로 기본 밴드를 문자열로 담고 있어야 한다.
    for key in ("header_region", "content_region", "footer_region"):
        assert key in DESIGN_SPEC_USER_PROMPT_TEMPLATE


def test_all_slide_type_prompts_include_line_geometry_contract() -> None:
    """title/closing 포함 모든 생성 경로가 line 좌표 계약을 동일하게 전달한다."""
    for slide_type, prompt in DESIGN_SPEC_SYSTEM_PROMPTS.items():
        assert "<line_geometry_contract>" in prompt, slide_type
        assert "height_px=0" in prompt, slide_type
        assert "width_px=0" in prompt, slide_type
        assert "border_width_pt" in prompt, slide_type
        assert "target box boundary" in prompt, slide_type


def test_design_prompt_separates_contracts_from_quality_guidance() -> None:
    base = DESIGN_SPEC_SYSTEM_PROMPTS["content"]
    assert "<enforcement_levels>" in base
    assert "consistency of the final JSON is evaluated" in base
    assert "do NOT revise upstream layers" not in base
    assert "Do not invent new positions in the Content layer" not in base
    assert "including a shallow diagonal" in base
    assert "Hard constraints (rendering will fail if violated)" not in base
    assert "<quality_guidance>" in base
    assert "Intentional asymmetric emphasis is allowed." in base
    assert "minimum font sizes (constraint 1)" not in base
    assert "font-range` lint rule still rejects" not in base
    assert "You MUST honor the outline's layout_plan" not in base
    assert "Five-Layer Hierarchy (MANDATORY" not in base
    assert "MUST NOT describe the slide structure" not in base
    assert "Do NOT invent your own y-axis bands" not in base
    assert "content cells must NOT extend" not in base
    assert "Endpoints must touch block edges exactly" not in base
    for prompt in DESIGN_SPEC_SYSTEM_PROMPTS.values():
        assert "Hard constraints (rendering will fail if violated)" not in prompt


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
    rule_id: DesignReviewRuleId, severity: DesignReviewSeverity
) -> None:
    """rule_id·severity 각각은 유효하지만, 그 *조합* 이 금지된 경우를 거부하는지 본다."""
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
        ("title", TitleSlideSpecOutput),
        ("closing", ClosingSlideSpecOutput),
    ],
)
def test_prompt_examples_validate_against_response_model(
    slide_type: str,
    model: (
        type[ContentSlideSpecOutput]
        | type[TitleSlideSpecOutput]
        | type[ClosingSlideSpecOutput]
    ),
) -> None:
    examples = re.findall(
        r"<layout_example[^>]*>\s*(\{.*?\})\s*</layout_example>",
        DESIGN_SPEC_SYSTEM_PROMPTS[slide_type],
        re.S,
    )
    assert examples
    for example in examples:
        model.model_validate(json.loads(example))
