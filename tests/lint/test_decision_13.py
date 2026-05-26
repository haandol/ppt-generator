"""결정 13 — 단계적 lint, grid-section-link, section-element-bbox,
section-grid-containment, edge-alignment 신규 규칙 테스트.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    DesignDoc,
    GridCell,
    GridPlan,
    LayoutNode,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from lint._lint_helpers import minimal_content_grid_plan, slide, tb


# ---------------------------------------------------------------------------
# 결정 13a/b — 단계적 lint
# ---------------------------------------------------------------------------


class TestStopOnLayerError:
    """stop_on_layer_error=True 가 layer 별 검사를 단계적으로 진행."""

    def _layout_error_spec(self) -> PptxSlideSpec:
        # content slide + grid_plan=None → grid-plan-required (layout, error)
        return PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            textboxes=[tb("작은 제목", font=12)],  # title-font-min content error
            grid_plan=None,
        )

    def test_default_runs_all_layers(self) -> None:
        result = lint_slide_spec(self._layout_error_spec())
        rules = {v.rule for v in result.violations}
        assert "grid-plan-required" in rules
        assert "title-font-min" in rules

    def test_stop_on_layer_error_skips_content(self) -> None:
        result = lint_slide_spec(self._layout_error_spec(), stop_on_layer_error=True)
        rules = {v.rule for v in result.violations}
        # layout error 발견 → section/cross/content 스킵
        assert "grid-plan-required" in rules
        assert "title-font-min" not in rules


# ---------------------------------------------------------------------------
# 결정 13c — grid-section-link-orphan-cell
# ---------------------------------------------------------------------------


class TestGridSectionLink:
    def _spec_with(self, cell_id: str | None) -> PptxSlideSpec:
        layout = [
            LayoutNode(
                id="left",
                kind="section",
                cell_id=cell_id,
                left_px=64,
                top_px=148,
                width_px=560,
                height_px=400,
            ),
        ]
        return PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            grid_plan=minimal_content_grid_plan(),  # cells: h1, c1
            design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
        )

    def test_orphan_cell_id_detected(self) -> None:
        result = lint_slide_spec(self._spec_with("nonexistent_cell"))
        v = [r for r in result.violations if r.rule == "grid-section-link-orphan-cell"]
        assert len(v) == 1
        assert v[0].severity == "error"

    def test_valid_cell_id_passes(self) -> None:
        result = lint_slide_spec(self._spec_with("c1"))
        assert not [
            r for r in result.violations if r.rule == "grid-section-link-orphan-cell"
        ]

    def test_none_cell_id_passes(self) -> None:
        result = lint_slide_spec(self._spec_with(None))
        assert not [
            r for r in result.violations if r.rule == "grid-section-link-orphan-cell"
        ]


# ---------------------------------------------------------------------------
# 결정 13d — section-element-bbox-mismatch
# ---------------------------------------------------------------------------


def _spec_with_leaf_and_element(
    leaf_bbox: tuple[float, float, float, float],
    elem_bbox: tuple[float, float, float, float],
) -> PptxSlideSpec:
    """leaf bbox 와 그 leaf 를 component_id 로 가리키는 textbox 1 개."""
    l, t, r, b = leaf_bbox
    el, et, er, eb = elem_bbox
    layout = [
        LayoutNode(
            id="leaf",
            kind="component",
            left_px=l,
            top_px=t,
            width_px=r - l,
            height_px=b - t,
        ),
    ]
    return PptxSlideSpec(
        background_color="#1a1a2e",
        slide_type="content",
        textboxes=[
            PptxTextBox(
                left_px=el,
                top_px=et,
                width_px=er - el,
                height_px=eb - et,
                paragraphs=[
                    PptxParagraph(runs=[PptxTextRun(text="x", font_size_pt=20)])
                ],
                component_id="leaf",
            ),
        ],
        design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
    )


class TestSectionElementBboxMismatch:
    def test_bbox_match_no_violation(self) -> None:
        s = _spec_with_leaf_and_element(
            leaf_bbox=(64, 148, 624, 548),
            elem_bbox=(64, 148, 624, 548),
        )
        result = lint_slide_spec(s)
        assert not [
            r for r in result.violations if r.rule == "section-element-bbox-mismatch"
        ]

    def test_within_tolerance_no_violation(self) -> None:
        s = _spec_with_leaf_and_element(
            leaf_bbox=(64, 148, 624, 548),
            elem_bbox=(70, 152, 622, 546),  # max 6px diff < 8px
        )
        result = lint_slide_spec(s)
        assert not [
            r for r in result.violations if r.rule == "section-element-bbox-mismatch"
        ]

    def test_bbox_mismatch_detected(self) -> None:
        s = _spec_with_leaf_and_element(
            leaf_bbox=(64, 148, 624, 548),
            elem_bbox=(120, 160, 624, 548),  # left 56px diff
        )
        result = lint_slide_spec(s)
        v = [r for r in result.violations if r.rule == "section-element-bbox-mismatch"]
        assert len(v) == 1
        assert v[0].severity == "error"


# ---------------------------------------------------------------------------
# 결정 13g — element-out-of-section
# ---------------------------------------------------------------------------


class TestElementOutOfSection:
    def _spec(self, elem_left: float, elem_width: float) -> PptxSlideSpec:
        layout = [
            LayoutNode(
                id="parent",
                kind="section",
                left_px=64,
                top_px=148,
                width_px=560,
                height_px=400,
                children=[
                    LayoutNode(
                        id="child",
                        kind="component",
                        left_px=80,
                        top_px=160,
                        width_px=520,
                        height_px=380,
                    ),
                ],
            ),
        ]
        return PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            textboxes=[
                PptxTextBox(
                    left_px=elem_left,
                    top_px=160,
                    width_px=elem_width,
                    height_px=300,
                    paragraphs=[
                        PptxParagraph(runs=[PptxTextRun(text="x", font_size_pt=20)])
                    ],
                    component_id="child",
                ),
            ],
            design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
        )

    def test_inside_parent_no_violation(self) -> None:
        result = lint_slide_spec(self._spec(elem_left=80, elem_width=520))
        assert not [r for r in result.violations if r.rule == "element-out-of-section"]

    def test_outside_parent_detected(self) -> None:
        # element 가 parent (64+560=624) 를 한참 넘어감
        result = lint_slide_spec(self._spec(elem_left=80, elem_width=900))
        v = [r for r in result.violations if r.rule == "element-out-of-section"]
        assert len(v) == 1
        assert v[0].severity == "error"


# ---------------------------------------------------------------------------
# 결정 13f — slide-edge-alignment
# ---------------------------------------------------------------------------


class TestEdgeAlignment:
    def _shape(self, left: int, top: int, w: int = 200, h: int = 100) -> PptxShape:
        return PptxShape(
            left_px=left,
            top_px=top,
            width_px=w,
            height_px=h,
            shape_type="rounded_rectangle",
            fill_color="#243447",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="카드", font_size_pt=18)])
            ],
        )

    def test_aligned_left_edges_no_violation(self) -> None:
        a = self._shape(64, 148)
        b = self._shape(64, 320)
        c = self._shape(64, 500)
        result = lint_slide_spec(slide(shapes=[a, b, c]))
        assert not [
            r for r in result.violations if r.rule.startswith("slide-edge-alignment")
        ]

    def test_misaligned_left_edge_detected(self) -> None:
        a = self._shape(64, 148)  # cluster ref
        b = self._shape(72, 320)  # 8px off → > 4
        c = self._shape(64, 500)
        result = lint_slide_spec(slide(shapes=[a, b, c]))
        v = [r for r in result.violations if r.rule == "slide-edge-alignment-left"]
        assert len(v) == 1
        assert v[0].severity == "warning"

    def test_misaligned_right_edge_detected(self) -> None:
        # right cluster: a.right=264, b.right=270 (6px off), c.right=264
        a = self._shape(64, 148, w=200)
        b = self._shape(64, 320, w=206)
        c = self._shape(64, 500, w=200)
        result = lint_slide_spec(slide(shapes=[a, b, c]))
        v = [r for r in result.violations if r.rule == "slide-edge-alignment-right"]
        assert len(v) == 1

    def test_outside_cluster_threshold_excluded(self) -> None:
        # left=64 한 개와 left=400 한 개 — 두 element 는 다른 cluster
        a = self._shape(64, 148)
        b = self._shape(400, 320)
        result = lint_slide_spec(slide(shapes=[a, b]))
        # cluster 에 element 가 1 개씩이면 정렬 검사 대상 아님
        assert not [
            r for r in result.violations if r.rule.startswith("slide-edge-alignment")
        ]

    def test_decoration_stripe_misaligned_with_body_detected(self) -> None:
        # 본문 카드들은 left=64 로 정렬되어 있는데 좌측 장식 stripe 만
        # left=72 로 어긋나 cluster (64±16) 안에 들어옴 → 위반 검출.
        a = self._shape(64, 148)
        b = self._shape(64, 320)
        # decoration: 텍스트 없는 6px 폭 stripe
        deco = PptxShape(
            left_px=72,
            top_px=148,
            width_px=6,
            height_px=300,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = lint_slide_spec(slide(shapes=[a, b, deco]))
        v = [r for r in result.violations if r.rule == "slide-edge-alignment-left"]
        assert len(v) == 1
        assert v[0].severity == "warning"

    def test_decoration_stripe_alone_no_violation(self) -> None:
        # 본문 element 가 없는 외곽 디바이더는 정렬 검사 대상 아님
        # (본문 element 2 개 미만이면 skip).
        deco_l = PptxShape(
            left_px=40,
            top_px=148,
            width_px=6,
            height_px=300,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        deco_r = PptxShape(
            left_px=1234,
            top_px=148,
            width_px=6,
            height_px=300,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        body = self._shape(64, 148)
        result = lint_slide_spec(slide(shapes=[deco_l, deco_r, body]))
        # body 가 1 개뿐 → 본문 cluster 정렬 검사 skip
        assert not [
            r for r in result.violations if r.rule.startswith("slide-edge-alignment")
        ]


# ---------------------------------------------------------------------------
# 결정 13e' — layout-tree sibling/containment/canvas-overflow severity
# ---------------------------------------------------------------------------


class TestLayoutTreeErrorSeverity:
    def test_sibling_overlap_is_error(self) -> None:
        layout = [
            LayoutNode(
                id="a",
                kind="section",
                left_px=64,
                top_px=148,
                width_px=540,
                height_px=510,
            ),
            LayoutNode(
                id="b",
                kind="section",
                left_px=400,
                top_px=148,
                width_px=540,
                height_px=510,
            ),
        ]
        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
        )
        v = [
            r
            for r in lint_slide_spec(spec).violations
            if r.rule == "layout-tree-sibling-overlap"
        ]
        assert v and v[0].severity == "error"

    def test_containment_is_error(self) -> None:
        layout = [
            LayoutNode(
                id="parent",
                kind="section",
                left_px=64,
                top_px=148,
                width_px=540,
                height_px=200,
                children=[
                    LayoutNode(
                        id="parent.child",
                        kind="component",
                        left_px=64,
                        top_px=148,
                        width_px=700,
                        height_px=100,
                    ),
                ],
            ),
        ]
        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
        )
        v = [
            r
            for r in lint_slide_spec(spec).violations
            if r.rule == "layout-tree-containment"
        ]
        assert v and v[0].severity == "error"
