"""Design spec post-generation review service.

LLM 호출을 클라이언트로 오프로딩했다. 이 서비스는 리뷰 태스크를 조립(prepare)하고,
클라이언트가 생성한 리뷰 결과 JSON 을 검증(ingest)한다. 기계적 lint 결과를 힌트로
프롬프트에 실어 클라이언트가 이미 잡힌 위반을 중복 보고하지 않게 한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ppt_generator.interfaces.constants import DESIGN_REVIEW_SYSTEM_PROMPT
from ppt_generator.interfaces.handoff import build_llm_task
from ppt_generator.interfaces.llm_output_models import DesignReviewOutput
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.interfaces.spec_utils.lint_types import SlideLintResult
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json

logger = logging.getLogger(__name__)


class DesignReviewService:
    """생성된 PptxSlideSpec을 디자인 규칙 체크리스트로 리뷰한다 (prepare/ingest)."""

    def prepare(
        self,
        spec: PptxSlideSpec,
        slide_index: int,
        lint_result: SlideLintResult | None = None,
    ) -> dict:
        """슬라이드 리뷰를 위한 LLM 태스크를 조립한다.

        Args:
            spec: 리뷰할 디자인 스펙
            slide_index: 1-based 슬라이드 인덱스 (프롬프트용)
            lint_result: 코드 린트 결과. 전달되면 이미 기계적으로 잡힌 위반을
                프롬프트에 실어 중복 보고를 피한다. None 이면 자동 실행.
        """
        if lint_result is None:
            lint_result = lint_slide_spec(spec)

        spec_json = slide_spec_to_json(spec)
        lint_block = _format_lint_block(lint_result)
        prompt = (
            f"Review the following slide {slide_index} design spec JSON "
            f"against the review checklist.\n\n"
            f"{lint_block}"
            f"<design_spec>\n{spec_json}\n</design_spec>"
        )
        return build_llm_task(
            system_prompt=DESIGN_REVIEW_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=DesignReviewOutput.model_json_schema(),
        )

    def ingest(self, output_json: str | dict) -> DesignReviewOutput:
        """클라이언트가 생성한 리뷰 결과 JSON 을 검증한다."""
        if isinstance(output_json, str):
            return DesignReviewOutput.model_validate_json(output_json)
        return DesignReviewOutput.model_validate(output_json)

    @staticmethod
    def format_feedback(review_output: DesignReviewOutput) -> str:
        """리뷰 이슈를 재생성 프롬프트에 추가할 피드백 텍스트로 변환한다."""
        return DesignReviewService.format_issue_feedback(
            [
                {
                    "severity": issue.severity,
                    "rule_id": issue.rule_id,
                    "description": issue.description,
                }
                for issue in review_output.issues
            ]
        )

    @staticmethod
    def format_issue_feedback(issues: list[dict]) -> str:
        """lint와 LLM 리뷰 이슈를 함께 재생성 피드백으로 변환한다."""
        lines = [
            "<design_review_feedback>",
            "The previous generation had the following rule violations. "
            "Fix ALL of them in the regenerated output:",
        ]
        for issue in issues:
            lines.append(
                f"- [{str(issue['severity']).upper()}] "
                f"{issue['rule_id']}: {issue['description']}"
            )
        lines.append("</design_review_feedback>")
        return "\n".join(lines)


def _format_lint_block(lint_result: SlideLintResult) -> str:
    """린트 위반을 LLM 이 참고할 수 있는 텍스트 블록으로 변환한다.

    전달된 위반 목록은 이미 기계적으로 감지된 것이므로, LLM 에게는
    "이것들은 이미 알고 있다 — 시각/의미 레벨 이슈만 추가로 찾아라"
    라고 지시해 중복 보고를 피한다.
    """
    if not lint_result.violations:
        return (
            "<code_lint_results>\n"
            "No mechanical violations were found by the code-level lint.\n"
            "Focus on visual/semantic issues the lint cannot detect "
            "(balance, hierarchy, readability, color contrast, label clarity, etc.).\n"
            "</code_lint_results>\n\n"
        )

    lines = [
        "<code_lint_results>",
        "The following rule violations have already been detected by the code-level "
        "lint BEFORE this LLM review. Do NOT repeat them in your output — they are "
        "reported separately. Focus your review on visual/semantic issues that the "
        "lint cannot detect (balance, hierarchy, readability, color contrast, label "
        "clarity, layout intent, etc.).",
        "",
    ]
    for v in lint_result.violations:
        lines.append(
            f"- [{v.severity.upper()}] {v.rule} "
            f"({v.element_type}[{v.element_index}]): {v.message}"
        )
    lines.append("</code_lint_results>")
    lines.append("")
    return "\n".join(lines)


@dataclass
class ReviewResult:
    """리뷰 결과. review_issues에 발견된 이슈 목록을 담는다."""

    spec: PptxSlideSpec
    regenerated: bool = False
    review_issues: list[dict] = field(default_factory=list)
