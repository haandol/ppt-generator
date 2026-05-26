"""Section layer lint 테스트.

design_doc.layout 트리(섹션/그룹/컴포넌트)의 bbox·구조 검증:
- layout-tree-sibling-overlap, layout-tree-containment,
  layout-tree-bbox-missing, layout-tree-canvas-overflow
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    DesignDoc,
    LayoutNode,
    PptxSlideSpec,
)
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from lint._lint_helpers import slide_with_design_doc


class TestLayoutTreeBbox:
    """design_doc.layout 트리의 bbox 검증."""

    def test_sibling_overlap_detected(self) -> None:
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
        result = lint_slide_spec(slide_with_design_doc(layout))
        v = [x for x in result.violations if x.rule == "layout-tree-sibling-overlap"]
        assert len(v) == 1

    def test_non_overlapping_siblings_pass(self) -> None:
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
                left_px=624,
                top_px=148,
                width_px=592,
                height_px=510,
            ),
        ]
        result = lint_slide_spec(slide_with_design_doc(layout))
        v = [x for x in result.violations if x.rule == "layout-tree-sibling-overlap"]
        assert len(v) == 0

    def test_child_outside_parent_detected(self) -> None:
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
        result = lint_slide_spec(slide_with_design_doc(layout))
        v = [x for x in result.violations if x.rule == "layout-tree-containment"]
        assert len(v) == 1

    def test_section_without_bbox_flagged(self) -> None:
        layout = [LayoutNode(id="s", kind="section")]
        result = lint_slide_spec(slide_with_design_doc(layout))
        v = [x for x in result.violations if x.rule == "layout-tree-bbox-missing"]
        assert len(v) == 1

    def test_canvas_overflow_detected(self) -> None:
        layout = [
            LayoutNode(
                id="s",
                kind="section",
                left_px=64,
                top_px=148,
                width_px=2000,
                height_px=510,
            ),
        ]
        result = lint_slide_spec(slide_with_design_doc(layout))
        v = [x for x in result.violations if x.rule == "layout-tree-canvas-overflow"]
        assert len(v) == 1

    def test_no_design_doc_skipped(self) -> None:
        result = lint_slide_spec(
            PptxSlideSpec(background_color="#000", slide_type="content")
        )
        v = [x for x in result.violations if x.rule.startswith("layout-tree")]
        assert len(v) == 0


class TestSectionLayerFilter:
    """layout-tree 위반은 section layer 로 분류된다."""

    def test_filter_section_layer(self) -> None:
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
        result = lint_slide_spec(spec, layers=["section"])
        rules = {v.rule for v in result.violations}
        assert "layout-tree-sibling-overlap" in rules
        assert {v.layer for v in result.violations} == {"section"}
