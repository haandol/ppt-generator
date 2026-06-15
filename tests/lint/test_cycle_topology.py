"""cycle-topology lint 테스트 — 순환 다이어그램 위상 일관성 (cross-layer).

선언 기반: design_doc.layout 의 role="cycle_diagram" 묶음만 검사. 마킹 없으면
검사 안 함(추측 금지). 각 노드 in/out-degree=1 + 단일 사이클이면 통과, 깨지면 warning.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    DesignDoc,
    LayoutNode,
    PptxShape,
    PptxSlideSpec,
)
from ppt_generator.interfaces.spec_utils import lint_slide_spec


def _node(
    node_id: str, left: float, top: float, w: float = 160, h: float = 60
) -> LayoutNode:
    return LayoutNode(
        id=node_id,
        kind="component",
        role="cycle_node",
        left_px=left,
        top_px=top,
        width_px=w,
        height_px=h,
    )


def _line(left, top, w, h, *, start_arrow=False, end_arrow=True) -> PptxShape:
    return PptxShape(
        left_px=left,
        top_px=top,
        width_px=w,
        height_px=h,
        shape_type="line",
        border_color="#FF9900",
        border_width_pt=2,
        start_arrow=start_arrow,
        end_arrow=end_arrow,
    )


# 3노드 삼각 순환 배치 (ReAct 루프 모사):
#   Think  : x[244..444] y[218..282]  (상단 중앙)
#   Act    : x[424..624] y[436..500]  (우하단)
#   Observe: x[64..264]  y[436..500]  (좌하단)
def _cycle_group() -> LayoutNode:
    return LayoutNode(
        id="loop",
        kind="group",
        role="cycle_diagram",
        left_px=64,
        top_px=218,
        width_px=560,
        height_px=282,
        children=[
            _node("loop.think", 244, 218, 200, 64),
            _node("loop.act", 424, 436, 200, 64),
            _node("loop.observe", 64, 436, 200, 64),
        ],
    )


def _spec(shapes: list[PptxShape], group: LayoutNode | None = None) -> PptxSlideSpec:
    g = group if group is not None else _cycle_group()
    return PptxSlideSpec(
        background_color="#1a1a2e",
        slide_type="content",
        shapes=shapes,
        design_doc=DesignDoc(topic="ReAct", layout_summary="loop", layout=[g]),
    )


def _violations(spec: PptxSlideSpec) -> list:
    result = lint_slide_spec(spec)
    return [v for v in result.violations if v.rule == "cycle-topology-broken"]


class TestCycleTopology:
    def test_consistent_cycle_passes(self) -> None:
        """Think→Act→Observe→Think 올바른 단일 순환 → 위반 없음."""
        shapes = [
            # Think→Act: Think 하단우측(344,282) → Act 좌상단 근처(424,436)
            _line(344, 282, 80, 154, end_arrow=True),
            # Act→Observe: Act 좌변(424,468) → Observe 우변(264,468), head=Observe(start)
            _line(264, 468, 160, 0, start_arrow=True, end_arrow=False),
            # Observe→Think: Observe top(164,436) ↗ Think 좌하(244,282), head=Think(end)
            _line(164, 282, 80, -154, end_arrow=True),
        ]
        assert _violations(_spec(shapes)) == []

    def test_broken_cycle_detected(self) -> None:
        """Think→Act, Think→Observe, Observe→Act (Act 유입2/유출0) → 위반."""
        shapes = [
            _line(344, 282, 80, 154, end_arrow=True),  # Think→Act
            _line(164, 282, 80, 154, end_arrow=True),  # Think→Observe (head=Observe)
            _line(264, 468, 160, 0, end_arrow=True),  # Observe→Act (head=Act)
        ]
        v = _violations(_spec(shapes))
        assert len(v) == 1
        assert "사이클" in v[0].message
        assert v[0].severity == "warning"

    def test_no_marking_no_check(self) -> None:
        """role 마킹이 없으면(일반 group) 깨진 배치라도 검사하지 않는다."""
        group = _cycle_group()
        plain = LayoutNode(
            id=group.id,
            kind=group.kind,
            role="diagram",  # cycle_diagram 아님
            left_px=group.left_px,
            top_px=group.top_px,
            width_px=group.width_px,
            height_px=group.height_px,
            children=group.children,
        )
        shapes = [
            _line(344, 282, 80, 154, end_arrow=True),
            _line(164, 282, 80, 154, end_arrow=True),
            _line(264, 468, 160, 0, end_arrow=True),
        ]
        assert _violations(_spec(shapes, group=plain)) == []

    def test_no_design_doc_no_check(self) -> None:
        """design_doc 자체가 없으면 검사 제외."""
        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            slide_type="content",
            shapes=[_line(344, 282, 80, 154, end_arrow=True)],
        )
        assert _violations(spec) == []

    def test_no_edges_no_violation(self) -> None:
        """사이클 노드를 잇는 화살표가 없으면 판정 보류(위반 없음)."""
        # 화살표가 노드에서 멀리 떨어져 부착 안 됨
        shapes = [_line(1000, 600, 50, 0, end_arrow=True)]
        assert _violations(_spec(shapes)) == []
