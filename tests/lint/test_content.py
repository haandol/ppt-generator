"""Content layer lint 테스트.

단일 textbox/shape 의 텍스트·픽셀·스타일 위반:
- title-font-min, font-range, canvas-overflow,
  decorative-no-rounding, hidden-decorative-strip,
  spacer-paragraph, row-autofit-mismatch / row-expand-height-unsafe,
  expand-height-collision, zero-size-shape, nowrap-overflow
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from lint._lint_helpers import slide, tb


# ---------------------------------------------------------------------------
# title-font-min
# ---------------------------------------------------------------------------


class TestTitleFontMin:
    def test_content_slide_title_below_24pt(self) -> None:
        result = lint_slide_spec(slide(textboxes=[tb("제목 텍스트", font=16)]))
        assert result.has_violations
        title_violations = [v for v in result.violations if v.rule == "title-font-min"]
        assert len(title_violations) == 1
        v = title_violations[0]
        assert v.severity == "error"
        assert v.current_value == 16

    def test_title_slide_title_below_36pt(self) -> None:
        result = lint_slide_spec(
            slide(textboxes=[tb("발표 제목", font=24)], slide_type="title")
        )
        assert result.has_violations
        violations = [v for v in result.violations if v.rule == "title-font-min"]
        assert len(violations) >= 1
        assert violations[0].current_value == 24

    def test_closing_slide_title_below_36pt(self) -> None:
        result = lint_slide_spec(
            slide(textboxes=[tb("감사합니다", font=20)], slide_type="closing")
        )
        violations = [v for v in result.violations if v.rule == "title-font-min"]
        assert len(violations) >= 1

    def test_title_above_min_no_violation(self) -> None:
        result = lint_slide_spec(slide(textboxes=[tb("큰 제목", font=32)]))
        assert not [v for v in result.violations if v.rule == "title-font-min"]

    def test_second_textbox_not_checked_for_title(self) -> None:
        title_tb = tb("제목", font=28)
        body_tb = tb("본문 작은 글씨", font=12, top_px=150)
        result = lint_slide_spec(slide(textboxes=[title_tb, body_tb]))
        assert not [v for v in result.violations if v.rule == "title-font-min"]

    def test_spec_not_modified(self) -> None:
        spec = slide(textboxes=[tb("제목 텍스트", font=16)])
        lint_slide_spec(spec)
        assert spec.textboxes[0].paragraphs[0].runs[0].font_size_pt == 16


# ---------------------------------------------------------------------------
# font-range
# ---------------------------------------------------------------------------


class TestFontRange:
    def test_font_below_min(self) -> None:
        result = lint_slide_spec(
            slide(
                textboxes=[
                    tb("제목", font=24),
                    tb("너무 작은 폰트", font=8, top_px=200),
                ]
            )
        )
        range_violations = [v for v in result.violations if v.rule == "font-range"]
        assert len(range_violations) >= 1
        assert range_violations[0].current_value == 8

    def test_font_above_max(self) -> None:
        result = lint_slide_spec(slide(textboxes=[tb("너무 큰 폰트", font=50)]))
        range_violations = [v for v in result.violations if v.rule == "font-range"]
        assert len(range_violations) >= 1
        assert range_violations[0].current_value == 50

    def test_font_in_range_no_violation(self) -> None:
        result = lint_slide_spec(slide(textboxes=[tb("정상 폰트", font=24)]))
        assert not [v for v in result.violations if v.rule == "font-range"]

    def test_shape_font_below_min(self) -> None:
        shape = PptxShape(
            left_px=64,
            top_px=148,
            width_px=400,
            height_px=200,
            shape_type="rounded_rectangle",
            fill_color="#2E3D50",
            text="카드",
            text_size_pt=8,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        range_violations = [v for v in result.violations if v.rule == "font-range"]
        assert len(range_violations) >= 1
        assert range_violations[0].element_type == "shape"

    def test_shape_paragraph_font_checked(self) -> None:
        shape = PptxShape(
            left_px=64,
            top_px=148,
            width_px=400,
            height_px=200,
            shape_type="rounded_rectangle",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="작은 글", font_size_pt=6)])
            ],
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert [v for v in result.violations if v.rule == "font-range"]


# ---------------------------------------------------------------------------
# canvas-overflow
# ---------------------------------------------------------------------------


class TestCanvasOverflow:
    def test_textbox_overflow_right(self) -> None:
        result = lint_slide_spec(
            slide(textboxes=[tb("넘침", font=24, left_px=1200, width_px=200)])
        )
        assert [v for v in result.violations if v.rule == "canvas-overflow"]

    def test_textbox_overflow_bottom(self) -> None:
        result = lint_slide_spec(
            slide(textboxes=[tb("넘침", font=24, top_px=700, height_px=100)])
        )
        assert [v for v in result.violations if v.rule == "canvas-overflow"]

    def test_textbox_negative_left(self) -> None:
        result = lint_slide_spec(slide(textboxes=[tb("넘침", font=24, left_px=-10)]))
        assert [v for v in result.violations if v.rule == "canvas-overflow"]

    def test_textbox_within_canvas_no_violation(self) -> None:
        result = lint_slide_spec(
            slide(
                textboxes=[
                    tb(
                        "정상",
                        font=24,
                        left_px=64,
                        top_px=64,
                        width_px=500,
                        height_px=50,
                    )
                ]
            )
        )
        assert not [v for v in result.violations if v.rule == "canvas-overflow"]

    def test_decorative_shape_ignored(self) -> None:
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1400,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "canvas-overflow"]

    def test_shape_with_text_overflow_detected(self) -> None:
        shape = PptxShape(
            left_px=1200,
            top_px=100,
            width_px=200,
            height_px=100,
            shape_type="rectangle",
            text="넘치는 shape",
            text_size_pt=16,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert [v for v in result.violations if v.rule == "canvas-overflow"]


# ---------------------------------------------------------------------------
# decorative-no-rounding
# ---------------------------------------------------------------------------


class TestDecorativeNoRounding:
    def test_decorative_with_rounding_detected(self) -> None:
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1280,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
            corner_radius_px=8,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        violations = [
            v for v in result.violations if v.rule == "decorative-no-rounding"
        ]
        assert len(violations) == 1
        assert violations[0].current_value == 8

    def test_decorative_without_rounding_no_violation(self) -> None:
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1280,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "decorative-no-rounding"]

    def test_decorative_with_zero_radius_no_violation(self) -> None:
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1280,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
            corner_radius_px=0,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "decorative-no-rounding"]

    def test_non_decorative_with_rounding_no_violation(self) -> None:
        shape = PptxShape(
            left_px=64,
            top_px=148,
            width_px=400,
            height_px=200,
            shape_type="rounded_rectangle",
            fill_color="#2E3D50",
            text="카드",
            text_size_pt=16,
            corner_radius_px=12,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "decorative-no-rounding"]

    def test_thin_vertical_decorative_with_rounding(self) -> None:
        shape = PptxShape(
            left_px=640,
            top_px=100,
            width_px=3,
            height_px=500,
            shape_type="rectangle",
            fill_color="#CCCCCC",
            corner_radius_px=5,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        violations = [
            v for v in result.violations if v.rule == "decorative-no-rounding"
        ]
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# hidden-decorative-strip
# ---------------------------------------------------------------------------


class TestHiddenDecorativeStripRule:
    def test_strip_behind_card_detected(self) -> None:
        bar = PptxShape(
            left_px=626,
            top_px=148,
            width_px=6,
            height_px=160,
            shape_type="rectangle",
            fill_color="#FFC000",
            z_index=10,
        )
        card = PptxShape(
            left_px=626,
            top_px=148,
            width_px=590,
            height_px=160,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            z_index=11,
        )
        result = lint_slide_spec(slide(shapes=[bar, card]))
        violations = [
            v for v in result.violations if v.rule == "hidden-decorative-strip"
        ]
        assert len(violations) == 1
        assert violations[0].element_index == 0

    def test_strip_on_top_no_violation(self) -> None:
        card = PptxShape(
            left_px=626,
            top_px=148,
            width_px=590,
            height_px=160,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            z_index=10,
        )
        bar = PptxShape(
            left_px=626,
            top_px=148,
            width_px=6,
            height_px=160,
            shape_type="rectangle",
            fill_color="#FFC000",
            z_index=11,
        )
        result = lint_slide_spec(slide(shapes=[card, bar]))
        assert not [v for v in result.violations if v.rule == "hidden-decorative-strip"]

    def test_z_index_none_uses_array_order(self) -> None:
        bar = PptxShape(
            left_px=626,
            top_px=148,
            width_px=6,
            height_px=160,
            shape_type="rectangle",
            fill_color="#FFC000",
        )
        card = PptxShape(
            left_px=626,
            top_px=148,
            width_px=590,
            height_px=160,
            shape_type="rounded_rectangle",
            fill_color="#243447",
        )
        result = lint_slide_spec(slide(shapes=[bar, card]))
        violations = [
            v for v in result.violations if v.rule == "hidden-decorative-strip"
        ]
        assert len(violations) == 1

    def test_strip_not_contained_no_violation(self) -> None:
        bar = PptxShape(
            left_px=64,
            top_px=148,
            width_px=6,
            height_px=160,
            shape_type="rectangle",
            fill_color="#FFC000",
            z_index=10,
        )
        card = PptxShape(
            left_px=626,
            top_px=148,
            width_px=590,
            height_px=160,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            z_index=11,
        )
        result = lint_slide_spec(slide(shapes=[bar, card]))
        assert not [v for v in result.violations if v.rule == "hidden-decorative-strip"]


# ---------------------------------------------------------------------------
# spacer-paragraph
# ---------------------------------------------------------------------------


def _card_with_paragraphs(paragraphs, fill_color: str = "#243447") -> PptxShape:
    return PptxShape(
        left_px=626,
        top_px=148,
        width_px=590,
        height_px=160,
        shape_type="rounded_rectangle",
        fill_color=fill_color,
        paragraphs=paragraphs,
        autofit_mode="shrink_text",
    )


class TestSpacerParagraphRule:
    def test_spacer_paragraph_detected(self) -> None:
        card = _card_with_paragraphs(
            [
                PptxParagraph(
                    runs=[PptxTextRun(text="01 제목", font_size_pt=18, color="#FFC000")]
                ),
                PptxParagraph(
                    runs=[PptxTextRun(text=" ", font_size_pt=10, color="#243447")]
                ),
                PptxParagraph(
                    runs=[PptxTextRun(text="본문", font_size_pt=16, color="#D5DBDB")]
                ),
            ]
        )
        result = lint_slide_spec(slide(shapes=[card]))
        violations = [v for v in result.violations if v.rule == "spacer-paragraph"]
        assert len(violations) == 1
        assert violations[0].current_value["paragraph_index"] == 1

    def test_real_text_paragraph_no_violation(self) -> None:
        card = _card_with_paragraphs(
            [
                PptxParagraph(
                    runs=[PptxTextRun(text="01 제목", font_size_pt=18, color="#FFC000")]
                ),
                PptxParagraph(
                    runs=[PptxTextRun(text="본문", font_size_pt=16, color="#D5DBDB")]
                ),
            ]
        )
        result = lint_slide_spec(slide(shapes=[card]))
        assert not [v for v in result.violations if v.rule == "spacer-paragraph"]

    def test_spacer_with_different_color_no_violation(self) -> None:
        card = _card_with_paragraphs(
            [
                PptxParagraph(
                    runs=[PptxTextRun(text=" ", font_size_pt=10, color="#FF0000")]
                ),
            ]
        )
        result = lint_slide_spec(slide(shapes=[card]))
        assert not [v for v in result.violations if v.rule == "spacer-paragraph"]


# ---------------------------------------------------------------------------
# row-autofit-consistency
# ---------------------------------------------------------------------------


def _row_card(top_px, autofit_mode, *, idx_label: str = "01") -> PptxShape:
    return PptxShape(
        left_px=626,
        top_px=top_px,
        width_px=590,
        height_px=160,
        shape_type="rounded_rectangle",
        fill_color="#243447",
        paragraphs=[
            PptxParagraph(
                runs=[
                    PptxTextRun(
                        text=f"{idx_label} 제목", font_size_pt=18, color="#FFC000"
                    )
                ]
            ),
        ],
        autofit_mode=autofit_mode,
    )


class TestRowAutofitConsistency:
    def test_mixed_autofit_modes_detected(self) -> None:
        a = _row_card(148.0, "shrink_text", idx_label="01")
        b = _row_card(148.0, "expand_height", idx_label="02")
        result = lint_slide_spec(slide(shapes=[a, b]))
        rule_violations = [
            v for v in result.violations if v.rule == "row-autofit-mismatch"
        ]
        assert len(rule_violations) == 2

    def test_both_expand_height_in_row_detected(self) -> None:
        a = _row_card(148.0, "expand_height", idx_label="01")
        b = _row_card(148.0, "expand_height", idx_label="02")
        result = lint_slide_spec(slide(shapes=[a, b]))
        violations = [
            v for v in result.violations if v.rule == "row-expand-height-unsafe"
        ]
        assert len(violations) == 2

    def test_both_shrink_text_in_row_no_violation(self) -> None:
        a = _row_card(148.0, "shrink_text", idx_label="01")
        b = _row_card(148.0, "shrink_text", idx_label="02")
        result = lint_slide_spec(slide(shapes=[a, b]))
        assert not [
            v
            for v in result.violations
            if v.rule in ("row-autofit-mismatch", "row-expand-height-unsafe")
        ]

    def test_different_rows_not_grouped(self) -> None:
        a = _row_card(148.0, "shrink_text", idx_label="01")
        b = _row_card(322.0, "expand_height", idx_label="02")
        result = lint_slide_spec(slide(shapes=[a, b]))
        assert not [
            v
            for v in result.violations
            if v.rule in ("row-autofit-mismatch", "row-expand-height-unsafe")
        ]


# ---------------------------------------------------------------------------
# expand-height-collision
# ---------------------------------------------------------------------------


class TestExpandHeightCollision:
    def _long_shape(self, top: int, height: int = 56) -> PptxShape:
        long_text = (
            "긴 프롬프트 1개를 전체 복사해 Claude Code 에 붙여넣어 "
            "이 텍스트는 한 줄을 반드시 넘겨야 테스트가 성립한다."
        )
        return PptxShape(
            left_px=664,
            top_px=top,
            width_px=552,
            height_px=height,
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text=long_text, font_size_pt=18)])
            ],
            autofit_mode="expand_height",
            padding_left_px=24,
            padding_right_px=24,
            padding_top_px=16,
            padding_bottom_px=16,
        )

    def _next_card(self, top: int) -> PptxShape:
        return PptxShape(
            left_px=664,
            top_px=top,
            width_px=552,
            height_px=56,
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="다음 카드", font_size_pt=18)])
            ],
            autofit_mode="expand_height",
        )

    def test_expand_height_overlap_with_next_shape_detected(self) -> None:
        result = lint_slide_spec(
            slide(
                shapes=[self._long_shape(top=184, height=56), self._next_card(top=256)]
            )
        )
        violations = [
            v for v in result.violations if v.rule == "expand-height-collision"
        ]
        assert len(violations) == 1
        assert violations[0].current_value["neighbor_index"] == 1

    def test_no_overflow_no_violation(self) -> None:
        short = PptxShape(
            left_px=664,
            top_px=184,
            width_px=552,
            height_px=96,
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="짧은 텍스트", font_size_pt=18)])
            ],
            autofit_mode="expand_height",
        )
        result = lint_slide_spec(slide(shapes=[short, self._next_card(top=300)]))
        assert not [v for v in result.violations if v.rule == "expand-height-collision"]

    def test_horizontal_neighbor_ignored(self) -> None:
        side_by_side = PptxShape(
            left_px=64,
            top_px=400,
            width_px=552,
            height_px=100,
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="옆 카드", font_size_pt=18)])
            ],
            autofit_mode="expand_height",
        )
        result = lint_slide_spec(
            slide(shapes=[self._long_shape(top=184, height=56), side_by_side])
        )
        assert not [v for v in result.violations if v.rule == "expand-height-collision"]

    def test_shrink_text_mode_skipped(self) -> None:
        long_text = (
            "긴 프롬프트 1개를 전체 복사해 Claude Code 에 붙여넣어 "
            "이 텍스트는 한 줄을 반드시 넘겨야 테스트가 성립한다."
        )
        shrink = PptxShape(
            left_px=664,
            top_px=184,
            width_px=552,
            height_px=56,
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text=long_text, font_size_pt=18)])
            ],
            autofit_mode="shrink_text",
        )
        result = lint_slide_spec(slide(shapes=[shrink, self._next_card(top=256)]))
        assert not [v for v in result.violations if v.rule == "expand-height-collision"]


# ---------------------------------------------------------------------------
# zero-size-shape
# ---------------------------------------------------------------------------


class TestZeroSizeShape:
    def test_zero_height_rectangle_detected(self) -> None:
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=0,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "zero-size-shape"]
        assert len(violations) == 1

    def test_zero_width_rectangle_detected(self) -> None:
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=0,
            height_px=200,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "zero-size-shape"]
        assert len(violations) == 1

    def test_line_with_both_axes_zero_detected(self) -> None:
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=0,
            height_px=0,
            shape_type="line",
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "zero-size-shape"]
        assert len(violations) == 1

    def test_line_with_one_axis_zero_allowed(self) -> None:
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=40,
            height_px=0,
            shape_type="line",
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "zero-size-shape"]

    def test_normal_shape_no_violation(self) -> None:
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=100,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "zero-size-shape"]


# ---------------------------------------------------------------------------
# nowrap-overflow
# ---------------------------------------------------------------------------


class TestNowrapOverflow:
    def _shape_with_text(
        self,
        text: str,
        font: int,
        width_px: float,
        padding_lr: float = 12.0,
        bullet_level: int = -1,
    ) -> PptxShape:
        return PptxShape(
            left_px=64,
            top_px=64,
            width_px=width_px,
            height_px=120,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text=text, font_size_pt=font)],
                    bullet_level=bullet_level,
                )
            ],
            padding_left_px=padding_lr,
            padding_right_px=padding_lr,
        )

    def test_short_text_within_box_no_violation(self) -> None:
        shape = self._shape_with_text("짧은 라벨", font=14, width_px=500)
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "nowrap-overflow"]

    def test_long_text_wraps_naturally_no_violation(self) -> None:
        shape = self._shape_with_text(
            "이 문장은 박스 가용 폭을 한참 넘는 긴 한글 문장이라 nowrap 이 적용되지 않습니다",
            font=14,
            width_px=300,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "nowrap-overflow"]

    def test_borderline_text_within_95_percent_no_violation(self) -> None:
        shape = self._shape_with_text("스킬로 자가개선", font=14, width_px=268)
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "nowrap-overflow"]

    def test_bullet_paragraph_excluded(self) -> None:
        shape = self._shape_with_text(
            "박스 폭에 거의 맞는 한글 라벨",
            font=14,
            width_px=300,
            bullet_level=0,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        assert not [v for v in result.violations if v.rule == "nowrap-overflow"]

    def test_textbox_short_text_no_violation(self) -> None:
        result = lint_slide_spec(
            slide(textboxes=[tb("작은 라벨", font=14, width_px=400)])
        )
        assert not [v for v in result.violations if v.rule == "nowrap-overflow"]

    def test_regression_when_nowrap_gate_admits_overflowing_paragraph(
        self, monkeypatch
    ) -> None:
        """tolerance 0.95 에서는 자연 발생하지 않지만, 회귀가 생기면 lint 가 잡는다."""
        from ppt_generator.interfaces.spec_utils.lint_rules import nowrap_overflow

        monkeypatch.setattr(
            nowrap_overflow,
            "should_apply_nowrap_to_paragraph",
            lambda paragraph, usable_width_px: True,
        )
        shape = self._shape_with_text(
            "스킬로 작업 실행 결과 자가 개선 패턴 누적",
            font=14,
            width_px=268,
        )
        result = lint_slide_spec(slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "nowrap-overflow"]
        assert len(violations) == 1
        assert violations[0].element_type == "shape"


class TestContentLayerFilter:
    """layer 필터 — content layer 만 추출."""

    def _slide(self) -> PptxSlideSpec:
        return PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            textboxes=[tb("제목", font=16)],
            shapes=[],
            grid_plan=None,
        )

    def test_filter_content_only(self) -> None:
        result = lint_slide_spec(self._slide(), layers=["content"])
        assert {v.layer for v in result.violations} == {"content"}


# ---------------------------------------------------------------------------
# 결정 14: PptxShape autofit_mode 기본값
# ---------------------------------------------------------------------------


class TestShapeAutofitDefault:
    """기본값이 'shrink_text' 인지 + LLM output model 도 정렬되어 있는지."""

    def test_pptx_shape_default_is_shrink_text(self) -> None:
        from ppt_generator.interfaces.schemas import PptxShape as _Shape

        s = _Shape(left_px=0, top_px=0, width_px=10, height_px=10)
        assert s.autofit_mode == "shrink_text"

    def test_shape_output_default_is_shrink_text(self) -> None:
        from ppt_generator.interfaces.llm_output_models import ShapeOutput

        s = ShapeOutput(left_px=0, top_px=0, width_px=10, height_px=10)
        assert s.autofit_mode == "shrink_text"


class TestTextOverflowSkipShrinkText:
    """text-overflow rule 이 shrink_text shape 의 height 검사를 스킵하는지."""

    def _long_card(self, autofit_mode: str) -> PptxShape:
        return PptxShape(
            left_px=64,
            top_px=148,
            width_px=520,
            height_px=80,  # 의도적으로 작게
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(
                    runs=[
                        PptxTextRun(
                            text="매우 긴 텍스트 " * 30,
                            font_size_pt=18,
                        )
                    ]
                )
            ],
            autofit_mode=autofit_mode,
        )

    def test_shrink_text_shape_no_overflow_warning(self) -> None:
        spec = PptxSlideSpec(
            background_color="#000",
            slide_type="content",
            shapes=[self._long_card("shrink_text")],
        )
        result = lint_slide_spec(spec)
        overflows = [v for v in result.violations if v.rule == "text-overflow"]
        assert overflows == []

    def test_expand_height_shape_still_flags(self) -> None:
        spec = PptxSlideSpec(
            background_color="#000",
            slide_type="content",
            shapes=[self._long_card("expand_height")],
        )
        result = lint_slide_spec(spec)
        overflows = [
            v
            for v in result.violations
            if v.rule == "text-overflow" and v.element_type == "shape"
        ]
        assert overflows, "expand_height shape 의 text-overflow 는 그대로 검출되어야 함"
