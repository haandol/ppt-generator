"""layout-tree-bbox: design_doc.layout 트리의 bbox 위반 검사.

같은 부모를 공유하는 sibling 노드끼리 bbox 가 겹치면 위반 (구조적 충돌).
자식의 bbox 는 부모 bbox 안에 포함되어야 한다 (containment 위반 검출).
bbox 가 캔버스 밖이면 canvas-overflow 와 별개로 layout-tree 차원에서 검출.

Rules:
  - layout-tree-sibling-overlap: 같은 depth 의 형제 두 노드 bbox 교집합 면적 > 0
  - layout-tree-containment: 자식 bbox 가 부모 bbox 의 외부로 빠져나감
  - layout-tree-bbox-missing: section/group 노드인데 bbox 미지정
  - layout-tree-canvas-overflow: 노드 bbox 가 캔버스 [0, 0, 1280, 720] 밖
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import SLIDE_WIDTH, SLIDE_HEIGHT
from ppt_generator.interfaces.schemas import (
    LayoutNode,
    PptxSlideSpec,
)
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)


def _bbox(node: LayoutNode) -> tuple[float, float, float, float] | None:
    if (
        node.left_px is None
        or node.top_px is None
        or node.width_px is None
        or node.height_px is None
    ):
        return None
    return (
        node.left_px,
        node.top_px,
        node.left_px + abs(node.width_px),
        node.top_px + abs(node.height_px),
    )


def _intersection_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def _contained(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
    tol: float = 1.0,
) -> bool:
    return (
        inner[0] >= outer[0] - tol
        and inner[1] >= outer[1] - tol
        and inner[2] <= outer[2] + tol
        and inner[3] <= outer[3] + tol
    )


def _walk(
    nodes: list[LayoutNode],
    depth: int,
    parent_path: str,
    parent_bbox: tuple[float, float, float, float] | None,
    result: SlideLintResult,
) -> None:
    # Sibling overlap check
    siblings_with_bbox: list[tuple[LayoutNode, tuple[float, float, float, float]]] = []
    for node in nodes:
        b = _bbox(node)
        if b is not None:
            siblings_with_bbox.append((node, b))

    for i in range(len(siblings_with_bbox)):
        node_a, bbox_a = siblings_with_bbox[i]
        for j in range(i + 1, len(siblings_with_bbox)):
            node_b, bbox_b = siblings_with_bbox[j]
            inter = _intersection_area(bbox_a, bbox_b)
            if inter > 1.0:  # 1px tolerance
                result.violations.append(
                    LintViolation(
                        rule="layout-tree-sibling-overlap",
                        severity="warning",
                        message=(
                            f"depth {depth} sibling 노드 '{node_a.id}' 와 '{node_b.id}' "
                            f"bbox 가 겹침 (교집합 {inter:.0f}px²)"
                        ),
                        element_index=-1,
                        element_type="slide",
                        current_value={
                            "node_a_id": node_a.id,
                            "node_b_id": node_b.id,
                            "intersection_px2": round(inter, 1),
                            "depth": depth,
                        },
                        expected="형제 노드 bbox 는 겹쳐서는 안 됨",
                    )
                )

    # 각 노드 검사
    for node, bbox in siblings_with_bbox:
        # canvas overflow
        if (
            bbox[0] < -1
            or bbox[1] < -1
            or bbox[2] > SLIDE_WIDTH + 1
            or bbox[3] > SLIDE_HEIGHT + 1
        ):
            result.violations.append(
                LintViolation(
                    rule="layout-tree-canvas-overflow",
                    severity="warning",
                    message=(
                        f"layout 노드 '{node.id}' bbox 가 캔버스 ({SLIDE_WIDTH}x{SLIDE_HEIGHT}) 밖"
                    ),
                    element_index=-1,
                    element_type="slide",
                    current_value={"node_id": node.id, "bbox": list(bbox)},
                    expected="bbox 가 캔버스 안에 있어야 함",
                )
            )
        # containment
        if parent_bbox is not None and not _contained(bbox, parent_bbox):
            result.violations.append(
                LintViolation(
                    rule="layout-tree-containment",
                    severity="warning",
                    message=(
                        f"layout 노드 '{node.id}' bbox 가 부모 '{parent_path}' bbox 밖으로 나감"
                    ),
                    element_index=-1,
                    element_type="slide",
                    current_value={
                        "node_id": node.id,
                        "node_bbox": list(bbox),
                        "parent_bbox": list(parent_bbox),
                    },
                    expected="자식 bbox 는 부모 bbox 안에 완전히 포함되어야 함",
                )
            )

    # bbox 미지정 노드 (section/group 만 강제)
    for node in nodes:
        if node.kind in ("section", "group") and _bbox(node) is None:
            result.violations.append(
                LintViolation(
                    rule="layout-tree-bbox-missing",
                    severity="warning",
                    message=(
                        f"{node.kind} 노드 '{node.id}' 에 bbox 가 지정되지 않음 "
                        f"(bbox-first 원칙: section/group 은 좌표를 먼저 결정)"
                    ),
                    element_index=-1,
                    element_type="slide",
                    current_value={"node_id": node.id, "kind": node.kind},
                    expected="left_px/top_px/width_px/height_px 모두 지정",
                )
            )

    # 자식 재귀
    for node in nodes:
        if node.children:
            _walk(
                node.children,
                depth + 1,
                node.id,
                _bbox(node),
                result,
            )


def check_layout_tree_bbox(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    if spec.design_doc is None or not spec.design_doc.layout:
        return
    _walk(
        spec.design_doc.layout,
        depth=0,
        parent_path="<root>",
        parent_bbox=None,
        result=result,
    )
