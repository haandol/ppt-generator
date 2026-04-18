"""Design spec post-generation review service.

생성된 디자인 스펙을 LLM으로 리뷰하여 규칙 위반을 감지한다.
Extended thinking 없는 Sonnet을 사용하여 빠르고 저렴하게 체크리스트 판단을 수행한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from strands import Agent

from ppt_generator.interfaces.llm_output_models import DesignReviewOutput
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.interfaces.utils import log_token_usage

logger = logging.getLogger(__name__)


class DesignReviewService:
    """생성된 PptxSlideSpec을 디자인 규칙 체크리스트로 리뷰한다."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._last_token_usage: dict[str, int] = {}

    def review(self, spec: PptxSlideSpec, slide_index: int) -> DesignReviewOutput:
        """슬라이드 스펙을 리뷰하고 구조화된 결과를 반환한다.

        Args:
            spec: 리뷰할 디자인 스펙
            slide_index: 1-based 슬라이드 인덱스 (로깅용)

        Returns:
            DesignReviewOutput (has_high_severity, issues)
        """
        spec_json = slide_spec_to_json(spec)
        prompt = (
            f"Review the following slide {slide_index} design spec JSON "
            f"against the review checklist.\n\n"
            f"<design_spec>\n{spec_json}\n</design_spec>"
        )
        result = self._agent(prompt, structured_output_model=DesignReviewOutput)
        self._last_token_usage = log_token_usage(
            result, f"design_review[{slide_index}]"
        )
        return result.structured_output

    @property
    def last_token_usage(self) -> dict[str, int]:
        return self._last_token_usage

    @staticmethod
    def format_feedback(review_output: DesignReviewOutput) -> str:
        """리뷰 이슈를 재생성 프롬프트에 추가할 피드백 텍스트로 변환한다."""
        lines = [
            "<design_review_feedback>",
            "The previous generation had the following rule violations. "
            "Fix ALL of them in the regenerated output:",
        ]
        for issue in review_output.issues:
            lines.append(
                f"- [{issue.severity.upper()}] {issue.rule_id}: {issue.description}"
            )
        lines.append("</design_review_feedback>")
        return "\n".join(lines)


def merge_token_usage(*usages: dict[str, int]) -> dict[str, int]:
    """여러 토큰 사용량 dict를 합산한다."""
    merged: dict[str, int] = {}
    for u in usages:
        if not u:
            continue
        for k, v in u.items():
            merged[k] = merged.get(k, 0) + v
    return merged


@dataclass
class ReviewResult:
    """리뷰 결과. review_issues에 발견된 이슈 목록을 담는다."""

    spec: PptxSlideSpec
    token_usage: dict[str, int]
    regenerated: bool = False
    review_issues: list[dict] = field(default_factory=list)


def apply_review_and_fix(
    *,
    spec: PptxSlideSpec,
    slide_index: int,
    gen_usage: dict[str, int],
    review_service_factory: Callable[[], DesignReviewService],
    regenerate: Callable[[str], tuple[PptxSlideSpec, dict[str, int]]],
) -> ReviewResult:
    """리뷰를 실행하고 결과를 리포트한다.

    자동 재생성은 수행하지 않는다. high-severity 이슈가 있어도
    현재 스펙을 그대로 저장하고, 리뷰 결과를 ReviewResult.review_issues에 담아 반환한다.
    사용자가 리포트를 확인한 뒤 modify_design_spec 등으로 직접 수정을 요청할 수 있다.

    Args:
        spec: 리뷰할 디자인 스펙
        slide_index: 1-based 슬라이드 인덱스
        gen_usage: 초기 생성 토큰 사용량
        review_service_factory: DesignReviewService 팩토리
        regenerate: feedback 문자열을 받아 (new_spec, regen_usage)를 반환하는 콜백
            (현재는 사용되지 않으며, 호환성을 위해 유지)

    Returns:
        ReviewResult (spec, token_usage, regenerated=False, review_issues)
    """
    review_svc = review_service_factory()
    review_output = review_svc.review(spec, slide_index=slide_index)
    review_usage = review_svc.last_token_usage

    if review_output.has_high_severity:
        high_count = sum(1 for i in review_output.issues if i.severity == "high")
        logger.info(
            "slide[%d] review: %d high-severity issues found (report only, no auto-regeneration)",
            slide_index,
            high_count,
        )
    else:
        logger.info(
            "slide[%d] review passed (%d issues, none high)",
            slide_index,
            len(review_output.issues),
        )

    return ReviewResult(
        spec=spec,
        token_usage=merge_token_usage(gen_usage, review_usage),
        regenerated=False,
        review_issues=[
            {
                "rule_id": issue.rule_id,
                "severity": issue.severity,
                "description": issue.description,
            }
            for issue in review_output.issues
        ],
    )
