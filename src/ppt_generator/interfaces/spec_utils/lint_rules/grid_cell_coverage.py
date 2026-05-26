"""grid-cell-coverage: 선언된 cell 의 미사용/중복 매핑 검사.

모든 textbox/shape 는 grid_cell 로 선언된 cell 을 참조해야 한다
(decorative element 는 명시적으로 null). 선언만 되고 어느 element 도 참조하지
않는 cell, 그리고 동일 cell 에 여러 element 가 매핑되어 의도치 않은 중첩이
발생하는 경우를 잡는다.

decorative element(예: 화살표, divider line) 는 grid_cell=None 이 정상이며
이 규칙에서 제외한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)


def _has_text(shape: PptxShape) -> bool:
    if shape.text and shape.text.strip():
        return True
    return any(run.text.strip() for para in shape.paragraphs for run in para.runs)


def check_grid_cell_coverage(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    plan = spec.grid_plan
    if plan is None or not plan.cells:
        return

    declared_ids = {c.id for c in plan.cells}
    used_by: dict[str, list[tuple[str, int]]] = {cid: [] for cid in declared_ids}

    for idx, tb in enumerate(spec.textboxes):
        if tb.grid_cell is None:
            result.violations.append(
                LintViolation(
                    rule="grid-cell-coverage",
                    severity="warning",
                    message=(
                        f"textbox[{idx}] 가 grid_cell 을 명시하지 않음 "
                        f"(textbox 는 항상 cell 에 매핑되어야 한다)."
                    ),
                    element_index=idx,
                    element_type="textbox",
                    current_value={"grid_cell": None},
                    expected="grid_cell 에 declared cell id 명시",
                )
            )
            continue
        if tb.grid_cell not in declared_ids:
            result.violations.append(
                LintViolation(
                    rule="grid-cell-coverage",
                    severity="error",
                    message=(
                        f"textbox[{idx}].grid_cell='{tb.grid_cell}' 는 "
                        f"grid_plan.cells 에 선언되지 않음."
                    ),
                    element_index=idx,
                    element_type="textbox",
                    current_value={"grid_cell": tb.grid_cell},
                    expected=f"declared cell id 중 하나: {sorted(declared_ids)}",
                )
            )
            continue
        used_by[tb.grid_cell].append(("textbox", idx))

    for idx, sh in enumerate(spec.shapes):
        if is_decorative(sh):
            continue
        if not _has_text(sh) and sh.fill_color is None:
            continue
        if sh.grid_cell is None:
            result.violations.append(
                LintViolation(
                    rule="grid-cell-coverage",
                    severity="warning",
                    message=(
                        f"shape[{idx}] 가 grid_cell 을 명시하지 않음 (content "
                        f"shape 은 cell 매핑 필요; decorative line/arrow 는 예외)."
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={"grid_cell": None},
                    expected="grid_cell 에 declared cell id 명시",
                )
            )
            continue
        if sh.grid_cell not in declared_ids:
            result.violations.append(
                LintViolation(
                    rule="grid-cell-coverage",
                    severity="error",
                    message=(
                        f"shape[{idx}].grid_cell='{sh.grid_cell}' 는 "
                        f"grid_plan.cells 에 선언되지 않음."
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={"grid_cell": sh.grid_cell},
                    expected=f"declared cell id 중 하나: {sorted(declared_ids)}",
                )
            )
            continue
        used_by[sh.grid_cell].append(("shape", idx))

    empty_cells = [cid for cid, refs in used_by.items() if not refs]
    if empty_cells:
        result.violations.append(
            LintViolation(
                rule="grid-cell-coverage",
                severity="warning",
                message=(
                    f"선언만 되고 어느 element 도 참조하지 않은 cell: {empty_cells}. "
                    f"불필요한 cell 은 grid_plan 에서 제거하거나 element 를 매핑하라."
                ),
                element_index=-1,
                element_type="slide",
                current_value={"empty_cells": empty_cells},
                expected="모든 declared cell 은 최소 1개 element 가 참조",
            )
        )

    for cid, refs in used_by.items():
        if len(refs) <= 1:
            continue
        text_refs = [r for r in refs if r[0] == "textbox"]
        shape_refs = [r for r in refs if r[0] == "shape"]
        if len(shape_refs) > 1 and len(text_refs) == 0:
            result.violations.append(
                LintViolation(
                    rule="grid-cell-coverage",
                    severity="warning",
                    message=(
                        f"cell '{cid}' 에 shape 이 {len(shape_refs)}개 매핑됨 "
                        f"({shape_refs}). 카드 + 보조 라벨 외에는 cell 분리 검토."
                    ),
                    element_index=shape_refs[0][1],
                    element_type="shape",
                    current_value={"cell": cid, "refs": refs},
                    expected="동일 cell 에는 의도된 컨테이너+라벨 조합만 허용",
                )
            )
