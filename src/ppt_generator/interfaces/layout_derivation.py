"""Section 의미 트리의 bbox를 실제 렌더 요소 좌표에서 파생한다."""

from __future__ import annotations

from dataclasses import replace

from ppt_generator.interfaces.schemas import (
    LayoutNode,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)


def _element_bbox(
    element: PptxTextBox | PptxShape,
) -> tuple[float, float, float, float]:
    left = min(element.left_px, element.left_px + element.width_px)
    right = max(element.left_px, element.left_px + element.width_px)
    top = min(element.top_px, element.top_px + element.height_px)
    bottom = max(element.top_px, element.top_px + element.height_px)
    return left, top, right, bottom


def _derive_nodes(
    roots: list[LayoutNode],
    textboxes: list[PptxTextBox],
    shapes: list[PptxShape],
) -> list[LayoutNode]:
    elements: dict[str, PptxTextBox | PptxShape] = {}
    for element in [*textboxes, *shapes]:
        if element.component_id:
            elements[element.component_id] = element

    def derive(node: LayoutNode) -> LayoutNode:
        if not node.children:
            element = elements.get(node.id)
            if element is None:
                return node
            left, top, right, bottom = _element_bbox(element)
            return replace(
                node,
                left_px=left,
                top_px=top,
                width_px=right - left,
                height_px=bottom - top,
            )

        children = [derive(child) for child in node.children]
        bboxes = [
            (child.left_px, child.top_px, child.width_px, child.height_px)
            for child in children
            if all(
                value is not None
                for value in (
                    child.left_px,
                    child.top_px,
                    child.width_px,
                    child.height_px,
                )
            )
        ]
        if not bboxes:
            return replace(node, children=children)
        left = min(float(bbox[0]) for bbox in bboxes)
        top = min(float(bbox[1]) for bbox in bboxes)
        right = max(float(bbox[0]) + float(bbox[2]) for bbox in bboxes)
        bottom = max(float(bbox[1]) + float(bbox[3]) for bbox in bboxes)
        return replace(
            node,
            children=children,
            left_px=left,
            top_px=top,
            width_px=right - left,
            height_px=bottom - top,
        )

    return [derive(root) for root in roots]


def derive_layout_bboxes(
    roots: list[LayoutNode],
    textboxes: list[PptxTextBox],
    shapes: list[PptxShape],
) -> list[LayoutNode]:
    """LLM이 만든 의미 트리에 Content 좌표 기반 bbox를 채운다."""
    return _derive_nodes(roots, textboxes, shapes)


def derive_spec_layout_bboxes(spec: PptxSlideSpec) -> PptxSlideSpec:
    """부분 수정 뒤에도 Section bbox가 실제 렌더 요소를 가리키게 재구성한다."""
    if spec.design_doc is None:
        return spec
    design_doc = replace(
        spec.design_doc,
        layout=_derive_nodes(
            spec.design_doc.layout,
            spec.textboxes,
            spec.shapes,
        ),
    )
    return replace(spec, design_doc=design_doc)
