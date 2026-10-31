"""design 스펙 리뷰 핸들러 (prepare/ingest, 슬라이드 단위).

리뷰 LLM 호출은 클라이언트가 수행한다. 서버는 기계적 lint 를 돌려 프롬프트에 힌트로
싣고(prepare), 클라이언트가 생성한 리뷰 결과 JSON 을 검증한다(ingest). auto-fix 재생성은
클라이언트가 update-slide prepare/ingest 를 이어서 호출하는 것으로 대체된다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ppt_generator.interfaces.index_validation import require_positive_slide_index
from ppt_generator.interfaces.schemas import DesignSpec, ProjectMetadata
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import (
    design_spec_to_json,
    slide_spec_fingerprint,
)
from ppt_generator.interfaces.utils import parse_outline_json
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
    directives = project_service.load_design_directives(project_dir, slide_index)

    task = deps.review_service.prepare(
        spec,
        slide_index=slide_index,
        lint_result=lint_result,
        design_directives=directives,
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
            "design_directives": directives,
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
    if context.get("design_directives", "") != project_service.load_design_directives(
        project_dir, slide_index
    ):
        raise ValueError("Stale review_context: design intent changed after prepare")
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
    return slide_spec_fingerprint(spec)


def handle_prepare_deck_review(
    deps: DesignDeps,
    *,
    project_id: str,
) -> str:
    """덱 전체의 근거·서사·반복을 검토하는 read-only 태스크를 조립한다."""
    if deps.review_service is None:
        raise ValueError("Review service is not configured.")
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    outline_json = project_service.load_outline(project_dir)
    outline = parse_outline_json(outline_json)
    design_spec = project_service.load_design_spec(project_dir)
    metadata = project_service.load_metadata(project_dir)
    review_inputs = _deck_review_inputs(project_dir, metadata)
    fingerprint = _deck_fingerprint(outline_json, design_spec, review_inputs)
    task = deps.review_service.prepare_deck(
        outline,
        design_spec,
        presentation_minutes=metadata.presentation_minutes,
        **review_inputs,
    )
    task["project_id"] = project_id
    task["review_context"] = encode_signed_context(
        {
            "kind": "deck_review",
            "version": 1,
            "project_id": project_id,
            "fingerprint": fingerprint,
            "slide_count": len(design_spec.slides),
        },
        project_dir,
    )
    return json.dumps(task, ensure_ascii=False)


def handle_ingest_deck_review(
    deps: DesignDeps,
    *,
    project_id: str,
    review_json: str,
    review_context: str,
) -> str:
    """덱 전체 review 결과를 검증해 의미 변경 필요 여부를 보고한다."""
    if deps.review_service is None:
        raise ValueError("Review service is not configured.")
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    context = decode_signed_context(review_context, project_dir)
    if (
        context.get("kind") != "deck_review"
        or context.get("version") != 1
        or context.get("project_id") != project_id
    ):
        raise ValueError("review_context does not match deck review request")
    outline_json = project_service.load_outline(project_dir)
    design_spec = project_service.load_design_spec(project_dir)
    review_inputs = _deck_review_inputs(
        project_dir, project_service.load_metadata(project_dir)
    )
    if context.get("fingerprint") != _deck_fingerprint(
        outline_json, design_spec, review_inputs
    ):
        raise ValueError("Stale review_context: deck changed after prepare")

    output = deps.review_service.ingest_deck(review_json)
    slide_count = len(design_spec.slides)
    for issue in output.issues:
        if any(index > slide_count for index in issue.slide_indices):
            raise ValueError("deck review issue references an invalid slide")
    issues = [issue.model_dump() for issue in output.issues]
    return json.dumps(
        {
            "project_id": project_id,
            "has_high_severity": output.has_high_severity,
            "issue_count": len(issues),
            "issues": issues,
            "requires_user_decision": output.has_high_severity,
        },
        ensure_ascii=False,
    )


def _deck_review_inputs(project_dir: Path, metadata: ProjectMetadata) -> dict:
    """리뷰가 판단에 사용한 문서와 발표 조건을 같은 형태로 재구성한다."""
    path = project_dir / "DESIGN.md"
    return {
        "design_intent": path.read_text(encoding="utf-8") if path.exists() else "",
        "presentation_context": {
            "topic": metadata.topic,
            "purpose": metadata.purpose,
            "audience_type": metadata.audience_type,
            "presentation_minutes": metadata.presentation_minutes,
        },
    }


def _deck_fingerprint(
    outline_json: str, design_spec: DesignSpec, review_inputs: dict
) -> str:
    """슬라이드뿐 아니라 판단 기준 변경 후의 오래된 리뷰도 거부한다."""
    import hashlib

    payload = (
        outline_json
        + "\n"
        + design_spec_to_json(design_spec)
        + "\n"
        + json.dumps(review_inputs, ensure_ascii=False, sort_keys=True)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
