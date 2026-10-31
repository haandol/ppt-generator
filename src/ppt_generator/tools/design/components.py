"""단일 요소 식별과 의미 트리 갱신을 위한 순수 함수."""

from __future__ import annotations

from dataclasses import replace

from ppt_generator.interfaces.schemas import (
    LayoutNode,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)


def _find_element_by_component_id(
    spec: PptxSlideSpec, component_id: str
) -> tuple[str, int, "PptxTextBox | PptxShape"]:
    """spec 의 textboxes/shapes 중 component_id 일치 element 를 찾는다.

    Returns:
        (kind, index, element) — kind 는 "textbox" | "shape", index 는 0-based.

    Raises:
        ValueError: component_id 가 어디에도 없거나 (정상 케이스), 두 곳 이상에서
            중복 매칭 (ambiguous link, 결정 12).
    """
    matches: list[tuple[str, int, PptxTextBox | PptxShape]] = []
    for i, tb in enumerate(spec.textboxes):
        if tb.component_id == component_id:
            matches.append(("textbox", i, tb))
    for i, s in enumerate(spec.shapes):
        if s.component_id == component_id:
            matches.append(("shape", i, s))
    if not matches:
        raise ValueError(
            f"component_id not found in slide: {component_id!r}. "
            "Check design_doc.layout for the available component ids."
        )
    if len(matches) > 1:
        locs = ", ".join(f"{k}#{i}" for k, i, _ in matches)
        raise ValueError(
            f"component_id {component_id!r} is ambiguous — matches multiple "
            f"elements: {locs}. component_id must be unique within a slide."
        )
    return matches[0]


def _find_layout_leaf_by_id(nodes: list[LayoutNode], component_id: str) -> LayoutNode:
    """design tree에서 id가 일치하는 유일한 component leaf를 찾는다."""
    matches: list[LayoutNode] = []

    def _walk(node: LayoutNode) -> None:
        if node.id == component_id:
            matches.append(node)
        for child in node.children:
            _walk(child)

    for root in nodes:
        _walk(root)
    if not matches:
        raise ValueError(
            f"component_id not found in design_doc.layout: {component_id!r}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"component_id {component_id!r} is ambiguous in design_doc.layout"
        )
    node = matches[0]
    if node.kind != "component" or node.children:
        raise ValueError(
            f"component_id {component_id!r} must reference a component leaf"
        )
    return node


def _replace_node_bbox(
    nodes: list[LayoutNode],
    target_id: str,
    bbox: tuple[float, float, float, float],
) -> list[LayoutNode]:
    """design_doc.layout 트리(임의 깊이)에서 target_id 노드의 bbox 만 교체한다.

    frozen dataclass 라 path 따라 부모 체인을 replace 로 새로 만든다.
    """
    left, top, width, height = bbox

    def _walk(node: LayoutNode) -> tuple[LayoutNode, bool]:
        if node.id == target_id:
            return (
                replace(
                    node,
                    left_px=left,
                    top_px=top,
                    width_px=width,
                    height_px=height,
                ),
                True,
            )
        new_children: list[LayoutNode] = []
        changed = False
        for child in node.children:
            new_child, child_changed = _walk(child)
            new_children.append(new_child)
            if child_changed:
                changed = True
        if changed:
            return (replace(node, children=new_children), True)
        return (node, False)

    out: list[LayoutNode] = []
    for n in nodes:
        new_node, _ = _walk(n)
        out.append(new_node)
    return out
