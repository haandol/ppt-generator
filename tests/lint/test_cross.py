"""Cross layer lint 테스트.

요소 간 관계 / 계층 간 link 위반:
- arrow-endpoint-attachment, label-orphan,
  decoration-shape-overlap, textbox-shape-intrusion,
  textbox-textbox-overlap, sibling-gap-minimum, sibling-grid-uniformity
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    GridCell,
    GridPlan,
    PptxParagraph,
    PptxShape,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from lint._lint_helpers import slide


# ---------------------------------------------------------------------------
# sibling-gap-minimum
# ---------------------------------------------------------------------------


class TestSiblingGapMinimum:
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
        a = self._card(left=656, top=200)
        b = self._card(left=816, top=200)
        result = lint_slide_spec(slide(shapes=[a, b]))
        violations = [v for v in result.violations if v.rule == "sibling-gap-minimum"]
        assert len(violations) == 1
        assert violations[0].current_value["direction"] == "horizontal"

    def test_horizontal_sufficient_gap_no_violation(self) -> None:
        a = self._card(left=656, top=200)
        b = self._card(left=830, top=200)
        result = lint_slide_spec(slide(shapes=[a, b]))
        assert not [v for v in result.violations if v.rule == "sibling-gap-minimum"]

    def test_thin_line_between_cards_still_detected(self) -> None:
        a = self._card(left=656, top=200)
        arrow = PptxShape(
            left_px=816,
            top_px=258,
            width_px=40,
            height_px=0,
            shape_type="line",
        )
        b = self._card(left=856, top=200)
        result = lint_slide_spec(slide(shapes=[a, arrow, b]))
        assert not [v for v in result.violations if v.rule == "sibling-gap-minimum"]

    def test_vertical_zero_gap_detected(self) -> None:
        a = self._card(left=64, top=148, w=500, h=100)
        b = self._card(left=64, top=248, w=500, h=100)
        result = lint_slide_spec(slide(shapes=[a, b]))
        violations = [v for v in result.violations if v.rule == "sibling-gap-minimum"]
        assert len(violations) == 1
        assert violations[0].current_value["direction"] == "vertical"

    def test_non_adjacent_shapes_ignored(self) -> None:
        a = self._card(left=64, top=148)
        b = self._card(left=600, top=500)
        result = lint_slide_spec(slide(shapes=[a, b]))
        assert not [v for v in result.violations if v.rule == "sibling-gap-minimum"]


# ---------------------------------------------------------------------------
# sibling-grid-uniformity
# ---------------------------------------------------------------------------


class TestSiblingGridUniformity:
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
        a = self._card(left=64, top=200, w=200, h=100)
        b = self._card(left=272, top=200, w=200, h=100)
        c = self._card(left=480, top=200, w=200, h=132)
        result = lint_slide_spec(slide(shapes=[a, b, c]))
        violations = [
            v for v in result.violations if v.rule == "sibling-grid-uniformity"
        ]
        assert len(violations) == 1
        assert violations[0].current_value["axis"] == "row"
        assert violations[0].current_value["dimension"] == "height"

    def test_row_uniform_heights_no_violation(self) -> None:
        a = self._card(left=64, top=200, w=200, h=100)
        b = self._card(left=272, top=200, w=200, h=100)
        c = self._card(left=480, top=200, w=200, h=102)
        result = lint_slide_spec(slide(shapes=[a, b, c]))
        assert not [v for v in result.violations if v.rule == "sibling-grid-uniformity"]

    def test_column_width_mismatch_detected(self) -> None:
        a = self._card(left=64, top=148, w=400, h=100)
        b = self._card(left=64, top=256, w=400, h=100)
        c = self._card(left=64, top=364, w=360, h=100)
        result = lint_slide_spec(slide(shapes=[a, b, c]))
        violations = [
            v for v in result.violations if v.rule == "sibling-grid-uniformity"
        ]
        assert len(violations) == 1
        assert violations[0].current_value["axis"] == "column"
        assert violations[0].current_value["dimension"] == "width"

    def test_two_cards_not_checked(self) -> None:
        a = self._card(left=64, top=524, w=672, h=100)
        b = self._card(left=752, top=524, w=464, h=100)
        result = lint_slide_spec(slide(shapes=[a, b]))
        assert not [v for v in result.violations if v.rule == "sibling-grid-uniformity"]

    def test_non_card_shapes_ignored(self) -> None:
        a = self._card(left=64, top=200, w=200, h=100)
        b = self._card(left=272, top=200, w=200, h=100)
        deco = PptxShape(
            left_px=480,
            top_px=200,
            width_px=200,
            height_px=140,
            shape_type="rectangle",
        )
        result = lint_slide_spec(slide(shapes=[a, b, deco]))
        assert not [v for v in result.violations if v.rule == "sibling-grid-uniformity"]


# ---------------------------------------------------------------------------
# arrow-endpoint-attachment
# ---------------------------------------------------------------------------


class TestArrowEndpointAttachment:
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
        box = self._box(200, 100)
        arrow = self._arrow(150, 130, 50, 0)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        assert not [
            x for x in result.violations if x.rule == "arrow-endpoint-attachment"
        ]

    def test_arrow_end_within_tolerance_passes(self) -> None:
        box = self._box(200, 100)
        arrow = self._arrow(150, 130, 45, 0)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        assert not [
            x for x in result.violations if x.rule == "arrow-endpoint-attachment"
        ]

    def test_arrow_end_inside_box_is_penetration_error(self) -> None:
        box = self._box(200, 100)
        arrow = self._arrow(150, 130, 58, 0)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        violations = [
            x for x in result.violations if x.rule == "arrow-endpoint-penetration"
        ]
        assert len(violations) == 1
        assert violations[0].severity == "error"
        assert violations[0].current_value["penetration_px"] == 8

    def test_arrow_end_floating_fails(self) -> None:
        box = self._box(200, 100)
        arrow = self._arrow(50, 130, 100, 0)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 1
        assert v[0].current_value["endpoint"] == "end"

    def test_arrow_start_floating_fails(self) -> None:
        box = self._box(200, 100)
        arrow = self._arrow(50, 130, 100, 0, end_arrow=False, start_arrow=True)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 1
        assert v[0].current_value["endpoint"] == "start"

    def test_line_without_arrowhead_excluded(self) -> None:
        box = self._box(200, 100)
        arrow = self._arrow(50, 130, 100, 0, end_arrow=False, start_arrow=False)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        assert not [
            x for x in result.violations if x.rule == "arrow-endpoint-attachment"
        ]

    # 음수 height(↗ flipV) — 끝점 flip 을 반영해야 렌더 위치와 일치한다.
    # 이 케이스들은 flip 미반영 시 |h|px 어긋나 오판한다.

    def test_negative_height_end_touches_box_passes(self) -> None:
        # 박스 top edge y=300, x[200..300]. ↗ 화살표 end(flip)=(250,300) 으로 부착.
        # flip 미반영(버그) 시 end=(250,220) 으로 80px 떠 잘못된 위반이 떴었다.
        box = self._box(200, 300)
        arrow = self._arrow(200, 300, 50, -80, end_arrow=True)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        assert not [
            x for x in result.violations if x.rule == "arrow-endpoint-attachment"
        ]

    def test_negative_height_end_floating_fails(self) -> None:
        # flip 반영 end=(250,300) 이 어떤 박스에도 안 닿는 진짜 floating 케이스.
        box = self._box(600, 100)
        arrow = self._arrow(200, 300, 50, -80, end_arrow=True)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 1
        assert v[0].current_value["endpoint"] == "end"

    def test_negative_height_start_touches_box_passes(self) -> None:
        # ↗ 화살표 start(flip)=(left, top+|h|)=(200,380). 박스 top edge y=380 에 부착.
        box = self._box(150, 380)
        arrow = self._arrow(200, 300, 50, -80, end_arrow=False, start_arrow=True)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        assert not [
            x for x in result.violations if x.rule == "arrow-endpoint-attachment"
        ]

    # 음수 width(↙/↖ flipH) — 부호가 x축 끝점 방향을 뒤집는다.
    # bbox 최소 모서리는 left 그대로이고, end 는 부호에 따라 대각으로 간다.

    def test_negative_width_end_touches_box_passes(self) -> None:
        # ↖ 화살표: w<0 이므로 end 는 x 최소쪽(left=200), h<0 이므로 y 최소쪽(top=300).
        # 박스 우하단 근처(x=200,y=300)에 end 부착.
        box = self._box(120, 300)  # x[120..220], top y=300 → end (200,300) 부착
        arrow = self._arrow(200, 300, -60, -80, end_arrow=True)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        assert not [
            x for x in result.violations if x.rule == "arrow-endpoint-attachment"
        ]

    def test_negative_width_end_floating_fails(self) -> None:
        # end=(200,300) 이 어떤 박스에도 안 닿는 진짜 floating.
        box = self._box(600, 100)
        arrow = self._arrow(200, 300, -60, -80, end_arrow=True)
        result = lint_slide_spec(slide(shapes=[box, arrow]))
        v = [x for x in result.violations if x.rule == "arrow-endpoint-attachment"]
        assert len(v) == 1
        assert v[0].current_value["endpoint"] == "end"


# ---------------------------------------------------------------------------
# label-orphan
# ---------------------------------------------------------------------------


class TestLabelOrphan:
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
        box = self._box(200, 100)
        label = self._label_tb("Yes", left=310, top=120)
        result = lint_slide_spec(slide(textboxes=[label], shapes=[box]))
        assert not [x for x in result.violations if x.rule == "label-orphan"]

    def test_label_floating_far_fails(self) -> None:
        box = self._box(200, 100)
        label = self._label_tb("Yes", left=600, top=400)
        result = lint_slide_spec(slide(textboxes=[label], shapes=[box]))
        v = [x for x in result.violations if x.rule == "label-orphan"]
        assert len(v) == 1
        assert v[0].element_type == "textbox"

    def test_long_text_excluded(self) -> None:
        box = self._box(200, 100)
        long_tb = self._label_tb(
            "이건 본문 텍스트라서 라벨이 아니다", left=600, top=400, font=14, width=300
        )
        result = lint_slide_spec(slide(textboxes=[long_tb], shapes=[box]))
        assert not [x for x in result.violations if x.rule == "label-orphan"]

    def test_large_font_excluded(self) -> None:
        box = self._box(200, 100)
        big_tb = self._label_tb("Yes", left=600, top=400, font=18)
        result = lint_slide_spec(slide(textboxes=[big_tb], shapes=[box]))
        assert not [x for x in result.violations if x.rule == "label-orphan"]

    def test_header_region_excluded(self) -> None:
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
        result = lint_slide_spec(
            slide(textboxes=[title_tb], shapes=[box], grid_plan=plan)
        )
        assert not [x for x in result.violations if x.rule == "label-orphan"]


# ---------------------------------------------------------------------------
# textbox-shape-intrusion
# ---------------------------------------------------------------------------


class TestTextboxShapeIntrusion:
    def _label_tb(
        self,
        text: str,
        left: float,
        top: float,
        font: int = 12,
        width: float = 140,
        height: float = 22,
        grid_cell: str | None = None,
    ) -> PptxTextBox:
        return PptxTextBox(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text=text, font_size_pt=font)])
            ],
            grid_cell=grid_cell,
        )

    def _card(
        self,
        left: float,
        top: float,
        width: float = 260,
        height: float = 56,
        text: str = "web_search()",
        dash_style: str | None = None,
        fill_color: str | None = "#243447",
        grid_cell: str | None = None,
    ) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            shape_type="rounded_rectangle",
            fill_color=fill_color,
            dash_style=dash_style,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text=text, font_size_pt=16)])],
            grid_cell=grid_cell,
        )

    def test_label_intruding_card_detected(self) -> None:
        card = self._card(880, 265, width=268, height=50)
        label = self._label_tb("직접 호출 불가 ✗", left=820, top=282)
        result = lint_slide_spec(slide(textboxes=[label], shapes=[card]))
        v = [x for x in result.violations if x.rule == "textbox-shape-intrusion"]
        assert len(v) == 1
        assert v[0].element_type == "textbox"

    def test_label_outside_card_passes(self) -> None:
        card = self._card(880, 265)
        label = self._label_tb("라벨", left=700, top=270)
        result = lint_slide_spec(slide(textboxes=[label], shapes=[card]))
        assert not [x for x in result.violations if x.rule == "textbox-shape-intrusion"]

    def test_dashed_container_child_excluded(self) -> None:
        container = self._card(
            880,
            220,
            width=300,
            height=380,
            text="",
            dash_style="dash",
            fill_color=None,
        )
        label = self._label_tb("애플리케이션 영역", left=900, top=230, width=260)
        result = lint_slide_spec(slide(textboxes=[label], shapes=[container]))
        assert not [x for x in result.violations if x.rule == "textbox-shape-intrusion"]

    def test_minor_overlap_below_ratio_passes(self) -> None:
        card = self._card(880, 265, width=268, height=50)
        label = self._label_tb("토큰 처리 ✓", left=700, top=270, width=140)
        result = lint_slide_spec(slide(textboxes=[label], shapes=[card]))
        assert not [x for x in result.violations if x.rule == "textbox-shape-intrusion"]


# ---------------------------------------------------------------------------
# decoration-shape-overlap
# ---------------------------------------------------------------------------


class TestDecorationShapeOverlap:
    def _card(
        self,
        left: float,
        top: float,
        width: float = 260,
        height: float = 80,
    ) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="web_search()", font_size_pt=16)])
            ],
        )

    def _badge(
        self,
        left: float,
        top: float,
        size: float = 44,
        text: str = "✕",
    ) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=size,
            height_px=size,
            shape_type="ellipse",
            fill_color="#E74C3C",
            text=text,
            text_color="#FFFFFF",
            text_size_pt=20,
            text_bold=True,
        )

    def test_badge_on_card_detected(self) -> None:
        card = self._card(880, 265, width=268, height=80)
        badge = self._badge(900, 280)
        result = lint_slide_spec(slide(shapes=[card, badge]))
        v = [x for x in result.violations if x.rule == "decoration-shape-overlap"]
        assert len(v) == 1
        assert v[0].element_index == 1

    def test_badge_outside_card_passes(self) -> None:
        card = self._card(880, 265)
        badge = self._badge(820, 290)
        result = lint_slide_spec(slide(shapes=[card, badge]))
        assert not [
            x for x in result.violations if x.rule == "decoration-shape-overlap"
        ]

    def test_centered_overlay_excluded(self) -> None:
        card = self._card(800, 260, width=300, height=200)
        badge = self._badge(930, 340, size=40)
        result = lint_slide_spec(slide(shapes=[card, badge]))
        assert not [
            x for x in result.violations if x.rule == "decoration-shape-overlap"
        ]

    def test_large_shape_not_decoration(self) -> None:
        card_a = self._card(800, 260, width=300, height=100)
        card_b = self._card(900, 290, width=300, height=100)
        result = lint_slide_spec(slide(shapes=[card_a, card_b]))
        assert not [
            x for x in result.violations if x.rule == "decoration-shape-overlap"
        ]


# ---------------------------------------------------------------------------
# textbox-textbox-overlap
# ---------------------------------------------------------------------------


class TestTextboxTextboxOverlap:
    def _label(
        self,
        text: str,
        left: float,
        top: float,
        width: float = 100,
        height: float = 22,
        font: int = 12,
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

    def test_overlapping_labels_detected(self) -> None:
        a = self._label("파싱 후 호출", left=980, top=376, width=80)
        b = self._label("함수들", left=998, top=376, width=160)
        result = lint_slide_spec(slide(textboxes=[a, b]))
        v = [x for x in result.violations if x.rule == "textbox-textbox-overlap"]
        assert len(v) == 1

    def test_separated_labels_pass(self) -> None:
        a = self._label("라벨 A", left=200, top=100)
        b = self._label("라벨 B", left=400, top=100)
        result = lint_slide_spec(slide(textboxes=[a, b]))
        assert not [x for x in result.violations if x.rule == "textbox-textbox-overlap"]

    def test_minor_corner_touch_passes(self) -> None:
        a = self._label("A", left=200, top=100, width=100, height=20)
        b = self._label("B", left=295, top=115, width=100, height=20)
        result = lint_slide_spec(slide(textboxes=[a, b]))
        assert not [x for x in result.violations if x.rule == "textbox-textbox-overlap"]

    def test_empty_textbox_excluded(self) -> None:
        a = self._label("라벨", left=200, top=100)
        empty = PptxTextBox(
            left_px=210,
            top_px=110,
            width_px=80,
            height_px=20,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="", font_size_pt=12)])],
        )
        result = lint_slide_spec(slide(textboxes=[a, empty]))
        assert not [x for x in result.violations if x.rule == "textbox-textbox-overlap"]


# ---------------------------------------------------------------------------
# component-id-link
# ---------------------------------------------------------------------------


class TestComponentIdLink:
    """Section ↔ Content 계층 link 정합성 검사."""

    def _layout_with_two_leaves(self):
        from ppt_generator.interfaces.schemas import LayoutNode

        return [
            LayoutNode(
                id="root",
                kind="section",
                left_px=0,
                top_px=0,
                width_px=100,
                height_px=100,
                children=[
                    LayoutNode(
                        id="root.a",
                        kind="component",
                        left_px=0,
                        top_px=0,
                        width_px=50,
                        height_px=50,
                    ),
                    LayoutNode(
                        id="root.b",
                        kind="component",
                        left_px=50,
                        top_px=0,
                        width_px=50,
                        height_px=50,
                    ),
                ],
            ),
        ]

    def _slide_with_layout(self, *, textboxes=None, shapes=None):
        from lint._lint_helpers import slide_with_design_doc

        from dataclasses import replace as _r

        spec = slide_with_design_doc(self._layout_with_two_leaves())
        spec = _r(spec, textboxes=textboxes or [], shapes=shapes or [])
        return spec

    def test_orphan_element_detected(self) -> None:
        """component_id 가 leaf 어디에도 없을 때."""
        from ppt_generator.interfaces.schemas import PptxTextBox

        tb_orphan = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=10,
            height_px=10,
            component_id="ghost.id",
        )
        spec = self._slide_with_layout(textboxes=[tb_orphan])
        result = lint_slide_spec(spec)
        v = [
            x for x in result.violations if x.rule == "component-id-link-orphan-element"
        ]
        assert len(v) == 1
        assert v[0].layer == "cross"

    def test_orphan_leaf_warning(self) -> None:
        """leaf 인데 어떤 element 도 참조 안 하면 warning."""
        # 두 leaf 중 하나만 참조
        from ppt_generator.interfaces.schemas import PptxTextBox

        tb_a = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=10,
            height_px=10,
            component_id="root.a",
        )
        spec = self._slide_with_layout(textboxes=[tb_a])
        result = lint_slide_spec(spec)
        orphan_leaves = [
            x for x in result.violations if x.rule == "component-id-link-orphan-leaf"
        ]
        # root.b 가 orphan
        assert len(orphan_leaves) == 1
        assert orphan_leaves[0].current_value == "root.b"

    def test_ambiguous_link_detected(self) -> None:
        """같은 component_id 가 두 element 에서 참조되면 ambiguous."""
        from ppt_generator.interfaces.schemas import PptxShape, PptxTextBox

        tb = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=10,
            height_px=10,
            component_id="root.a",
        )
        sh = PptxShape(
            left_px=50,
            top_px=0,
            width_px=10,
            height_px=10,
            component_id="root.a",  # 중복
        )
        spec = self._slide_with_layout(textboxes=[tb], shapes=[sh])
        result = lint_slide_spec(spec)
        v = [x for x in result.violations if x.rule == "component-id-link-ambiguous"]
        assert len(v) == 1

    def test_design_doc_none_skips_check(self) -> None:
        """design_doc=None 슬라이드는 검사 대상 제외 (graceful fallback)."""
        from ppt_generator.interfaces.schemas import PptxTextBox

        from lint._lint_helpers import slide

        # textbox 가 component_id 를 가지더라도 design_doc=None 이면 검사 스킵
        tb = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=10,
            height_px=10,
            component_id="something",
        )
        spec = slide(textboxes=[tb], slide_type="title")  # design_doc 없음
        result = lint_slide_spec(spec)
        v = [x for x in result.violations if x.rule.startswith("component-id-link")]
        assert len(v) == 0

    def test_clean_link_passes(self) -> None:
        """1:1 매칭 정상 케이스."""
        from ppt_generator.interfaces.schemas import PptxShape, PptxTextBox

        tb = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=10,
            height_px=10,
            component_id="root.a",
        )
        sh = PptxShape(
            left_px=50,
            top_px=0,
            width_px=10,
            height_px=10,
            component_id="root.b",
        )
        spec = self._slide_with_layout(textboxes=[tb], shapes=[sh])
        result = lint_slide_spec(spec)
        v = [x for x in result.violations if x.rule.startswith("component-id-link")]
        assert len(v) == 0
