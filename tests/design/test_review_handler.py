"""디자인 리뷰 prepare/ingest 핸들러 계약 테스트."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.llm_output_models import (
    DesignReviewIssue,
    DesignReviewOutput,
)
from ppt_generator.tools.design.handlers.review import handle_ingest_review


def test_high_severity_fix_suggestion_uses_registered_edit_tool() -> None:
    deps = MagicMock()
    deps.project_service.get_design_spec_slide_count.return_value = 3
    deps.review_service.ingest.return_value = DesignReviewOutput(
        has_high_severity=True,
        issues=[
            DesignReviewIssue(
                rule_id="font_size_floor",
                severity="high",
                description="본문 글자가 너무 작습니다.",
            )
        ],
    )

    result = json.loads(
        handle_ingest_review(
            deps,
            project_id="project-1",
            slide_index=2,
            review_json="{}",
        )
    )

    assert "prepare_slide_edit" in result["fix_suggestion"]
    assert "prepare_update_slide" not in result["fix_suggestion"]


def test_ingest_review_rejects_out_of_range_slide() -> None:
    deps = MagicMock()
    deps.project_service.get_design_spec_slide_count.return_value = 1

    with pytest.raises(ValueError, match="valid range: 1-1"):
        handle_ingest_review(
            deps,
            project_id="project-1",
            slide_index=2,
            review_json="{}",
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
