"""슬라이드 복잡도 추정 + thinking effort 변환 단위 테스트."""

import pytest

from ppt_generator.interfaces.constants import COMPONENT_HINT_COMPLEXITY
from ppt_generator.interfaces.schemas import SlideOutline
from ppt_generator.interfaces.utils import (
    complexity_to_thinking_effort,
    estimate_slide_complexity,
)


class TestEstimateSlideComplexity:
    """estimate_slide_complexity 단위 테스트."""

    def test_title_slide_always_1(self) -> None:
        slide = SlideOutline(
            title="제목", content_summary="긴 내용" * 100,
            component_hint="arch_diagram", slide_type="title",
        )
        assert estimate_slide_complexity(slide) == 1

    def test_closing_slide_always_1(self) -> None:
        slide = SlideOutline(
            title="끝", content_summary="긴 내용" * 100,
            component_hint="process_flow", slide_type="closing",
        )
        assert estimate_slide_complexity(slide) == 1

    def test_arch_diagram_base(self) -> None:
        slide = SlideOutline(
            title="아키텍처", content_summary="짧은 내용",
            component_hint="arch_diagram",
        )
        assert estimate_slide_complexity(slide) == 10  # base=10, content_bonus=0

    def test_bullets_base(self) -> None:
        slide = SlideOutline(
            title="불릿", content_summary="짧은 내용",
            component_hint="bullets",
        )
        assert estimate_slide_complexity(slide) == 2  # base=2, content_bonus=0

    def test_quote_base(self) -> None:
        slide = SlideOutline(
            title="인용문", content_summary="짧은 내용",
            component_hint="quote",
        )
        assert estimate_slide_complexity(slide) == 1  # base=1, content_bonus=0

    def test_content_bonus_200_chars(self) -> None:
        """200자 이상이면 +1 보너스."""
        slide = SlideOutline(
            title="테스트", content_summary="가" * 200,
            component_hint="bullets",
        )
        assert estimate_slide_complexity(slide) == 3  # base=2 + bonus=1

    def test_content_bonus_max_3(self) -> None:
        """content_bonus는 최대 3."""
        slide = SlideOutline(
            title="테스트", content_summary="가" * 1000,
            component_hint="bullets",
        )
        assert estimate_slide_complexity(slide) == 5  # base=2 + bonus=3

    def test_content_bonus_exact_boundary(self) -> None:
        """199자는 보너스 0, 200자는 보너스 1."""
        slide_199 = SlideOutline(
            title="테스트", content_summary="가" * 199,
            component_hint="bullets",
        )
        slide_200 = SlideOutline(
            title="테스트", content_summary="가" * 200,
            component_hint="bullets",
        )
        assert estimate_slide_complexity(slide_199) == 2
        assert estimate_slide_complexity(slide_200) == 3

    def test_unknown_component_hint_defaults_to_2(self) -> None:
        slide = SlideOutline(
            title="테스트", content_summary="짧은 내용",
            component_hint="unknown_hint",
        )
        assert estimate_slide_complexity(slide) == 2

    def test_max_complexity_is_13(self) -> None:
        """arch_diagram(10) + 최대 content_bonus(3) = 13."""
        slide = SlideOutline(
            title="테스트", content_summary="가" * 1000,
            component_hint="arch_diagram",
        )
        assert estimate_slide_complexity(slide) == 13

    @pytest.mark.parametrize("hint,expected_base", list(COMPONENT_HINT_COMPLEXITY.items()))
    def test_all_known_hints_mapped(self, hint: str, expected_base: int) -> None:
        """모든 알려진 component_hint가 매핑에 포함되어 있는지 검증."""
        slide = SlideOutline(
            title="테스트", content_summary="짧은 내용",
            component_hint=hint,
        )
        assert estimate_slide_complexity(slide) == expected_base


class TestComplexityToThinkingEffort:
    """complexity_to_thinking_effort 단위 테스트."""

    @pytest.mark.parametrize("complexity,expected", [
        (1, "low"),
        (2, "low"),
        (3, "low"),
        (4, "medium"),
        (5, "medium"),
        (6, "medium"),
        (7, "medium"),
        (8, "medium"),
        (9, "high"),
        (10, "high"),
        (13, "high"),
    ])
    def test_effort_mapping(self, complexity: int, expected: str) -> None:
        assert complexity_to_thinking_effort(complexity) == expected

    def test_boundary_3_is_low(self) -> None:
        assert complexity_to_thinking_effort(3) == "low"

    def test_boundary_4_is_medium(self) -> None:
        assert complexity_to_thinking_effort(4) == "medium"

    def test_boundary_6_is_medium(self) -> None:
        assert complexity_to_thinking_effort(6) == "medium"

    def test_boundary_8_is_medium(self) -> None:
        assert complexity_to_thinking_effort(8) == "medium"

    def test_boundary_9_is_high(self) -> None:
        assert complexity_to_thinking_effort(9) == "high"
