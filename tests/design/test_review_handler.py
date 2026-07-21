"""디자인 리뷰 prepare/ingest 핸들러 계약 테스트."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.llm_output_models import (
    DesignReviewIssue,
    DesignReviewOutput,
)
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)
from ppt_generator.tools.design.handlers.review import (
    handle_ingest_review,
    handle_prepare_review,
)

from _helpers import make_slide_spec


def _review_deps(tmp_path, review_output: DesignReviewOutput):
    deps = MagicMock()
    deps.project_service.resolve_existing_project_dir.return_value = (
        "project-1",
        tmp_path,
    )
    deps.project_service.get_design_spec_slide_count.return_value = 3
    deps.project_service.load_design_spec_slide.return_value = make_slide_spec("review")
    deps.review_service.prepare.return_value = {
        "system_prompt": "system",
        "user_prompt": "user",
        "response_schema": {},
    }
    deps.review_service.ingest.return_value = review_output
    return deps


def test_high_severity_fix_suggestion_uses_registered_edit_tool(tmp_path) -> None:
    deps = _review_deps(
        tmp_path,
        DesignReviewOutput(
            has_high_severity=True,
            issues=[
                DesignReviewIssue(
                    rule_id="font_size_floor",
                    severity="high",
                    description="본문 글자가 너무 작습니다.",
                )
            ],
        ),
    )
    prepared = json.loads(
        handle_prepare_review(deps, project_id="project-1", slide_index=2)
    )

    result = json.loads(
        handle_ingest_review(
            deps,
            project_id="project-1",
            slide_index=2,
            review_json="{}",
            review_context=prepared["review_context"],
        )
    )

    assert "prepare_slide_edit" in result["fix_suggestion"]
    assert "prepare_update_slide" not in result["fix_suggestion"]


def test_ingest_review_rejects_out_of_range_slide() -> None:
    deps = MagicMock()
    deps.project_service.resolve_existing_project_dir.return_value = (
        "project-1",
        MagicMock(),
    )
    deps.project_service.get_design_spec_slide_count.return_value = 1

    with pytest.raises(ValueError, match="valid range: 1-1"):
        handle_ingest_review(
            deps,
            project_id="project-1",
            slide_index=2,
            review_json="{}",
            review_context="",
        )

    deps.review_service.ingest.assert_not_called()


def test_high_severity_is_derived_from_issues() -> None:
    output = DesignReviewOutput(
        has_high_severity=False,
        issues=[
            DesignReviewIssue(
                rule_id="peer_font_consistency",
                severity="high",
                description="동급 카드의 제목 크기가 다릅니다.",
            )
        ],
    )
    assert output.has_high_severity is True


def test_lint_issues_are_merged_into_final_feedback(tmp_path, monkeypatch) -> None:
    deps = _review_deps(
        tmp_path,
        DesignReviewOutput(has_high_severity=False, issues=[]),
    )
    lint_result = SlideLintResult(
        slide_index=1,
        violations=[
            LintViolation(
                rule="text-overflow",
                severity="error",
                message="본문이 박스를 넘습니다.",
                element_index=0,
                element_type="textbox",
            )
        ],
    )
    monkeypatch.setattr(
        "ppt_generator.tools.design.handlers.review.lint_slide_spec",
        lambda spec: lint_result,
    )
    prepared = json.loads(
        handle_prepare_review(deps, project_id="project-1", slide_index=1)
    )

    result = json.loads(
        handle_ingest_review(
            deps,
            project_id="project-1",
            slide_index=1,
            review_json="{}",
            review_context=prepared["review_context"],
        )
    )

    assert result["has_high_severity"] is True
    assert result["issues"][0]["source"] == "lint"
    assert "text-overflow" in result["fix_feedback"]
