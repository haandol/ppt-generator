"""임포트 슬라이드의 의미 트리 검증과 보완."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import NoReturn

from ppt_generator.interfaces.output_models.layout import grid_plan_from_output
from ppt_generator.interfaces.output_models.modification import (
    BackfillDesignDocOutput,
    BackfillNode,
)
from ppt_generator.interfaces.schemas import (
    DesignDoc,
    GridPlan,
    LayoutNode,
    PptxShape,
    PptxSlideSpec,
)

logger = logging.getLogger(__name__)


def _is_decorative(shape: PptxShape) -> bool:
    """단순 connecting line/arrow (텍스트 없고 두께 ≤3px) 는 backfill 에서 제외."""
    has_text = bool(shape.text and shape.text.strip())
    if not has_text and shape.paragraphs:
        has_text = any(
            run.text.strip() for para in shape.paragraphs for run in para.runs
        )
    if has_text:
        return False
    is_thin_line = (
        shape.shape_type == "line"
        or abs(shape.width_px) <= 3
        or abs(shape.height_px) <= 3
    )
    return is_thin_line


def _serialize_elements_for_backfill(spec: PptxSlideSpec) -> str:
    """LLM 에 전달할 element 요약 JSON. bbox + 텍스트 + 핵심 스타일."""
    items: list[dict] = []
    for i, tb in enumerate(spec.textboxes):
        text_parts: list[str] = []
        for para in tb.paragraphs:
            for run in para.runs:
                if run.text.strip():
                    text_parts.append(run.text)
        items.append(
            {
                "kind": "textbox",
                "index": i,
                "bbox": [tb.left_px, tb.top_px, tb.width_px, tb.height_px],
                "text": " ".join(text_parts).strip(),
            }
        )
    for i, s in enumerate(spec.shapes):
        text_parts = []
        if s.text and s.text.strip():
            text_parts.append(s.text)
        for para in s.paragraphs:
            for run in para.runs:
                if run.text.strip():
                    text_parts.append(run.text)
        item: dict = {
            "kind": "shape",
            "index": i,
            "bbox": [s.left_px, s.top_px, s.width_px, s.height_px],
            "shape_type": s.shape_type,
            "fill_color": s.fill_color,
            "text": " ".join(text_parts).strip(),
            "decorative": _is_decorative(s),
        }
        items.append(item)
    return json.dumps({"elements": items}, ensure_ascii=False, indent=2)


def _backfill_fail(reason: str, **context: object) -> NoReturn:
    """backfill 검증 실패를 로깅하고 ValueError raise. context 는 디버깅용 메타."""
    ctx_str = " ".join(f"{k}={v!r}" for k, v in context.items() if v is not None)
    logger.error("backfill validation failed: %s | %s", reason, ctx_str)
    raise ValueError(reason)


def _apply_backfill_output(
    spec: PptxSlideSpec, output: BackfillDesignDocOutput
) -> PptxSlideSpec:
    """LLM 응답을 검증하고, design_doc 트리 + textbox/shape component_id 를 채운다.

    bbox 후처리:
      - leaf component bbox = 참조한 element bbox
      - section/group bbox = 자식 bbox 의 axis-aligned 합집합
    """
    nodes_by_id: dict[str, BackfillNode] = {}
    for ni, n in enumerate(output.nodes):
        if not n.id:
            _backfill_fail(
                "backfill output contains a node with empty id",
                node_position=ni,
                kind=n.kind,
                parent_id=n.parent_id,
            )
        if n.id in nodes_by_id:
            _backfill_fail(
                f"backfill output has duplicate node id: {n.id}",
                node_id=n.id,
                node_position=ni,
            )
        nodes_by_id[n.id] = n

    # parent 검증
    for n in output.nodes:
        pid = n.parent_id or ""
        if pid and pid not in nodes_by_id:
            _backfill_fail(
                f"backfill node {n.id!r} has unknown parent_id: {pid!r}",
                node_id=n.id,
                parent_id=pid,
                known_ids=sorted(nodes_by_id.keys()),
            )

    # leaf 의 element_ref 검증 + 매핑 수집
    tb_to_component: dict[int, str] = {}
    sh_to_component: dict[int, str] = {}
    for n in output.nodes:
        if n.kind != "component":
            continue
        if n.element_ref is None:
            _backfill_fail(
                f"component leaf {n.id!r} has no element_ref",
                node_id=n.id,
            )
        ref = n.element_ref
        if ref.kind == "textbox":
            if ref.index >= len(spec.textboxes):
                _backfill_fail(
                    f"component {n.id!r} references textbox#{ref.index} but slide "
                    f"has {len(spec.textboxes)} textboxes",
                    node_id=n.id,
                    ref_kind=ref.kind,
                    ref_index=ref.index,
                    textbox_count=len(spec.textboxes),
                )
            if ref.index in tb_to_component:
                _backfill_fail(
                    f"textbox#{ref.index} is referenced by multiple components: "
                    f"{tb_to_component[ref.index]!r} and {n.id!r}",
                    ref_index=ref.index,
                    first_node=tb_to_component[ref.index],
                    second_node=n.id,
                )
            tb_to_component[ref.index] = n.id
        else:
            if ref.index >= len(spec.shapes):
                _backfill_fail(
                    f"component {n.id!r} references shape#{ref.index} but slide "
                    f"has {len(spec.shapes)} shapes",
                    node_id=n.id,
                    ref_kind=ref.kind,
                    ref_index=ref.index,
                    shape_count=len(spec.shapes),
                )
            if ref.index in sh_to_component:
                _backfill_fail(
                    f"shape#{ref.index} is referenced by multiple components: "
                    f"{sh_to_component[ref.index]!r} and {n.id!r}",
                    ref_index=ref.index,
                    first_node=sh_to_component[ref.index],
                    second_node=n.id,
                )
            sh_to_component[ref.index] = n.id

    # 모든 textbox 가 매핑되었는지 확인 (decorative 가 textbox 일 수는 없음)
    missing_tb = [i for i in range(len(spec.textboxes)) if i not in tb_to_component]
    if missing_tb:
        _backfill_fail(
            f"backfill missed textbox indices: {missing_tb} — "
            "every textbox must map to exactly one component leaf",
            missing_textbox_indices=missing_tb,
        )
    # decorative 가 아닌 모든 shape 매핑 확인
    missing_sh = [
        i
        for i, s in enumerate(spec.shapes)
        if i not in sh_to_component and not _is_decorative(s)
    ]
    if missing_sh:
        _backfill_fail(
            f"backfill missed non-decorative shape indices: {missing_sh}",
            missing_shape_indices=missing_sh,
        )

    # 1) component leaf bbox 계산
    leaf_bboxes: dict[str, tuple[float, float, float, float]] = {}
    for n in output.nodes:
        if n.kind != "component":
            continue
        ref = n.element_ref
        if ref.kind == "textbox":
            tb = spec.textboxes[ref.index]
            leaf_bboxes[n.id] = (tb.left_px, tb.top_px, tb.width_px, tb.height_px)
        else:
            sh = spec.shapes[ref.index]
            leaf_bboxes[n.id] = (sh.left_px, sh.top_px, sh.width_px, sh.height_px)

    # 2) parent → children 인덱스 (입력 순서 유지)
    children_of: dict[str, list[str]] = {}
    order: list[str] = []
    for n in output.nodes:
        order.append(n.id)
        children_of.setdefault(n.parent_id or "", []).append(n.id)

    # 3) post-order 로 bbox 합집합
    bbox_of: dict[str, tuple[float, float, float, float]] = dict(leaf_bboxes)
    pending = list(order)
    while pending:
        progress = False
        for nid in list(pending):
            kids = children_of.get(nid, [])
            if all(k in bbox_of for k in kids):
                if nid in bbox_of:
                    pending.remove(nid)
                    progress = True
                    continue
                if not kids:
                    _backfill_fail(
                        f"non-component node {nid!r} has no children — invalid tree",
                        node_id=nid,
                    )
                lefts = [bbox_of[k][0] for k in kids]
                tops = [bbox_of[k][1] for k in kids]
                rights = [bbox_of[k][0] + bbox_of[k][2] for k in kids]
                bottoms = [bbox_of[k][1] + bbox_of[k][3] for k in kids]
                left = min(lefts)
                top = min(tops)
                width = max(rights) - left
                height = max(bottoms) - top
                bbox_of[nid] = (left, top, width, height)
                pending.remove(nid)
                progress = True
        if not progress:
            _backfill_fail(
                f"backfill tree has cycle or dangling parent_id: pending={pending}",
                pending_ids=pending,
            )

    # 4) LayoutNode 트리 구성 (post-order, frozen dataclass replace)
    finalized: dict[str, LayoutNode] = {}
    pending = list(order)
    while pending:
        progress = False
        for nid in list(pending):
            kids = children_of.get(nid, [])
            if all(k in finalized for k in kids):
                src = nodes_by_id[nid]
                left, top, width, height = bbox_of[nid]
                cell_id = ""
                # leaf 의 component_id 는 textbox/shape 의 grid_cell 에서 가져오면
                # imported 슬라이드는 None 이므로 그대로 빈 문자열 유지
                ref = src.element_ref
                if ref is not None:
                    if ref.kind == "textbox":
                        cell_id = spec.textboxes[ref.index].grid_cell or ""
                    else:
                        cell_id = spec.shapes[ref.index].grid_cell or ""
                finalized[nid] = LayoutNode(
                    id=nid,
                    kind=src.kind,
                    role=src.role or "",
                    description=src.description or "",
                    cell_id=cell_id,
                    left_px=left,
                    top_px=top,
                    width_px=width,
                    height_px=height,
                    children=[finalized[k] for k in kids],
                )
                pending.remove(nid)
                progress = True
        if not progress:
            _backfill_fail(
                "backfill tree finalization failed (cycle or unresolvable parent)",
                pending_ids=pending,
            )

    roots: list[LayoutNode] = [
        finalized[nid] for nid in order if not (nodes_by_id[nid].parent_id or "")
    ]
    new_design_doc = DesignDoc(
        topic=output.topic,
        layout_summary=output.layout_summary,
        layout=roots,
    )

    # 5) textbox/shape 에 component_id 채우기
    new_textboxes = [
        replace(tb, component_id=tb_to_component.get(i))
        for i, tb in enumerate(spec.textboxes)
    ]
    new_shapes = [
        replace(s, component_id=sh_to_component.get(i))
        for i, s in enumerate(spec.shapes)
    ]

    # 6) grid_plan 백필 — LLM 이 grid_layout/cell_assignment 를 출력했을
    # 때만 채운다. 그렇지 않으면 기존 spec.grid_plan 유지 (보통 None).
    new_grid_plan: GridPlan | None = spec.grid_plan
    if output.grid_layout is not None:
        new_grid_plan = grid_plan_from_output(
            output.grid_layout, output.cell_assignment
        )

    return replace(
        spec,
        textboxes=new_textboxes,
        shapes=new_shapes,
        design_doc=new_design_doc,
        grid_plan=new_grid_plan,
    )
