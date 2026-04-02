"""Design spec post-generation review service.

생성된 디자인 스펙을 LLM으로 리뷰하여 규칙 위반을 감지한다.
Adaptive thinking 없는 Sonnet을 사용하여 빠르고 저렴하게 체크리스트 판단을 수행한다.
"""

from __future__ import annotations

import logging

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
        self._last_token_usage = log_token_usage(result, f"design_review[{slide_index}]")
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
            lines.append(f"- [{issue.severity.upper()}] {issue.rule_id}: {issue.description}")
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
