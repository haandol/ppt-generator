"""슬라이드 복잡도 추정 + thinking effort 변환 단위 테스트."""

import pytest

from ppt_generator.interfaces.constants import COMPONENT_HINT_COMPLEXITY
from ppt_generator.interfaces.schemas import SlideOutline
from ppt_generator.interfaces.utils import (
    complexity_to_budget_tokens,
    estimate_slide_complexity,
)


class TestEstimateSlideComplexity:
    """estimate_slide_complexity 단위 테스트 (1-5 scale)."""

    def test_title_slide_always_1(self) -> None:
        slide = SlideOutline(
            title="제목",
            content_summary="긴 내용" * 100,
            component_hint="arch_diagram",
            slide_type="title",
        )
        assert estimate_slide_complexity(slide) == 1

    def test_closing_slide_always_1(self) -> None:
        slide = SlideOutline(
            title="끝",
            content_summary="긴 내용" * 100,
            component_hint="process_flow",
            slide_type="closing",
        )
        assert estimate_slide_complexity(slide) == 1

    def test_arch_diagram(self) -> None:
        slide = SlideOutline(
            title="아키텍처",
            content_summary="짧은 내용",
            component_hint="arch_diagram",
        )
        assert estimate_slide_complexity(slide) == 5

    def test_bullets(self) -> None:
        slide = SlideOutline(
            title="불릿",
            content_summary="짧은 내용",
            component_hint="bullets",
        )
        assert estimate_slide_complexity(slide) == 1

    def test_quote(self) -> None:
        slide = SlideOutline(
            title="인용문",
            content_summary="짧은 내용",
            component_hint="quote",
        )
        assert estimate_slide_complexity(slide) == 1

    def test_content_length_does_not_affect(self) -> None:
        """content_summary 길이는 복잡도에 영향을 주지 않는다."""
        short = SlideOutline(
            title="테스트",
            content_summary="짧은 내용",
            component_hint="step_cards",
        )
        long = SlideOutline(
            title="테스트",
            content_summary="가" * 1000,
            component_hint="step_cards",
        )
        assert estimate_slide_complexity(short) == estimate_slide_complexity(long) == 3

    def test_unknown_component_hint_defaults_to_2(self) -> None:
        slide = SlideOutline(
            title="테스트",
            content_summary="짧은 내용",
            component_hint="unknown_hint",
        )
        assert estimate_slide_complexity(slide) == 2

    def test_max_complexity_is_5(self) -> None:
        """arch_diagram / process_flow = 5 (최대값)."""
        slide = SlideOutline(
            title="테스트",
            content_summary="가" * 1000,
            component_hint="arch_diagram",
        )
        assert estimate_slide_complexity(slide) == 5

    @pytest.mark.parametrize("hint,expected", list(COMPONENT_HINT_COMPLEXITY.items()))
    def test_all_known_hints_mapped(self, hint: str, expected: int) -> None:
        """모든 알려진 component_hint가 매핑에 포함되어 있는지 검증."""
        slide = SlideOutline(
            title="테스트",
            content_summary="짧은 내용",
            component_hint=hint,
        )
        assert estimate_slide_complexity(slide) == expected


class TestComplexityToBudgetTokens:
    """complexity_to_budget_tokens 단위 테스트 (1-5 scale)."""

    @pytest.mark.parametrize(
        "complexity,expected",
        [
            (1, 1024),
            (2, 4096),
            (3, 4096),
            (4, 4096),
            (5, 10240),
        ],
    )
    def test_budget_mapping(self, complexity: int, expected: int) -> None:
        assert complexity_to_budget_tokens(complexity) == expected

    def test_boundary_1_is_1024(self) -> None:
        assert complexity_to_budget_tokens(1) == 1024

    def test_boundary_2_is_4096(self) -> None:
        assert complexity_to_budget_tokens(2) == 4096

    def test_boundary_3_is_4096(self) -> None:
        assert complexity_to_budget_tokens(3) == 4096

    def test_boundary_4_is_4096(self) -> None:
        assert complexity_to_budget_tokens(4) == 4096

    def test_boundary_5_is_10240(self) -> None:
        assert complexity_to_budget_tokens(5) == 10240

    def test_agenda_complexity_is_1(self) -> None:
        """agenda 슬라이드는 복잡도 1 → budget_tokens 1024."""
        slide = SlideOutline(
            title="Agenda",
            content_summary="발표 순서",
            component_hint="agenda",
        )
        complexity = estimate_slide_complexity(slide)
        assert complexity == 1
        assert complexity_to_budget_tokens(complexity) == 1024
