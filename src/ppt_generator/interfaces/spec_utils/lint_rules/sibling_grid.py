"""sibling-grid-uniformity / grid-cell-uniformity: 같은 row/column cell 의 크기 균일성 검사.

 이후 두 가지 모드로 동작한다.

1) grid_plan 있는 경우 (grid-cell-uniformity 모드):
   grid_plan.cells 의 (row, col, row_span, col_span) 을 신뢰하여, 같은 row 의
   cell 들에 매핑된 element bbox 들이 같은 height 를, 같은 column 의 cell 들에
   매핑된 element bbox 들이 같은 width 를 갖는지 검사한다. row_span/col_span 이
   다른 cell 끼리는 비교에서 제외해 의도된 비대칭은 허용한다.

2) grid_plan 없는 경우 (legacy sibling-grid-uniformity 모드, imported PPTX 등):
   shape 좌표만으로 같은 row/column 그룹을 추정해 균일성을 검사한다 (기존 동작).

판정 (legacy):
- 같은 row: top 차이 ≤ _ROW_TOLERANCE_PX, x 범위가 서로 겹치지 않음
- 같은 column: left 차이 ≤ _COL_TOLERANCE_PX, y 범위가 서로 겹치지 않음
- 카드 후보: shape_type in {rectangle, rounded_rectangle} + fill_color 보유 + 텍스트 보유

3개 이상의 카드가 같은 row/column 에 있을 때만 legacy 검사 (2개는 의도적 비대칭일
수 있어 false positive 비용이 큼).
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

_ROW_TOLERANCE_PX = 8.0  # 같은 row 로 인정할 top 차이
_COL_TOLERANCE_PX = 8.0  # 같은 column 으로 인정할 left 차이
_SIZE_TOLERANCE_PX = 4.0  # 균일 판정 시 허용 오차
_MIN_GROUP_SIZE = 3  # 이 개수 이상 모여있을 때만 검사

_CARD_SHAPE_TYPES = {"rectangle", "rounded_rectangle"}


def _has_text(shape: PptxShape) -> bool:
    if shape.text and shape.text.strip():
        return True
    return any(run.text.strip() for para in shape.paragraphs for run in para.runs)


def _is_card(shape: PptxShape) -> bool:
    if shape.shape_type not in _CARD_SHAPE_TYPES:
        return False
    if not shape.fill_color:
        return False
    return _has_text(shape)


def _ranges_overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    return a_min < b_max and b_min < a_max


def _group_by(
    cards: list[tuple[int, PptxShape]],
    axis: str,
    tolerance: float,
) -> list[list[tuple[int, PptxShape]]]:
    """axis 축(top 또는 left) 값이 tolerance 안에 있는 카드끼리 그룹핑."""
    sorted_cards = sorted(
        cards, key=lambda pair: pair[1].top_px if axis == "top" else pair[1].left_px
    )
    groups: list[list[tuple[int, PptxShape]]] = []
    for idx, shape in sorted_cards:
        val = shape.top_px if axis == "top" else shape.left_px
        placed = False
        for g in groups:
            head_val = g[0][1].top_px if axis == "top" else g[0][1].left_px
            if abs(val - head_val) <= tolerance:
                g.append((idx, shape))
                placed = True
                break
        if not placed:
            groups.append([(idx, shape)])
    return groups


def _check_horizontal_separation(group: list[tuple[int, PptxShape]]) -> bool:
    """같은 row 그룹: 서로 x 범위가 겹치지 않아야 진짜 sibling row."""
    sorted_g = sorted(group, key=lambda p: p[1].left_px)
    for (_, a), (_, b) in zip(sorted_g, sorted_g[1:]):
        a_right = a.left_px + abs(a.width_px)
        if a_right > b.left_px + 0.5:
            return False
    return True


def _check_vertical_separation(group: list[tuple[int, PptxShape]]) -> bool:
    """같은 column 그룹: 서로 y 범위가 겹치지 않아야 진짜 sibling column."""
    sorted_g = sorted(group, key=lambda p: p[1].top_px)
    for (_, a), (_, b) in zip(sorted_g, sorted_g[1:]):
        a_bottom = a.top_px + abs(a.height_px)
        if a_bottom > b.top_px + 0.5:
            return False
    return True


def check_sibling_grid(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    if spec.grid_plan is not None and spec.grid_plan.cells:
        _check_grid_cell_uniformity(spec, result)
        return

    cards: list[tuple[int, PptxShape]] = [
        (idx, s) for idx, s in enumerate(spec.shapes) if _is_card(s)
    ]
    if len(cards) < _MIN_GROUP_SIZE:
        return

    _check_row_height_uniformity(cards, result)
    _check_column_width_uniformity(cards, result)


def _check_grid_cell_uniformity(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    """grid_plan 기반: 같은 row 의 cell 끼리 height, 같은 column 끼리 width 비교."""
    plan = spec.grid_plan
    assert plan is not None

    # cell id -> 매핑된 element 의 (left, top, width, height) 대표값
    cell_bbox: dict[str, tuple[float, float, float, float]] = {}
    for sh in spec.shapes:
        if sh.grid_cell and sh.grid_cell not in cell_bbox:
            cell_bbox[sh.grid_cell] = (
                sh.left_px,
                sh.top_px,
                abs(sh.width_px),
                abs(sh.height_px),
            )
    for tb in spec.textboxes:
        if tb.grid_cell and tb.grid_cell not in cell_bbox:
            cell_bbox[tb.grid_cell] = (
                tb.left_px,
                tb.top_px,
                abs(tb.width_px),
                abs(tb.height_px),
            )

    # row 별 그룹: 같은 region + 같은 row + 같은 row_span
    by_row: dict[tuple[str, int, int], list[tuple[str, int]]] = {}
    by_col: dict[tuple[str, int, int], list[tuple[str, int]]] = {}
    for c in plan.cells:
        if c.id not in cell_bbox:
            continue
        by_row.setdefault((c.region, c.row, c.row_span), []).append((c.id, c.col))
        by_col.setdefault((c.region, c.col, c.col_span), []).append((c.id, c.row))

    for (region, row, row_span), members in by_row.items():
        if len(members) < 2:
            continue
        heights = [cell_bbox[cid][3] for cid, _ in members]
        min_h, max_h = min(heights), max(heights)
        if max_h - min_h <= _SIZE_TOLERANCE_PX:
            continue
        cell_ids = [cid for cid, _ in members]
        result.violations.append(
            LintViolation(
                rule="grid-cell-uniformity",
                severity="warning",
                message=(
                    f"같은 row(region={region}, row={row}, row_span={row_span}) "
                    f"cell {cell_ids} 의 height 가 불균일 "
                    f"(min={min_h:.0f}, max={max_h:.0f}, 차이 {max_h - min_h:.0f}px "
                    f"> 허용 {_SIZE_TOLERANCE_PX:.0f}px)"
                ),
                element_index=-1,
                element_type="slide",
                current_value={
                    "cells": cell_ids,
                    "axis": "row",
                    "dimension": "height",
                    "heights": [round(h, 1) for h in heights],
                },
                expected=(
                    f"row peer cell 의 height 가 {_SIZE_TOLERANCE_PX:.0f}px 이내"
                ),
            )
        )

    for (region, col, col_span), members in by_col.items():
        if len(members) < 2:
            continue
        widths = [cell_bbox[cid][2] for cid, _ in members]
        min_w, max_w = min(widths), max(widths)
        if max_w - min_w <= _SIZE_TOLERANCE_PX:
            continue
        cell_ids = [cid for cid, _ in members]
        result.violations.append(
            LintViolation(
                rule="grid-cell-uniformity",
                severity="warning",
                message=(
                    f"같은 column(region={region}, col={col}, col_span={col_span}) "
                    f"cell {cell_ids} 의 width 가 불균일 "
                    f"(min={min_w:.0f}, max={max_w:.0f}, 차이 {max_w - min_w:.0f}px "
                    f"> 허용 {_SIZE_TOLERANCE_PX:.0f}px)"
                ),
                element_index=-1,
                element_type="slide",
                current_value={
                    "cells": cell_ids,
                    "axis": "column",
                    "dimension": "width",
                    "widths": [round(w, 1) for w in widths],
                },
                expected=(
                    f"column peer cell 의 width 가 {_SIZE_TOLERANCE_PX:.0f}px 이내"
                ),
            )
        )


def _check_row_height_uniformity(
    cards: list[tuple[int, PptxShape]],
    result: SlideLintResult,
) -> None:
    row_groups = _group_by(cards, axis="top", tolerance=_ROW_TOLERANCE_PX)
    for group in row_groups:
        if len(group) < _MIN_GROUP_SIZE:
            continue
        if not _check_horizontal_separation(group):
            continue
        heights = [abs(s.height_px) for _, s in group]
        min_h, max_h = min(heights), max(heights)
        if max_h - min_h <= _SIZE_TOLERANCE_PX:
            continue
        indices = [idx for idx, _ in group]
        result.violations.append(
            LintViolation(
                rule="sibling-grid-uniformity",
                severity="warning",
                message=(
                    f"같은 row 카드 {indices} 의 height 가 불균일 "
                    f"(min={min_h:.0f}, max={max_h:.0f}, 차이 {max_h - min_h:.0f}px "
                    f"> 허용 {_SIZE_TOLERANCE_PX:.0f}px)"
                ),
                element_index=indices[0],
                element_type="shape",
                current_value={
                    "indices": indices,
                    "axis": "row",
                    "dimension": "height",
                    "heights": [round(h, 1) for h in heights],
                },
                expected=(
                    f"모든 row peer 의 height 가 {_SIZE_TOLERANCE_PX:.0f}px 이내"
                ),
            )
        )


def _check_column_width_uniformity(
    cards: list[tuple[int, PptxShape]],
    result: SlideLintResult,
) -> None:
    col_groups = _group_by(cards, axis="left", tolerance=_COL_TOLERANCE_PX)
    for group in col_groups:
        if len(group) < _MIN_GROUP_SIZE:
            continue
        if not _check_vertical_separation(group):
            continue
        widths = [abs(s.width_px) for _, s in group]
        min_w, max_w = min(widths), max(widths)
        if max_w - min_w <= _SIZE_TOLERANCE_PX:
            continue
        indices = [idx for idx, _ in group]
        result.violations.append(
            LintViolation(
                rule="sibling-grid-uniformity",
                severity="warning",
                message=(
                    f"같은 column 카드 {indices} 의 width 가 불균일 "
                    f"(min={min_w:.0f}, max={max_w:.0f}, 차이 {max_w - min_w:.0f}px "
                    f"> 허용 {_SIZE_TOLERANCE_PX:.0f}px)"
                ),
                element_index=indices[0],
                element_type="shape",
                current_value={
                    "indices": indices,
                    "axis": "column",
                    "dimension": "width",
                    "widths": [round(w, 1) for w in widths],
                },
                expected=(
                    f"모든 column peer 의 width 가 {_SIZE_TOLERANCE_PX:.0f}px 이내"
                ),
            )
        )
