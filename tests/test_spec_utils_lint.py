"""spec_utils lint 테스트.

lint는 디자인 규칙 위반을 감지하되 수정하지 않는다:
- title-font-min: 슬라이드 제목 최소 폰트 검사
- font-range: 폰트 허용 범위(10~44pt) 검사
- canvas-overflow: 캔버스 경계 이탈 검사

기계적 정리(빈 textbox 제거)는 clean_slide_spec으로 수행.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    GridCell,
    GridPlan,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import (
    clean_slide_spec,
    lint_design_spec,
    lint_slide_spec,
)


def _minimal_content_grid_plan() -> GridPlan:
    """content 슬라이드용 최소 grid_plan: header+content 1열 1행."""
    return GridPlan(
        regions=["header", "content"],
        content_columns=1,
        content_rows=1,
        cells=[
            GridCell(id="h1", region="header", row=1, col=1, role="title"),
            GridCell(id="c1", region="content", row=1, col=1, role="body"),
        ],
    )


def _tb(text: str, font: int = 18, **kw) -> PptxTextBox:
    defaults = dict(left_px=64, top_px=64, width_px=500, height_px=50)
    defaults.update(kw)
    return PptxTextBox(
        paragraphs=[PptxParagraph(runs=[PptxTextRun(text=text, font_size_pt=font)])],
        **defaults,
    )


def _slide(
    textboxes: list[PptxTextBox] | None = None,
    shapes: list[PptxShape] | None = None,
    slide_type: str = "content",
    grid_plan: GridPlan | None = None,
) -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=textboxes or [],
        shapes=shapes or [],
        slide_type=slide_type,
        grid_plan=grid_plan,
    )


# ---------------------------------------------------------------------------
# title-font-min 규칙
# ---------------------------------------------------------------------------


class TestTitleFontMin:
    """슬라이드 제목(첫 번째 textbox) 최소 폰트 위반 감지."""

    def test_content_slide_title_below_24pt(self) -> None:
        tb = _tb("제목 텍스트", font=16)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        assert result.has_violations
        v = result.violations[0]
        assert v.rule == "title-font-min"
        assert v.severity == "error"
        assert v.current_value == 16

    def test_title_slide_title_below_36pt(self) -> None:
        tb = _tb("발표 제목", font=24)
        result = lint_slide_spec(_slide(textboxes=[tb], slide_type="title"))
        assert result.has_violations
        violations = [v for v in result.violations if v.rule == "title-font-min"]
        assert len(violations) >= 1
        assert violations[0].current_value == 24

    def test_closing_slide_title_below_36pt(self) -> None:
        tb = _tb("감사합니다", font=20)
        result = lint_slide_spec(_slide(textboxes=[tb], slide_type="closing"))
        assert result.has_violations
        violations = [v for v in result.violations if v.rule == "title-font-min"]
        assert len(violations) >= 1

    def test_title_above_min_no_violation(self) -> None:
        tb = _tb("큰 제목", font=32)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        title_violations = [v for v in result.violations if v.rule == "title-font-min"]
        assert len(title_violations) == 0

    def test_second_textbox_not_checked_for_title(self) -> None:
        title_tb = _tb("제목", font=28)
        body_tb = _tb("본문 작은 글씨", font=12, top_px=150)
        result = lint_slide_spec(_slide(textboxes=[title_tb, body_tb]))
        title_violations = [v for v in result.violations if v.rule == "title-font-min"]
        assert len(title_violations) == 0

    def test_spec_not_modified(self) -> None:
        """lint는 spec을 수정하지 않는다."""
        tb = _tb("제목 텍스트", font=16)
        slide = _slide(textboxes=[tb])
        lint_slide_spec(slide)
        assert slide.textboxes[0].paragraphs[0].runs[0].font_size_pt == 16


# ---------------------------------------------------------------------------
# font-range 규칙
# ---------------------------------------------------------------------------


class TestFontRange:
    """폰트 허용 범위(10~44pt) 위반 감지."""

    def test_font_below_min(self) -> None:
        tb = _tb("너무 작은 폰트", font=8, top_px=200)
        title_tb = _tb("제목", font=24)
        result = lint_slide_spec(_slide(textboxes=[title_tb, tb]))
        range_violations = [v for v in result.violations if v.rule == "font-range"]
        assert len(range_violations) >= 1
        assert range_violations[0].current_value == 8

    def test_font_above_max(self) -> None:
        tb = _tb("너무 큰 폰트", font=50)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        range_violations = [v for v in result.violations if v.rule == "font-range"]
        assert len(range_violations) >= 1
        assert range_violations[0].current_value == 50

    def test_font_in_range_no_violation(self) -> None:
        tb = _tb("정상 폰트", font=24)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        range_violations = [v for v in result.violations if v.rule == "font-range"]
        assert len(range_violations) == 0

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
        result = lint_slide_spec(_slide(shapes=[shape]))
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
        result = lint_slide_spec(_slide(shapes=[shape]))
        range_violations = [v for v in result.violations if v.rule == "font-range"]
        assert len(range_violations) >= 1


# ---------------------------------------------------------------------------
# canvas-overflow 규칙
# ---------------------------------------------------------------------------


class TestCanvasOverflow:
    """캔버스 경계 이탈 감지."""

    def test_textbox_overflow_right(self) -> None:
        tb = _tb("넘침", font=24, left_px=1200, width_px=200)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        overflow_violations = [
            v for v in result.violations if v.rule == "canvas-overflow"
        ]
        assert len(overflow_violations) >= 1

    def test_textbox_overflow_bottom(self) -> None:
        tb = _tb("넘침", font=24, top_px=700, height_px=100)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        overflow_violations = [
            v for v in result.violations if v.rule == "canvas-overflow"
        ]
        assert len(overflow_violations) >= 1

    def test_textbox_negative_left(self) -> None:
        tb = _tb("넘침", font=24, left_px=-10)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        overflow_violations = [
            v for v in result.violations if v.rule == "canvas-overflow"
        ]
        assert len(overflow_violations) >= 1

    def test_textbox_within_canvas_no_violation(self) -> None:
        tb = _tb("정상", font=24, left_px=64, top_px=64, width_px=500, height_px=50)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        overflow_violations = [
            v for v in result.violations if v.rule == "canvas-overflow"
        ]
        assert len(overflow_violations) == 0

    def test_decorative_shape_ignored(self) -> None:
        """장식 요소(텍스트 없는 얇은 shape)는 canvas-overflow 검사 제외."""
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1400,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        overflow_violations = [
            v for v in result.violations if v.rule == "canvas-overflow"
        ]
        assert len(overflow_violations) == 0

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
        result = lint_slide_spec(_slide(shapes=[shape]))
        overflow_violations = [
            v for v in result.violations if v.rule == "canvas-overflow"
        ]
        assert len(overflow_violations) >= 1


# ---------------------------------------------------------------------------
# decorative-no-rounding 규칙
# ---------------------------------------------------------------------------


class TestDecorativeNoRounding:
    """장식 요소(꾸밈선)에 라운딩이 설정되면 위반."""

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
        result = lint_slide_spec(_slide(shapes=[shape]))
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
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [
            v for v in result.violations if v.rule == "decorative-no-rounding"
        ]
        assert len(violations) == 0

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
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [
            v for v in result.violations if v.rule == "decorative-no-rounding"
        ]
        assert len(violations) == 0

    def test_non_decorative_with_rounding_no_violation(self) -> None:
        """텍스트가 있는 일반 shape는 라운딩이 있어도 위반이 아님."""
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
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [
            v for v in result.violations if v.rule == "decorative-no-rounding"
        ]
        assert len(violations) == 0

    def test_thin_vertical_decorative_with_rounding(self) -> None:
        """세로 방향 얇은 장식선도 감지."""
        shape = PptxShape(
            left_px=640,
            top_px=100,
            width_px=3,
            height_px=500,
            shape_type="rectangle",
            fill_color="#CCCCCC",
            corner_radius_px=5,
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [
            v for v in result.violations if v.rule == "decorative-no-rounding"
        ]
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# hidden-decorative-strip 규칙
# ---------------------------------------------------------------------------


class TestHiddenDecorativeStripRule:
    """장식 strip이 더 큰 카드에 가려지는 z-order 결함 검사."""

    def test_strip_behind_card_detected(self) -> None:
        """동일 위치에 시작하는 6px 강조 바가 카드 뒤에 있으면 위반."""
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
        result = lint_slide_spec(_slide(shapes=[bar, card]))
        violations = [
            v for v in result.violations if v.rule == "hidden-decorative-strip"
        ]
        assert len(violations) == 1
        assert violations[0].element_index == 0

    def test_strip_on_top_no_violation(self) -> None:
        """strip이 카드보다 위 z-order면 위반 없음."""
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
        result = lint_slide_spec(_slide(shapes=[card, bar]))
        violations = [
            v for v in result.violations if v.rule == "hidden-decorative-strip"
        ]
        assert len(violations) == 0

    def test_z_index_none_uses_array_order(self) -> None:
        """z_index 미설정 시 배열 인덱스로 판정 — strip이 먼저 나오면 카드에 가려짐."""
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
        result = lint_slide_spec(_slide(shapes=[bar, card]))
        violations = [
            v for v in result.violations if v.rule == "hidden-decorative-strip"
        ]
        assert len(violations) == 1

    def test_strip_not_contained_no_violation(self) -> None:
        """strip이 카드 영역에 포함되지 않으면 무시."""
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
        result = lint_slide_spec(_slide(shapes=[bar, card]))
        violations = [
            v for v in result.violations if v.rule == "hidden-decorative-strip"
        ]
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# spacer-paragraph 규칙
# ---------------------------------------------------------------------------


def _card_with_paragraphs(paragraphs, fill_color="#243447"):
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
    """카드 fill 색상과 동일한 색의 공백 단락이 spacer 안티패턴으로 차단되는지 검증."""

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
        result = lint_slide_spec(_slide(shapes=[card]))
        violations = [v for v in result.violations if v.rule == "spacer-paragraph"]
        assert len(violations) == 1
        assert violations[0].current_value["paragraph_index"] == 1

    def test_real_text_paragraph_no_violation(self) -> None:
        """실제 텍스트가 있는 단락은 위반 아님."""
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
        result = lint_slide_spec(_slide(shapes=[card]))
        assert not [v for v in result.violations if v.rule == "spacer-paragraph"]

    def test_spacer_with_different_color_no_violation(self) -> None:
        """공백이지만 색상이 fill과 다르면 spacer 안티패턴이 아님 (의도적 보임)."""
        card = _card_with_paragraphs(
            [
                PptxParagraph(
                    runs=[PptxTextRun(text=" ", font_size_pt=10, color="#FF0000")]
                ),
            ]
        )
        result = lint_slide_spec(_slide(shapes=[card]))
        assert not [v for v in result.violations if v.rule == "spacer-paragraph"]


# ---------------------------------------------------------------------------
# row-autofit-consistency 규칙
# ---------------------------------------------------------------------------


def _row_card(top_px, autofit_mode, *, idx_label="01"):
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
    """같은 행 카드들의 autofit_mode 충돌 감지."""

    def test_mixed_autofit_modes_detected(self) -> None:
        a = _row_card(148.0, "shrink_text", idx_label="01")
        b = _row_card(148.0, "expand_height", idx_label="02")
        result = lint_slide_spec(_slide(shapes=[a, b]))
        rule_violations = [
            v for v in result.violations if v.rule == "row-autofit-mismatch"
        ]
        # 두 카드 모두 보고
        assert len(rule_violations) == 2

    def test_both_expand_height_in_row_detected(self) -> None:
        a = _row_card(148.0, "expand_height", idx_label="01")
        b = _row_card(148.0, "expand_height", idx_label="02")
        result = lint_slide_spec(_slide(shapes=[a, b]))
        violations = [
            v for v in result.violations if v.rule == "row-expand-height-unsafe"
        ]
        assert len(violations) == 2

    def test_both_shrink_text_in_row_no_violation(self) -> None:
        a = _row_card(148.0, "shrink_text", idx_label="01")
        b = _row_card(148.0, "shrink_text", idx_label="02")
        result = lint_slide_spec(_slide(shapes=[a, b]))
        assert not [
            v
            for v in result.violations
            if v.rule in ("row-autofit-mismatch", "row-expand-height-unsafe")
        ]

    def test_different_rows_not_grouped(self) -> None:
        """top_px가 다르면 같은 행이 아니므로 autofit 차이가 위반이 아님."""
        a = _row_card(148.0, "shrink_text", idx_label="01")
        b = _row_card(322.0, "expand_height", idx_label="02")
        result = lint_slide_spec(_slide(shapes=[a, b]))
        assert not [
            v
            for v in result.violations
            if v.rule in ("row-autofit-mismatch", "row-expand-height-unsafe")
        ]


# ---------------------------------------------------------------------------
# expand-height-collision 규칙
# ---------------------------------------------------------------------------


class TestExpandHeightCollision:
    """autofit_mode='expand_height' shape 가 텍스트 확장 시 아래 이웃과 겹침 감지."""

    def _long_shape(self, top: int, height: int = 56) -> PptxShape:
        """단일 줄 height(56)밖에 없는데 2줄짜리 텍스트가 들어간 step 카드."""
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
        overflowing = self._long_shape(top=184, height=56)
        neighbor = self._next_card(top=256)  # gap=16, but shape expands > 72
        result = lint_slide_spec(_slide(shapes=[overflowing, neighbor]))
        violations = [
            v for v in result.violations if v.rule == "expand-height-collision"
        ]
        assert len(violations) == 1
        assert violations[0].current_value["neighbor_index"] == 1

    def test_no_overflow_no_violation(self) -> None:
        """텍스트가 선언 높이 안에 들어오면 확장 없으므로 위반 없음."""
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
        neighbor = self._next_card(top=300)
        result = lint_slide_spec(_slide(shapes=[short, neighbor]))
        violations = [
            v for v in result.violations if v.rule == "expand-height-collision"
        ]
        assert len(violations) == 0

    def test_horizontal_neighbor_ignored(self) -> None:
        """가로로만 겹치고 아래에 있지 않은 이웃은 대상 아님."""
        overflowing = self._long_shape(top=184, height=56)
        side_by_side = PptxShape(
            left_px=64,  # 가로로 떨어진 컬럼
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
        result = lint_slide_spec(_slide(shapes=[overflowing, side_by_side]))
        violations = [
            v for v in result.violations if v.rule == "expand-height-collision"
        ]
        assert len(violations) == 0

    def test_shrink_text_mode_skipped(self) -> None:
        """autofit_mode='shrink_text' 는 높이가 고정되므로 대상 아님."""
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
        neighbor = self._next_card(top=256)
        result = lint_slide_spec(_slide(shapes=[shrink, neighbor]))
        violations = [
            v for v in result.violations if v.rule == "expand-height-collision"
        ]
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# sibling-gap-minimum 규칙
# ---------------------------------------------------------------------------


class TestSiblingGapMinimum:
    """수평/수직으로 인접한 형제 shape 간 최소 간격 검사."""

    def _card(self, left: int, top: int, w: int = 160, h: int = 120) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=w,
            height_px=h,
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="카드", font_size_pt=18)])
            ],
        )

    def test_horizontal_zero_gap_detected(self) -> None:
        """STEP 1 (right=816) ↔ STEP 2 (left=816) 실제 0px 간격 케이스."""
        a = self._card(left=656, top=200)  # right=816
        b = self._card(left=816, top=200)  # 0px gap
        result = lint_slide_spec(_slide(shapes=[a, b]))
        violations = [v for v in result.violations if v.rule == "sibling-gap-minimum"]
        assert len(violations) == 1
        assert violations[0].current_value["direction"] == "horizontal"

    def test_horizontal_sufficient_gap_no_violation(self) -> None:
        a = self._card(left=656, top=200)  # right=816
        b = self._card(left=830, top=200)  # gap=14
        result = lint_slide_spec(_slide(shapes=[a, b]))
        violations = [v for v in result.violations if v.rule == "sibling-gap-minimum"]
        assert len(violations) == 0

    def test_thin_line_between_cards_still_detected(self) -> None:
        """두 카드 사이에 얇은 화살표가 끼어있어도 카드 간 간격이 없으면 위반."""
        a = self._card(left=656, top=200)  # right=816
        arrow = PptxShape(
            left_px=816,
            top_px=258,
            width_px=40,
            height_px=0,
            shape_type="line",
        )
        b = self._card(left=856, top=200)  # 카드 ↔ 카드 간 40px (화살표가 끼어있음)
        # 카드끼리 직접 비교 시 40px gap 이라 통과해야 하는데, 본 규칙은
        # 실제 밀집 상황을 잡기 위해 line 공간을 1차적으로 무시하지 않음.
        # 따라서 이 케이스는 pass 여야 한다 (40px >= 8px).
        result = lint_slide_spec(_slide(shapes=[a, arrow, b]))
        violations = [v for v in result.violations if v.rule == "sibling-gap-minimum"]
        assert len(violations) == 0

    def test_vertical_zero_gap_detected(self) -> None:
        a = self._card(left=64, top=148, w=500, h=100)  # bottom=248
        b = self._card(left=64, top=248, w=500, h=100)  # 0px gap
        result = lint_slide_spec(_slide(shapes=[a, b]))
        violations = [v for v in result.violations if v.rule == "sibling-gap-minimum"]
        assert len(violations) == 1
        assert violations[0].current_value["direction"] == "vertical"

    def test_non_adjacent_shapes_ignored(self) -> None:
        """x/y 가 서로 떨어진 shape 는 이웃이 아님."""
        a = self._card(left=64, top=148)
        b = self._card(left=600, top=500)
        result = lint_slide_spec(_slide(shapes=[a, b]))
        violations = [v for v in result.violations if v.rule == "sibling-gap-minimum"]
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# zero-size-shape 규칙
# ---------------------------------------------------------------------------


class TestZeroSizeShape:
    """width 또는 height 가 0 인 shape 감지."""

    def test_zero_height_rectangle_detected(self) -> None:
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=0,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
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
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "zero-size-shape"]
        assert len(violations) == 1

    def test_line_with_both_axes_zero_detected(self) -> None:
        """line 도 두 끝점이 모두 0 이면 렌더되지 않음."""
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=0,
            height_px=0,
            shape_type="line",
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "zero-size-shape"]
        assert len(violations) == 1

    def test_line_with_one_axis_zero_allowed(self) -> None:
        """line 은 한 축이 0 이어도 다른 축이 충분하면 정상 렌더."""
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=40,
            height_px=0,
            shape_type="line",
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "zero-size-shape"]
        assert len(violations) == 0

    def test_normal_shape_no_violation(self) -> None:
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=100,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "zero-size-shape"]
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# sibling-grid-uniformity 규칙
# ---------------------------------------------------------------------------


class TestSiblingGridUniformity:
    """같은 row/column 에 3개 이상 있는 카드의 크기 균일성 검사."""

    def _card(self, left: int, top: int, w: int, h: int) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=w,
            height_px=h,
            shape_type="rounded_rectangle",
            fill_color="#1E293B",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="카드", font_size_pt=18)])
            ],
        )

    def test_row_height_mismatch_detected(self) -> None:
        """같은 row 3개 카드 중 하나만 height 다름."""
        a = self._card(left=64, top=200, w=200, h=100)
        b = self._card(left=272, top=200, w=200, h=100)
        c = self._card(left=480, top=200, w=200, h=132)  # 32px 더 높음
        result = lint_slide_spec(_slide(shapes=[a, b, c]))
        violations = [
            v for v in result.violations if v.rule == "sibling-grid-uniformity"
        ]
        assert len(violations) == 1
        assert violations[0].current_value["axis"] == "row"
        assert violations[0].current_value["dimension"] == "height"

    def test_row_uniform_heights_no_violation(self) -> None:
        a = self._card(left=64, top=200, w=200, h=100)
        b = self._card(left=272, top=200, w=200, h=100)
        c = self._card(left=480, top=200, w=200, h=102)  # 2px 차이 — tolerance 이내
        result = lint_slide_spec(_slide(shapes=[a, b, c]))
        violations = [
            v for v in result.violations if v.rule == "sibling-grid-uniformity"
        ]
        assert len(violations) == 0

    def test_column_width_mismatch_detected(self) -> None:
        a = self._card(left=64, top=148, w=400, h=100)
        b = self._card(left=64, top=256, w=400, h=100)
        c = self._card(left=64, top=364, w=360, h=100)  # 40px 더 좁음
        result = lint_slide_spec(_slide(shapes=[a, b, c]))
        violations = [
            v for v in result.violations if v.rule == "sibling-grid-uniformity"
        ]
        assert len(violations) == 1
        assert violations[0].current_value["axis"] == "column"
        assert violations[0].current_value["dimension"] == "width"

    def test_two_cards_not_checked(self) -> None:
        """같은 row 에 카드가 2개만 있으면 검사 대상 아님."""
        a = self._card(left=64, top=524, w=672, h=100)
        b = self._card(left=752, top=524, w=464, h=100)
        result = lint_slide_spec(_slide(shapes=[a, b]))
        violations = [
            v for v in result.violations if v.rule == "sibling-grid-uniformity"
        ]
        assert len(violations) == 0

    def test_non_card_shapes_ignored(self) -> None:
        """fill_color 없는 shape 는 카드로 취급되지 않음."""
        a = self._card(left=64, top=200, w=200, h=100)
        b = self._card(left=272, top=200, w=200, h=100)
        # fill_color 없는 장식 shape — 카드 아님
        deco = PptxShape(
            left_px=480,
            top_px=200,
            width_px=200,
            height_px=140,
            shape_type="rectangle",
        )
        result = lint_slide_spec(_slide(shapes=[a, b, deco]))
        violations = [
            v for v in result.violations if v.rule == "sibling-grid-uniformity"
        ]
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# clean_slide_spec (기계적 정리)
# ---------------------------------------------------------------------------


class TestCleanSpec:
    """기계적 정리: 빈 textbox 제거."""

    def test_empty_textbox_removed(self) -> None:
        empty_tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="")])],
        )
        text_tb = _tb("유효 텍스트", font=18, top_px=200)
        result = clean_slide_spec(_slide(textboxes=[empty_tb, text_tb]))
        assert len(result.textboxes) == 1
        assert result.textboxes[0].paragraphs[0].runs[0].text == "유효 텍스트"

    def test_whitespace_only_textbox_removed(self) -> None:
        ws_tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="   ")])],
        )
        result = clean_slide_spec(_slide(textboxes=[ws_tb]))
        assert len(result.textboxes) == 0

    def test_valid_textbox_preserved(self) -> None:
        tb = _tb("유효 텍스트", font=18)
        result = clean_slide_spec(_slide(textboxes=[tb]))
        assert len(result.textboxes) == 1

    def test_shapes_not_affected(self) -> None:
        shape = PptxShape(
            left_px=64,
            top_px=148,
            width_px=400,
            height_px=200,
            shape_type="rounded_rectangle",
            fill_color="#2E3D50",
            text="카드 본문",
            text_size_pt=12,
        )
        result = clean_slide_spec(_slide(shapes=[shape]))
        assert len(result.shapes) == 1
        assert result.shapes[0].text_size_pt == 12


# ---------------------------------------------------------------------------
# 레이아웃/색상 비개입 확인
# ---------------------------------------------------------------------------


class TestNoModification:
    """lint는 spec을 수정하지 않고, clean_slide_spec은 빈 textbox만 제거한다."""

    def test_position_preserved(self) -> None:
        tb = PptxTextBox(
            left_px=100,
            top_px=100,
            width_px=1000,
            height_px=60,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="제목", font_size_pt=32, bold=True)]
                )
            ],
        )
        result = clean_slide_spec(_slide(textboxes=[tb]))
        assert result.textboxes[0].left_px == 100
        assert result.textboxes[0].top_px == 100

    def test_color_preserved(self) -> None:
        tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="테스트", font_size_pt=18, color="#222222")]
                )
            ],
        )
        result = clean_slide_spec(
            PptxSlideSpec(background_color="#1a1a2e", textboxes=[tb])
        )
        assert result.textboxes[0].paragraphs[0].runs[0].color == "#222222"

    def test_padding_preserved(self) -> None:
        tb = PptxTextBox(
            left_px=64,
            top_px=200,
            width_px=500,
            height_px=100,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])
            ],
            padding_left_px=16,
            padding_right_px=16,
            padding_top_px=12,
            padding_bottom_px=12,
        )
        result = clean_slide_spec(_slide(textboxes=[tb]))
        v = result.textboxes[0]
        assert v.padding_left_px == 16
        assert v.padding_right_px == 16
        assert v.padding_top_px == 12
        assert v.padding_bottom_px == 12

    def test_vertical_alignment_preserved(self) -> None:
        tb = PptxTextBox(
            left_px=64,
            top_px=180,
            width_px=1152,
            height_px=480,
            vertical_alignment="top",
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="짧은 본문", font_size_pt=20)],
                    bullet_level=0,
                )
            ],
        )
        result = clean_slide_spec(_slide(textboxes=[tb]))
        assert result.textboxes[0].vertical_alignment == "top"

    def test_shape_position_preserved(self) -> None:
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1280,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = clean_slide_spec(_slide(shapes=[shape]))
        assert result.shapes[0].left_px == 0
        assert result.shapes[0].height_px == 3
        assert result.shapes[0].width_px == 1280

    def test_shape_gap_preserved(self) -> None:
        s1 = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=50,
            shape_type="rectangle",
            text="A",
            text_size_pt=16,
        )
        s2 = PptxShape(
            left_px=100,
            top_px=153,
            width_px=200,
            height_px=50,
            shape_type="rectangle",
            text="B",
            text_size_pt=16,
        )
        result = clean_slide_spec(
            PptxSlideSpec(background_color="#FFFFFF", shapes=[s1, s2])
        )
        assert result.shapes[0].top_px == s1.top_px
        assert result.shapes[1].top_px == s2.top_px


# ---------------------------------------------------------------------------
# lint_design_spec (전체 슬라이드 lint)
# ---------------------------------------------------------------------------


class TestLintDesignSpec:
    """전체 슬라이드에 대한 lint 결과."""

    def test_all_pass(self) -> None:
        slides = [
            _slide(
                textboxes=[
                    _tb("제목1", font=28, grid_cell="h1"),
                    _tb("body", font=18, top_px=200, grid_cell="c1"),
                ],
                grid_plan=_minimal_content_grid_plan(),
            ),
            _slide(
                textboxes=[
                    _tb("제목2", font=26, grid_cell="h1"),
                    _tb("body", font=18, top_px=200, grid_cell="c1"),
                ],
                grid_plan=_minimal_content_grid_plan(),
            ),
        ]
        result = lint_design_spec(slides)
        assert not result.has_violations
        assert result.total_violations == 0
        assert len(result.cleaned_specs) == 2

    def test_mixed_violations(self) -> None:
        ok_slide = _slide(
            textboxes=[
                _tb("OK 제목", font=28, grid_cell="h1"),
                _tb("body", font=18, top_px=200, grid_cell="c1"),
            ],
            grid_plan=_minimal_content_grid_plan(),
        )
        bad_slide = _slide(
            textboxes=[
                _tb("작은 제목", font=16, grid_cell="h1"),
                _tb("body", font=18, top_px=200, grid_cell="c1"),
            ],
            grid_plan=_minimal_content_grid_plan(),
        )
        slides = [ok_slide, bad_slide]
        result = lint_design_spec(slides)
        assert result.has_violations
        assert result.total_violations >= 1
        assert not result.slides[0].has_violations
        assert result.slides[1].has_violations

    def test_to_dict_format(self) -> None:
        slides = [
            _slide(textboxes=[_tb("작은 제목", font=16)]),
        ]
        result = lint_design_spec(slides)
        d = result.to_dict()
        assert d["total_slides"] == 1
        assert d["total_violations"] >= 1
        assert d["failed_slides"] == 1
        assert d["passed_slides"] == 0
        assert len(d["per_slide"]) == 1
        slide_d = d["per_slide"][0]
        assert slide_d["slide_index"] == 1
        assert slide_d["status"] == "fail"
        assert "violations" in slide_d

    def test_pass_slide_not_in_per_slide(self) -> None:
        """위반 없는 슬라이드는 per_slide에 포함되지 않는다."""
        slides = [
            _slide(
                textboxes=[
                    _tb("OK 제목", font=28, grid_cell="h1"),
                    _tb("body", font=18, top_px=200, grid_cell="c1"),
                ],
                grid_plan=_minimal_content_grid_plan(),
            ),
        ]
        result = lint_design_spec(slides)
        d = result.to_dict()
        assert len(d["per_slide"]) == 0

    def test_cleaned_specs_returned(self) -> None:
        empty_tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="")])],
        )
        text_tb = _tb("유효 텍스트", font=24, top_px=200)
        slides = [_slide(textboxes=[empty_tb, text_tb])]
        result = lint_design_spec(slides)
        assert len(result.cleaned_specs[0].textboxes) == 1


# ---------------------------------------------------------------------------
# nowrap-overflow 규칙 (ADR-0047)
# ---------------------------------------------------------------------------


class TestNowrapOverflow:
    """nowrap 으로 렌더될 paragraph 의 추정 폭이 가용 폭을 초과하는지 검사."""

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
        """박스 폭의 약 50% 인 짧은 한글 텍스트는 위반 없음."""
        shape = self._shape_with_text("짧은 라벨", font=14, width_px=500)
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "nowrap-overflow"]
        assert len(violations) == 0

    def test_long_text_wraps_naturally_no_violation(self) -> None:
        """긴 한글 텍스트는 nowrap 게이트를 통과하지 못해 wrap 됨 → 위반 없음."""
        shape = self._shape_with_text(
            "이 문장은 박스 가용 폭을 한참 넘는 긴 한글 문장이라 nowrap 이 적용되지 않습니다",
            font=14,
            width_px=300,
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "nowrap-overflow"]
        assert len(violations) == 0

    def test_borderline_text_within_95_percent_no_violation(self) -> None:
        """ADR-0047 의 0.95 tolerance 안에 들어오는 텍스트는 nowrap 적용되어도 위반 없음."""
        # 가용 폭 ~ 244px (268 - 12*2). 추정 폭이 230px 정도가 되도록 조정.
        shape = self._shape_with_text("스킬로 자가개선", font=14, width_px=268)
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "nowrap-overflow"]
        assert len(violations) == 0

    def test_bullet_paragraph_excluded(self) -> None:
        """bullet (`<li>`) 는 렌더러가 nowrap 을 적용하지 않으므로 검사 대상 제외."""
        shape = self._shape_with_text(
            "박스 폭에 거의 맞는 한글 라벨",
            font=14,
            width_px=300,
            bullet_level=0,
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "nowrap-overflow"]
        assert len(violations) == 0

    def test_textbox_short_text_no_violation(self) -> None:
        """textbox 의 짧은 텍스트도 가용 폭 이내면 위반 없음."""
        tb = _tb("작은 라벨", font=14, width_px=400)
        result = lint_slide_spec(_slide(textboxes=[tb]))
        violations = [v for v in result.violations if v.rule == "nowrap-overflow"]
        assert len(violations) == 0

    def test_regression_when_nowrap_gate_admits_overflowing_paragraph(
        self, monkeypatch
    ) -> None:
        """nowrap 게이트가 가용 폭을 초과하는 paragraph 를 허용하는 경우 lint 가 잡는다.

        tolerance 0.95 에서는 자연 발생하지 않지만, 향후 tolerance 가 다시 느슨해지거나
        `should_apply_nowrap_to_paragraph` 구현이 바뀌어 회귀가 생기면 이 lint 가
        감지해야 한다. 게이트를 강제로 True 로 패치하여 시나리오를 재현한다.
        """
        from ppt_generator.interfaces.spec_utils.lint_rules import nowrap_overflow

        monkeypatch.setattr(
            nowrap_overflow,
            "should_apply_nowrap_to_paragraph",
            lambda paragraph, usable_width_px: True,
        )
        # 가용 폭 ~244px (268-24), 추정 폭이 가용 폭을 초과하도록 충분히 긴 한글.
        shape = self._shape_with_text(
            "스킬로 작업 실행 결과 자가 개선 패턴 누적",
            font=14,
            width_px=268,
        )
        result = lint_slide_spec(_slide(shapes=[shape]))
        violations = [v for v in result.violations if v.rule == "nowrap-overflow"]
        assert len(violations) == 1
        assert violations[0].element_type == "shape"


# ---------------------------------------------------------------------------
# arrow-endpoint-attachment 규칙 (ADR-0048)
# ---------------------------------------------------------------------------


class TestArrowEndpointAttachment:
    """화살표 끝점이 박스 변에 부착되어 있는지 검사."""

    def _box(
        self, left: float, top: float, width: float = 100, height: float = 60
    ) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="박스", font_size_pt=16)])
            ],
        )

    def _arrow(
        self,
        left: float,
        top: float,
        width: float,
        height: float,
        end_arrow: bool = True,
        start_arrow: bool = False,
    ) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            shape_type="line",
            border_color="#FF9900",
            border_width_pt=1.5,
            end_arrow=end_arrow,
            start_arrow=start_arrow,
        )

    def test_arrow_end_touches_box_edge_passes(self) -> None:
        """화살표 end 가 박스 left edge 정확히 닿음."""
        # 박스: (200, 100) ~ (300, 160). 화살표 end = (200, 130) ← 박스 left edge mid
        box = self._box(200, 100)
        arrow = self._arrow(150, 130, 50, 0)  # end=(200,130)
        result = lint_slide_spec(_slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 0

    def test_arrow_end_within_tolerance_passes(self) -> None:
        """화살표 end 가 박스에서 5px 떨어짐 (8px 이내)."""
        box = self._box(200, 100)
        arrow = self._arrow(150, 130, 45, 0)  # end=(195,130), 5px 떨어짐
        result = lint_slide_spec(_slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 0

    def test_arrow_end_floating_fails(self) -> None:
        """화살표 end 가 박스에서 30px 떨어져 허공에서 끝남."""
        box = self._box(200, 100)
        arrow = self._arrow(50, 130, 100, 0)  # end=(150,130), 50px 떨어짐
        result = lint_slide_spec(_slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 1
        assert v[0].current_value["endpoint"] == "end"

    def test_arrow_start_floating_fails(self) -> None:
        """start_arrow=True 일 때 line 시작점이 박스에서 멀면 fail."""
        box = self._box(200, 100)
        arrow = self._arrow(
            50, 130, 100, 0, end_arrow=False, start_arrow=True
        )  # start=(50,130) 떠있음
        result = lint_slide_spec(_slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 1
        assert v[0].current_value["endpoint"] == "start"

    def test_line_without_arrowhead_excluded(self) -> None:
        """end_arrow/start_arrow 모두 False 인 line 은 검사 제외."""
        box = self._box(200, 100)
        arrow = self._arrow(50, 130, 100, 0, end_arrow=False, start_arrow=False)
        result = lint_slide_spec(_slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 0


# ---------------------------------------------------------------------------
# label-orphan 규칙 (ADR-0048)
# ---------------------------------------------------------------------------


class TestLabelOrphan:
    """짧은 라벨 textbox 가 어떤 박스에도 부착되지 않고 떠있는지 검사."""

    def _label_tb(
        self,
        text: str,
        left: float,
        top: float,
        font: int = 12,
        width: float = 36,
        height: float = 22,
    ) -> PptxTextBox:
        return PptxTextBox(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text=text, font_size_pt=font)])
            ],
        )

    def _box(
        self, left: float, top: float, width: float = 100, height: float = 60
    ) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="박스", font_size_pt=16)])
            ],
        )

    def test_label_near_box_passes(self) -> None:
        """라벨이 박스 옆 10px 거리 → pass."""
        box = self._box(200, 100)  # (200,100)~(300,160)
        label = self._label_tb("Yes", left=310, top=120)  # 박스 right edge에서 10px
        result = lint_slide_spec(_slide(textboxes=[label], shapes=[box]))
        v = [x for x in result.violations if x.rule == "label-orphan"]
        assert len(v) == 0

    def test_label_floating_far_fails(self) -> None:
        """라벨이 박스에서 100px 이상 떨어짐 → fail."""
        box = self._box(200, 100)
        label = self._label_tb("Yes", left=600, top=400)
        result = lint_slide_spec(_slide(textboxes=[label], shapes=[box]))
        v = [x for x in result.violations if x.rule == "label-orphan"]
        assert len(v) == 1
        assert v[0].element_type == "textbox"

    def test_long_text_excluded(self) -> None:
        """글자수 12 초과 → 라벨 게이트 통과 못 함, 검사 제외."""
        box = self._box(200, 100)
        long_tb = self._label_tb(
            "이건 본문 텍스트라서 라벨이 아니다", left=600, top=400, font=14, width=300
        )
        result = lint_slide_spec(_slide(textboxes=[long_tb], shapes=[box]))
        v = [x for x in result.violations if x.rule == "label-orphan"]
        assert len(v) == 0

    def test_large_font_excluded(self) -> None:
        """폰트 14pt 초과 → 라벨 게이트 통과 못 함."""
        box = self._box(200, 100)
        big_tb = self._label_tb("Yes", left=600, top=400, font=18)
        result = lint_slide_spec(_slide(textboxes=[big_tb], shapes=[box]))
        v = [x for x in result.violations if x.rule == "label-orphan"]
        assert len(v) == 0

    def test_header_region_excluded(self) -> None:
        """제목 (header region) 은 검사 제외."""
        plan = GridPlan(
            regions=["header", "content"],
            content_columns=1,
            content_rows=1,
            cells=[
                GridCell(id="h1", region="header", row=1, col=1, role="title"),
                GridCell(id="c1", region="content", row=1, col=1, role="body"),
            ],
        )
        title_tb = PptxTextBox(
            left_px=64,
            top_px=72,
            width_px=1152,
            height_px=24,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="짧은제목", font_size_pt=12)])
            ],
            grid_cell="h1",
        )
        box = self._box(64, 200, width=400, height=200)
        # box 와 title_tb 거리 > 32px 이지만 header 라서 제외
        result = lint_slide_spec(
            _slide(textboxes=[title_tb], shapes=[box], grid_plan=plan)
        )
        v = [x for x in result.violations if x.rule == "label-orphan"]
        assert len(v) == 0
