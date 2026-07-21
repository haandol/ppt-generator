"""design 스펙 리뷰 핸들러 (prepare/ingest, 슬라이드 단위).

리뷰 LLM 호출은 클라이언트가 수행한다. 서버는 기계적 lint 를 돌려 프롬프트에 힌트로
싣고(prepare), 클라이언트가 생성한 리뷰 결과 JSON 을 검증한다(ingest). auto-fix 재생성은
클라이언트가 update-slide prepare/ingest 를 이어서 호출하는 것으로 대체된다.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ppt_generator.interfaces.index_validation import require_positive_slide_index
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.tools.design.edit_context import (
    decode_signed_context,
    encode_signed_context,
)
from ppt_generator.tools.design.review_service import DesignReviewService

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


def handle_prepare_review(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
) -> str:
    """단일 슬라이드 리뷰 태스크를 조립한다 (lint 를 힌트로 실어 보냄)."""
    if deps.review_service is None:
        raise ValueError("Review service is not configured.")

    require_positive_slide_index(slide_index)
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)

    if slide_index < 1 or slide_index > slide_count:
        raise ValueError(
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
        )

    idx = slide_index - 1
    spec = project_service.load_design_spec_slide(project_dir, idx)
    lint_result = lint_slide_spec(spec)

    task = deps.review_service.prepare(
        spec, slide_index=slide_index, lint_result=lint_result
    )
    task["project_id"] = project_id
    task["slide_index"] = slide_index
    lint_issues = [
        {
            "source": "lint",
            "severity": "high" if violation.severity == "error" else "medium",
            "rule_id": violation.rule,
            "description": violation.message,
        }
        for violation in lint_result.violations
    ]
    task["review_context"] = encode_signed_context(
        {
            "kind": "design_review",
            "version": 1,
            "project_id": project_id,
            "slide_index": slide_index,
            "spec_fingerprint": _spec_fingerprint(spec),
            "lint_issues": lint_issues,
        },
        project_dir,
    )
    return json.dumps(task, ensure_ascii=False)


def handle_ingest_review(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    review_json: str,
    review_context: str,
) -> str:
    """클라이언트가 생성한 리뷰 결과 JSON 을 검증해 이슈 목록으로 반환한다.

    자동 재생성은 하지 않는다 (report-only). high-severity 이슈가 있으면 클라이언트가
    피드백을 담아 update-slide 로 재생성하도록 안내한다.
    """
    if deps.review_service is None:
        raise ValueError("Review service is not configured.")
    require_positive_slide_index(slide_index)
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)
    if slide_index > slide_count:
        raise ValueError(
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
        )

    context = decode_signed_context(review_context, project_dir)
    if (
        context.get("kind") != "design_review"
        or context.get("version") != 1
        or context.get("project_id") != project_id
        or context.get("slide_index") != slide_index
    ):
        raise ValueError("review_context does not match ingest request")
    current_spec = project_service.load_design_spec_slide(project_dir, slide_index - 1)
    if context.get("spec_fingerprint") != _spec_fingerprint(current_spec):
        raise ValueError("Stale review_context: slide changed after prepare")
    lint_issues = context.get("lint_issues")
    if not isinstance(lint_issues, list) or any(
        not isinstance(issue, dict) for issue in lint_issues
    ):
        raise ValueError("Invalid review_context lint issues")

    review_output = deps.review_service.ingest(review_json)
    llm_issues = [
        {
            "source": "review",
            "severity": issue.severity,
            "rule_id": issue.rule_id,
            "description": issue.description,
        }
        for issue in review_output.issues
    ]
    issues = [*lint_issues, *llm_issues]
    high_count = sum(1 for issue in issues if issue.get("severity") == "high")
    logger.info(
        "slide[%d] review ingested: %d issues (%d high)",
        slide_index,
        len(issues),
        high_count,
    )

    result: dict = {
        "project_id": project_id,
        "slide_index": slide_index,
        "has_high_severity": high_count > 0,
        "issue_count": len(issues),
        "issues": issues,
    }
    if high_count:
        result["fix_feedback"] = DesignReviewService.format_issue_feedback(issues)
        result["fix_suggestion"] = (
            f"슬라이드 {slide_index}에 high-severity 이슈가 있습니다. "
            "prepare_slide_edit(action='update') 로 재생성할 때 "
            "fix_feedback 을 함께 반영하세요."
        )
    return json.dumps(result, ensure_ascii=False)


def _spec_fingerprint(spec) -> str:
    import hashlib

    return hashlib.sha256(slide_spec_to_json(spec).encode("utf-8")).hexdigest()
