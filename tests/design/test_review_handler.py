"""디자인 리뷰 prepare/ingest 핸들러 계약 테스트."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ppt_generator.interfaces.llm_output_models import (
    DesignReviewIssue,
    DesignReviewOutput,
)
from ppt_generator.tools.design.handlers.review import handle_ingest_review


def test_high_severity_fix_suggestion_uses_registered_edit_tool() -> None:
    deps = MagicMock()
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
