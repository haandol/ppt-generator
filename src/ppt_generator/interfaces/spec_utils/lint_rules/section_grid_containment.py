"""section-grid-containment: 섹션·cell 영역을 벗어나는 element 검출.

ADR-0049 결정 13g (cross layer rule):

각 element (textbox/shape) 는 자신이 속한 의미 영역(Section / Layout cell) 을
벗어나는 좌표를 가져선 안 된다. design_doc.layout 트리에서 element 의
component_id 를 leaf 로 잡고, 그 leaf 의 *조상* section/group 노드의 bbox 를
"섹션 경계" 로 보아 element bbox 가 그 외부로 빠져나가면 위반.

또한 element 의 grid_cell 이 GridPlan.cells 의 어떤 cell 을 가리킨다면,
그 cell 의 bbox 영역(region+row+col 으로 추정) 안에 element 가 들어와야 한다.

설계 원칙: ADR-0049 결정 3 ("Section/group 노드는 자식보다 *먼저* bbox 결정,
자식 bbox 는 부모 bbox 안에 완전히 포함") 을 *Content* 차원까지 확장.
section-element-bbox-mismatch 는 leaf↔element 1:1 동기화를 검사하지만,
이 규칙은 *조상 section* 까지 거슬러 올라가 "내가 속한 의미 영역" 을 element
가 지키는지 검사한다.

Rules:
  - element-out-of-section: element bbox 가 component_id 로 link 된 leaf 의
    가장 가까운 ancestor section/group bbox 외부로 빠져나감 (severity="error")
  - element-out-of-grid-cell: element 의 grid_cell 이 link 된 cell 의 estimated
    bbox 외부로 빠져나감 (severity="warning" — cell bbox 는 design_doc 가 더
    정확하므로 design_doc 가 있으면 이 규칙은 정보 보조 수준)

design_doc / grid_plan 가 없는 슬라이드는 검사 제외 (조건부).
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import SLIDE_HEIGHT, SLIDE_WIDTH
from ppt_generator.interfaces.schemas import LayoutNode, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

# section_element_bbox 와 동일 — leaf 와 정확히 일치 검사는 별도 규칙이 보고.
# 여기서는 *조상* 섹션을 벗어나는 큰 위반만 잡도록 더 관대한 임계값(8px) 사용.
_TOLERANCE_PX = 8.0


def _find_path_to_leaf(
    nodes: list[LayoutNode], target_id: str, path: list[LayoutNode]
) -> list[LayoutNode] | None:
    for n in nodes:
        new_path = path + [n]
        if n.id == target_id:
            return new_path
        if n.children:
            found = _find_path_to_leaf(n.children, target_id, new_path)
            if found is not None:
                return found
    return None


def _bbox_of(node: LayoutNode) -> tuple[float, float, float, float] | None:
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
        node.left_px + node.width_px,
        node.top_px + node.height_px,
    )


def _ancestor_section_bbox(
    path: list[LayoutNode],
) -> tuple[str, tuple[float, float, float, float]] | None:
    """leaf 까지의 path 에서 *leaf 자신* 을 빼고 가장 가까운 bbox 가 채워진 조상 반환."""
    for ancestor in reversed(path[:-1]):
        bbox = _bbox_of(ancestor)
        if bbox is not None:
            return ancestor.id, bbox
    return None


def _outside(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
    tol: float,
) -> dict | None:
    diffs = {
        "left_under": max(0.0, outer[0] - tol - inner[0]),
        "top_under": max(0.0, outer[1] - tol - inner[1]),
        "right_over": max(0.0, inner[2] - (outer[2] + tol)),
        "bottom_over": max(0.0, inner[3] - (outer[3] + tol)),
    }
    if all(v == 0 for v in diffs.values()):
        return None
    return diffs


def _grid_cell_estimated_bbox(
    spec: PptxSlideSpec, cell_id: str
) -> tuple[float, float, float, float] | None:
    """GridPlan.cells 의 row/col/region 에서 cell 의 추정 bbox 를 계산.

    region 픽셀 분할은 design_system_base.prompt.md 와 일치 — header [0,148],
    content [148,628], footer [628, 720]. content 영역에서 row/col span 으로
    나눈다. cell 이 없으면 None.
    """
    if spec.grid_plan is None:
        return None
    plan = spec.grid_plan
    cell = next((c for c in plan.cells if c.id == cell_id), None)
    if cell is None:
        return None

    # region 별 세로 영역
    if cell.region == "header":
        region_top, region_bottom = 0.0, 148.0
    elif cell.region == "footer":
        region_top, region_bottom = 628.0, float(SLIDE_HEIGHT)
    else:
        region_top, region_bottom = 148.0, 628.0

    cols = max(1, plan.content_columns) if cell.region == "content" else 1
    rows = max(1, plan.content_rows) if cell.region == "content" else 1
    col_w = SLIDE_WIDTH / cols
    row_h = (region_bottom - region_top) / rows

    col_start = max(0, cell.col - 1)
    row_start = max(0, cell.row - 1)
    left = col_start * col_w
    top = region_top + row_start * row_h
    right = left + col_w * max(1, cell.col_span)
    bottom = top + row_h * max(1, cell.row_span)
    return (left, top, right, bottom)


def check_section_grid_containment(
    spec: PptxSlideSpec, result: SlideLintResult
) -> None:
    has_design_doc = spec.design_doc is not None and bool(spec.design_doc.layout)
    has_grid_plan = spec.grid_plan is not None and bool(spec.grid_plan.cells)
    if not has_design_doc and not has_grid_plan:
        return

    elements: list[
        tuple[str, int, str | None, str | None, tuple[float, float, float, float]]
    ] = []
    for i, tb in enumerate(spec.textboxes):
        elements.append(
            (
                "textbox",
                i,
                tb.component_id,
                tb.grid_cell,
                (
                    tb.left_px,
                    tb.top_px,
                    tb.left_px + tb.width_px,
                    tb.top_px + tb.height_px,
                ),
            )
        )
    for i, s in enumerate(spec.shapes):
        elements.append(
            (
                "shape",
                i,
                s.component_id,
                s.grid_cell,
                (s.left_px, s.top_px, s.left_px + s.width_px, s.top_px + s.height_px),
            )
        )

    for kind, idx, cid, gcid, ebox in elements:
        # 1) Section ancestor containment
        if has_design_doc and cid:
            path = _find_path_to_leaf(spec.design_doc.layout, cid, [])
            if path is not None:
                ancestor = _ancestor_section_bbox(path)
                if ancestor is not None:
                    ancestor_id, abox = ancestor
                    diffs = _outside(ebox, abox, _TOLERANCE_PX)
                    if diffs is not None:
                        result.violations.append(
                            LintViolation(
                                rule="element-out-of-section",
                                severity="error",
                                message=(
                                    f"{kind}#{idx} (component_id={cid!r}) 가 조상 섹션 "
                                    f"{ancestor_id!r} bbox 를 벗어남 — "
                                    f"각 섹션 안의 element 좌표는 섹션 경계를 넘으면 안 됩니다."
                                ),
                                element_index=idx,
                                element_type=kind,
                                current_value={
                                    "ancestor_section": ancestor_id,
                                    "section_bbox": list(abox),
                                    "element_bbox": list(ebox),
                                    "outside_px": diffs,
                                },
                                expected=f"element bbox 는 ancestor section bbox 안 (tolerance ±{_TOLERANCE_PX:.0f}px)",
                            )
                        )

        # 2) Grid cell containment (informational warning when design_doc is also present)
        if has_grid_plan and gcid:
            cell_bbox = _grid_cell_estimated_bbox(spec, gcid)
            if cell_bbox is not None:
                # cell 추정 bbox 는 region 분할 가정에 의존하므로 임계값을 더 크게.
                diffs = _outside(ebox, cell_bbox, _TOLERANCE_PX * 2)
                if diffs is not None:
                    result.violations.append(
                        LintViolation(
                            rule="element-out-of-grid-cell",
                            severity="warning",
                            message=(
                                f"{kind}#{idx} (grid_cell={gcid!r}) 가 cell 의 estimated "
                                "bbox 를 벗어남. design_doc.layout 의 cell_id 매칭 노드 "
                                "bbox 가 더 정확한 정답일 수 있습니다."
                            ),
                            element_index=idx,
                            element_type=kind,
                            current_value={
                                "grid_cell": gcid,
                                "estimated_cell_bbox": list(cell_bbox),
                                "element_bbox": list(ebox),
                                "outside_px": diffs,
                            },
                            expected=f"element bbox 는 cell estimated bbox 안 (tolerance ±{_TOLERANCE_PX * 2:.0f}px)",
                        )
                    )
