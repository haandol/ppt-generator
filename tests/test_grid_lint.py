"""ADR-0044 grid-first design spec lint 규칙 테스트.

신규/변경 규칙:
- grid-plan-required: content 슬라이드에 grid_plan 필수 (error)
- grid-cell-coverage: 미사용/미선언/중복 cell (error/warning)
- region-stacking: footer 사용 시 content cell 침범 (error)
- grid-cell-uniformity: grid_plan 인지 모드의 row/column 균일성 (warning)
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
from ppt_generator.interfaces.spec_utils import lint_slide_spec


def _make_text_run(text: str, font: int = 20) -> PptxTextRun:
    return PptxTextRun(text=text, font_size_pt=font, bold=True)


def _title_tb(grid_cell: str | None = "h1") -> PptxTextBox:
    return PptxTextBox(
        left_px=64,
        top_px=72,
        width_px=1152,
        height_px=48,
        paragraphs=[PptxParagraph(runs=[_make_text_run("Title", font=32)])],
        vertical_alignment="middle",
        grid_cell=grid_cell,
    )


def _card(
    left: int,
    top: int,
    w: int,
    h: int,
    grid_cell: str | None = "c1",
    text: str = "Card",
) -> PptxShape:
    return PptxShape(
        left_px=left,
        top_px=top,
        width_px=w,
        height_px=h,
        shape_type="rounded_rectangle",
        fill_color="#334155",
        paragraphs=[PptxParagraph(runs=[_make_text_run(text)])],
        grid_cell=grid_cell,
    )


def _three_cell_row_plan() -> GridPlan:
    return GridPlan(
        regions=["header", "content"],
        content_columns=3,
        content_rows=1,
        cells=[
            GridCell(id="h1", region="header", row=1, col=1, role="title"),
            GridCell(id="c1", region="content", row=1, col=1, role="card1"),
            GridCell(id="c2", region="content", row=1, col=2, role="card2"),
            GridCell(id="c3", region="content", row=1, col=3, role="card3"),
        ],
    )


# ---------------------------------------------------------------------------
# grid-plan-required
# ---------------------------------------------------------------------------


class TestGridPlanRequired:
    def test_content_slide_missing_grid_plan_error(self) -> None:
        spec = PptxSlideSpec(
            slide_type="content",
            textboxes=[_title_tb(grid_cell=None)],
            shapes=[],
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-plan-required"]
        assert len(violations) == 1
        assert violations[0].severity == "error"

    def test_title_slide_no_grid_plan_ok(self) -> None:
        spec = PptxSlideSpec(slide_type="title", textboxes=[_title_tb(grid_cell=None)])
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-plan-required"]
        assert len(violations) == 0

    def test_closing_slide_no_grid_plan_ok(self) -> None:
        spec = PptxSlideSpec(
            slide_type="closing", textboxes=[_title_tb(grid_cell=None)]
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-plan-required"]
        assert len(violations) == 0

    def test_missing_content_region_error(self) -> None:
        plan = GridPlan(
            regions=["header"],
            content_columns=1,
            content_rows=1,
            cells=[GridCell(id="h1", region="header", row=1, col=1)],
        )
        spec = PptxSlideSpec(
            slide_type="content",
            textboxes=[_title_tb()],
            grid_plan=plan,
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-plan-required"]
        assert any("'content'" in v.message for v in violations)

    def test_columns_out_of_range_error(self) -> None:
        plan = GridPlan(
            regions=["content"],
            content_columns=5,
            content_rows=1,
            cells=[GridCell(id="c1", region="content", row=1, col=1)],
        )
        spec = PptxSlideSpec(slide_type="content", grid_plan=plan)
        result = lint_slide_spec(spec)
        violations = [
            v
            for v in result.violations
            if v.rule == "grid-plan-required" and "content_columns" in v.message
        ]
        assert len(violations) == 1

    def test_cell_region_not_declared_error(self) -> None:
        plan = GridPlan(
            regions=["content"],
            content_columns=1,
            content_rows=1,
            cells=[
                GridCell(id="c1", region="content", row=1, col=1),
                GridCell(id="f1", region="footer", row=1, col=1),
            ],
        )
        spec = PptxSlideSpec(slide_type="content", grid_plan=plan)
        result = lint_slide_spec(spec)
        violations = [
            v
            for v in result.violations
            if v.rule == "grid-plan-required" and "f1" in v.message
        ]
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# grid-cell-coverage
# ---------------------------------------------------------------------------


class TestGridCellCoverage:
    def test_textbox_missing_grid_cell_warning(self) -> None:
        plan = _three_cell_row_plan()
        title = _title_tb(grid_cell=None)
        cards = [
            _card(64, 148, 362, 472, grid_cell="c1"),
            _card(458, 148, 362, 472, grid_cell="c2"),
            _card(852, 148, 362, 472, grid_cell="c3"),
        ]
        spec = PptxSlideSpec(
            slide_type="content", textboxes=[title], shapes=cards, grid_plan=plan
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-cell-coverage"]
        assert any(
            v.element_type == "textbox" and "grid_cell" in v.message for v in violations
        )

    def test_unknown_cell_id_error(self) -> None:
        plan = _three_cell_row_plan()
        title = _title_tb(grid_cell="h1")
        cards = [
            _card(64, 148, 362, 472, grid_cell="c1"),
            _card(458, 148, 362, 472, grid_cell="c2"),
            _card(852, 148, 362, 472, grid_cell="cX"),  # 미선언
        ]
        spec = PptxSlideSpec(
            slide_type="content", textboxes=[title], shapes=cards, grid_plan=plan
        )
        result = lint_slide_spec(spec)
        violations = [
            v
            for v in result.violations
            if v.rule == "grid-cell-coverage" and "cX" in v.message
        ]
        assert any(v.severity == "error" for v in violations)

    def test_empty_cell_warning(self) -> None:
        plan = _three_cell_row_plan()
        title = _title_tb(grid_cell="h1")
        # c3 매핑 누락
        cards = [
            _card(64, 148, 362, 472, grid_cell="c1"),
            _card(458, 148, 362, 472, grid_cell="c2"),
        ]
        spec = PptxSlideSpec(
            slide_type="content", textboxes=[title], shapes=cards, grid_plan=plan
        )
        result = lint_slide_spec(spec)
        violations = [
            v
            for v in result.violations
            if v.rule == "grid-cell-coverage" and "c3" in str(v.current_value)
        ]
        assert len(violations) == 1

    def test_decorative_line_grid_cell_null_ok(self) -> None:
        plan = _three_cell_row_plan()
        title = _title_tb(grid_cell="h1")
        cards = [
            _card(64, 148, 362, 472, grid_cell="c1"),
            _card(458, 148, 362, 472, grid_cell="c2"),
            _card(852, 148, 362, 472, grid_cell="c3"),
        ]
        # 화살표(얇은 line, 텍스트 없음): grid_cell=None 허용
        arrow = PptxShape(
            left_px=420,
            top_px=380,
            width_px=40,
            height_px=2,
            shape_type="line",
            border_color="#3B82F6",
            border_width_pt=2,
            end_arrow=True,
            grid_cell=None,
        )
        spec = PptxSlideSpec(
            slide_type="content",
            textboxes=[title],
            shapes=cards + [arrow],
            grid_plan=plan,
        )
        result = lint_slide_spec(spec)
        violations = [
            v
            for v in result.violations
            if v.rule == "grid-cell-coverage" and v.element_type == "shape"
        ]
        # arrow 가 None 이라고 warning 나면 안 됨
        assert all("[3]" not in v.message for v in violations)


# ---------------------------------------------------------------------------
# region-stacking
# ---------------------------------------------------------------------------


class TestRegionStacking:
    def test_content_extends_into_footer_error(self) -> None:
        plan = GridPlan(
            regions=["header", "content", "footer"],
            content_columns=1,
            content_rows=1,
            cells=[
                GridCell(id="h1", region="header", row=1, col=1),
                GridCell(id="c1", region="content", row=1, col=1),
                GridCell(id="f1", region="footer", row=1, col=1),
            ],
        )
        title = _title_tb(grid_cell="h1")
        # c1 의 bottom = 148 + 540 = 688, footer top=664, 한계 648
        big_card = _card(64, 148, 1152, 540, grid_cell="c1")
        footer_tb = PptxTextBox(
            left_px=64,
            top_px=664,
            width_px=1152,
            height_px=24,
            paragraphs=[PptxParagraph(runs=[_make_text_run("source", font=12)])],
            grid_cell="f1",
        )
        spec = PptxSlideSpec(
            slide_type="content",
            textboxes=[title, footer_tb],
            shapes=[big_card],
            grid_plan=plan,
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "region-stacking"]
        assert any(v.severity == "error" for v in violations)

    def test_no_footer_no_violation(self) -> None:
        plan = GridPlan(
            regions=["header", "content"],
            content_columns=1,
            content_rows=1,
            cells=[
                GridCell(id="h1", region="header", row=1, col=1),
                GridCell(id="c1", region="content", row=1, col=1),
            ],
        )
        title = _title_tb(grid_cell="h1")
        # footer 없으면 content 가 688 까지 사용해도 region-stacking 위반 아님
        big_card = _card(64, 148, 1152, 540, grid_cell="c1")
        spec = PptxSlideSpec(
            slide_type="content",
            textboxes=[title],
            shapes=[big_card],
            grid_plan=plan,
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "region-stacking"]
        assert len(violations) == 0

    def test_content_within_footer_top_no_violation(self) -> None:
        plan = GridPlan(
            regions=["header", "content", "footer"],
            content_columns=1,
            content_rows=1,
            cells=[
                GridCell(id="h1", region="header", row=1, col=1),
                GridCell(id="c1", region="content", row=1, col=1),
                GridCell(id="f1", region="footer", row=1, col=1),
            ],
        )
        title = _title_tb(grid_cell="h1")
        # bottom = 148 + 480 = 628, 한계 648 이내
        ok_card = _card(64, 148, 1152, 480, grid_cell="c1")
        footer_tb = PptxTextBox(
            left_px=64,
            top_px=664,
            width_px=1152,
            height_px=24,
            paragraphs=[PptxParagraph(runs=[_make_text_run("source", font=12)])],
            grid_cell="f1",
        )
        spec = PptxSlideSpec(
            slide_type="content",
            textboxes=[title, footer_tb],
            shapes=[ok_card],
            grid_plan=plan,
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "region-stacking"]
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# grid-cell-uniformity (grid_plan 인지 모드)
# ---------------------------------------------------------------------------


class TestGridCellUniformity:
    def test_row_height_mismatch_with_grid_plan(self) -> None:
        plan = _three_cell_row_plan()
        title = _title_tb(grid_cell="h1")
        cards = [
            _card(64, 148, 362, 472, grid_cell="c1"),
            _card(458, 148, 362, 472, grid_cell="c2"),
            _card(852, 148, 362, 520, grid_cell="c3"),  # 48px 더 큼
        ]
        spec = PptxSlideSpec(
            slide_type="content", textboxes=[title], shapes=cards, grid_plan=plan
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-cell-uniformity"]
        assert len(violations) == 1
        assert violations[0].current_value["axis"] == "row"

    def test_row_uniform_no_violation(self) -> None:
        plan = _three_cell_row_plan()
        title = _title_tb(grid_cell="h1")
        cards = [
            _card(64, 148, 362, 472, grid_cell="c1"),
            _card(458, 148, 362, 472, grid_cell="c2"),
            _card(852, 148, 362, 474, grid_cell="c3"),  # 2px 차이 — 허용
        ]
        spec = PptxSlideSpec(
            slide_type="content", textboxes=[title], shapes=cards, grid_plan=plan
        )
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-cell-uniformity"]
        assert len(violations) == 0

    def test_row_span_difference_excluded(self) -> None:
        """row_span 이 다른 cell 끼리는 같은 row 비교 대상이 아니다."""
        plan = GridPlan(
            regions=["content"],
            content_columns=2,
            content_rows=2,
            cells=[
                GridCell(id="c1", region="content", row=1, col=1, row_span=2),
                GridCell(id="c2", region="content", row=1, col=2, row_span=1),
                GridCell(id="c3", region="content", row=2, col=2, row_span=1),
            ],
        )
        # c1 은 큰 cell, c2/c3 는 작음. row_span 다르므로 c1 vs c2 비교 안 함.
        cards = [
            _card(64, 148, 552, 508, grid_cell="c1"),  # 두 row 차지
            _card(664, 148, 552, 240, grid_cell="c2"),
            _card(664, 416, 552, 240, grid_cell="c3"),
        ]
        spec = PptxSlideSpec(slide_type="content", shapes=cards, grid_plan=plan)
        result = lint_slide_spec(spec)
        violations = [v for v in result.violations if v.rule == "grid-cell-uniformity"]
        assert len(violations) == 0

    def test_legacy_mode_when_grid_plan_absent(self) -> None:
        """grid_plan 없으면 기존 sibling-grid-uniformity legacy 검사 동작."""
        cards = [
            _card(64, 200, 200, 100, grid_cell=None),
            _card(272, 200, 200, 100, grid_cell=None),
            _card(480, 200, 200, 132, grid_cell=None),
        ]
        spec = PptxSlideSpec(slide_type="content", shapes=cards)
        result = lint_slide_spec(spec)
        legacy = [v for v in result.violations if v.rule == "sibling-grid-uniformity"]
        # legacy 모드는 grid_plan 부재 시에만 동작
        # content 슬라이드인데 grid_plan 누락 → grid-plan-required 도 함께 발생
        assert len(legacy) == 1
