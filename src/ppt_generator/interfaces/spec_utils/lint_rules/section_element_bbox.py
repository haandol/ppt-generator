"""section-element-bbox-mismatch: design_doc leaf bbox ↔ element bbox 동기화.

ADR-0049 결정 13d (cross-layer rule):
  - section-element-bbox-mismatch: component leaf 의 bbox 와 그 leaf 를
    component_id 로 참조하는 textbox/shape 의 bbox 가 임계값 초과로 어긋남.

ADR-0049 결정 3 ("Section bbox 가 Content bbox 보다 *먼저* 결정된다") 의
약속을 lint 차원에서 검증한다. 두 bbox 가 어긋나면 modify_component 가 동기화
시점에 의존하게 되고, 시각 결과가 사용자가 design_doc 트리에서 인지한 영역과
달라진다.

검사 대상은 (a) design_doc 가 존재하고 (b) leaf node (children 없음) 이며
(c) 노드의 left/top/width/height 가 모두 채워져 있고 (d) 그 leaf 를
component_id 로 참조하는 element 가 정확히 1 개 존재할 때에 한정.

design_doc/element link 가 없거나 ambiguous 인 케이스는 component-id-link
규칙이 별도로 보고하므로 여기서는 검사하지 않는다 (중복 보고 회피).
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import LayoutNode, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

# 8px = ADR-0049 결정 13d. Section bbox 는 의미 영역의 *외곽*, element bbox 는
# 실제 그려지는 픽셀이라 미세한 오차는 허용한다. 단, 한 변이라도 8px 초과로
# 어긋나면 사용자가 인지하는 영역과 시각 결과가 달라진다.
_BBOX_TOLERANCE_PX = 8.0


def _leaf_components(nodes: list[LayoutNode]):
    """component-leaf 만 yield (children 없음 + bbox 4 개 모두 채워짐)."""
    for n in nodes:
        if n.children:
            yield from _leaf_components(n.children)
            continue
        if (
            n.left_px is not None
            and n.top_px is not None
            and n.width_px is not None
            and n.height_px is not None
        ):
            yield n


def check_section_element_bbox(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    if spec.design_doc is None:
        return

    # element index by component_id (textbox/shape 양쪽 합산)
    elem_by_cid: dict[str, tuple[str, int, float, float, float, float]] = {}
    duplicates: set[str] = set()
    for i, tb in enumerate(spec.textboxes):
        if not tb.component_id:
            continue
        key = tb.component_id
        if key in elem_by_cid:
            duplicates.add(key)
        else:
            elem_by_cid[key] = (
                "textbox",
                i,
                tb.left_px,
                tb.top_px,
                tb.left_px + tb.width_px,
                tb.top_px + tb.height_px,
            )
    for i, s in enumerate(spec.shapes):
        if not s.component_id:
            continue
        key = s.component_id
        if key in elem_by_cid:
            duplicates.add(key)
        else:
            elem_by_cid[key] = (
                "shape",
                i,
                s.left_px,
                s.top_px,
                s.left_px + s.width_px,
                s.top_px + s.height_px,
            )

    for leaf in _leaf_components(spec.design_doc.layout):
        if leaf.id in duplicates:
            continue  # ambiguous — component-id-link 가 보고
        link = elem_by_cid.get(leaf.id)
        if link is None:
            continue  # 0 reference — component-id-link-orphan-leaf 가 보고
        kind, idx, e_l, e_t, e_r, e_b = link
        s_l = leaf.left_px
        s_t = leaf.top_px
        s_r = leaf.left_px + leaf.width_px
        s_b = leaf.top_px + leaf.height_px
        diffs = {
            "left": abs(s_l - e_l),
            "top": abs(s_t - e_t),
            "right": abs(s_r - e_r),
            "bottom": abs(s_b - e_b),
        }
        worst = max(diffs.values())
        if worst > _BBOX_TOLERANCE_PX:
            offenders = ", ".join(
                f"{side}={d:.1f}px"
                for side, d in diffs.items()
                if d > _BBOX_TOLERANCE_PX
            )
            result.violations.append(
                LintViolation(
                    rule="section-element-bbox-mismatch",
                    severity="error",
                    message=(
                        f"design_doc leaf {leaf.id!r} 의 bbox 가 {kind}#{idx} "
                        f"(component_id={leaf.id!r}) 와 어긋납니다 ({offenders}, "
                        f"tolerance={_BBOX_TOLERANCE_PX:.0f}px). Section 의 bbox "
                        "결정이 Content 보다 먼저 이뤄져야 하며 element bbox 는 "
                        "그 안에 정렬되어야 합니다."
                    ),
                    element_index=idx,
                    element_type=kind,
                    current_value={
                        "leaf_bbox": [s_l, s_t, s_r, s_b],
                        "element_bbox": [e_l, e_t, e_r, e_b],
                        "diffs": diffs,
                    },
                    expected=f"max edge diff ≤ {_BBOX_TOLERANCE_PX:.0f}px",
                )
            )
