"""design 스펙 리뷰 핸들러 (prepare/ingest, 슬라이드 단위).

리뷰 LLM 호출은 클라이언트가 수행한다. 서버는 기계적 lint 를 돌려 프롬프트에 힌트로
싣고(prepare), 클라이언트가 생성한 리뷰 결과 JSON 을 검증한다(ingest). auto-fix 재생성은
클라이언트가 update-slide prepare/ingest 를 이어서 호출하는 것으로 대체된다.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from ppt_generator.interfaces.spec_utils import lint_slide_spec
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

    project_service = deps.project_service
    _, project_dir = project_service.resolve_project_dir(project_id)
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
    return json.dumps(task, ensure_ascii=False)


def handle_ingest_review(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    review_json: str,
) -> str:
    """클라이언트가 생성한 리뷰 결과 JSON 을 검증해 이슈 목록으로 반환한다.

    자동 재생성은 하지 않는다 (report-only). high-severity 이슈가 있으면 클라이언트가
    피드백을 담아 update-slide 로 재생성하도록 안내한다.
    """
    if deps.review_service is None:
        raise ValueError("Review service is not configured.")

    review_output = deps.review_service.ingest(review_json)
    high_count = sum(1 for i in review_output.issues if i.severity == "high")
    logger.info(
        "slide[%d] review ingested: %d issues (%d high)",
        slide_index,
        len(review_output.issues),
        high_count,
    )

    result: dict = {
        "project_id": project_id,
        "slide_index": slide_index,
        "has_high_severity": review_output.has_high_severity,
        "issue_count": len(review_output.issues),
        "issues": [
            {
                "severity": i.severity,
                "rule_id": i.rule_id,
                "description": i.description,
            }
            for i in review_output.issues
        ],
    }
    if review_output.has_high_severity:
        result["fix_feedback"] = DesignReviewService.format_feedback(review_output)
        result["fix_suggestion"] = (
            f"슬라이드 {slide_index}에 high-severity 이슈가 있습니다. "
            "prepare_update_slide 로 재생성할 때 fix_feedback 을 함께 반영하세요."
        )
    return json.dumps(result, ensure_ascii=False)
