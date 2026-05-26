"""grid-section-link: Layout(GridPlan) ↔ Section(design_doc.layout) link 정합성.

결정 13c (cross-layer rule):
  - grid-section-link-orphan-cell: design_doc.layout 트리의 어느 노드 cell_id 가
    GridPlan.cells.id 집합에 존재하지 않음.

design_doc.layout 의 `cell_id` 는 Section 영역이 어느 격자 cell 위에 놓이는지
명시하는 Layout↔Section 단방향 link 다. 깨지면 modify 시 cell 정렬이 무너지고
사용자가 "좌측 셀 영역" 같은 표현으로 부분 수정을 요청할 때 LLM 이 cell 을
역추적하지 못한다.

design_doc 또는 grid_plan 이 None 인 슬라이드 (title/closing/imported 미-backfill)
는 검사 대상 제외 (조건부 lint, 결정 5 와 일관). cell_id 가 None 인
노드는 정상 (전역 영역, root 등) — 검사는 cell_id 가 설정된 노드에 한정.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import LayoutNode, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)


def _walk(nodes: list[LayoutNode]):
    for n in nodes:
        yield n
        yield from _walk(n.children)


def check_grid_section_link(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    if spec.design_doc is None or spec.grid_plan is None:
        return

    valid_cell_ids = {c.id for c in spec.grid_plan.cells}
    for node in _walk(spec.design_doc.layout):
        if not node.cell_id:
            continue
        if node.cell_id not in valid_cell_ids:
            result.violations.append(
                LintViolation(
                    rule="grid-section-link-orphan-cell",
                    severity="error",
                    message=(
                        f"design_doc.layout 노드 {node.id!r} 의 "
                        f"cell_id={node.cell_id!r} 가 GridPlan.cells 에 존재하지 "
                        "않습니다. GridPlan 의 cell id 와 일치하도록 수정하거나, "
                        "전역 영역이라면 cell_id 를 비우세요."
                    ),
                    element_index=-1,
                    element_type="slide",
                    current_value=node.cell_id,
                    expected=f"GridPlan.cells.id ∈ {sorted(valid_cell_ids)}",
                )
            )
