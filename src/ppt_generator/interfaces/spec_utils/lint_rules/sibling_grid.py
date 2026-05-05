"""sibling-grid-uniformity: 같은 row/column 에 있는 카드 shape 들의 크기 균일성 검사.

같은 row 에 나란히 배치된 카드(fill_color + 텍스트 보유) 들끼리는 height 가,
같은 column 에 세로로 쌓인 카드들끼리는 width 가 균일해야 그리드 레이아웃이
깨지지 않는다. LLM 이 컨텐츠 길이에 맞춰 카드 크기를 제각기 다르게 만드는
흔한 패턴을 잡는다.

판정:
- 같은 row: top 차이 ≤ _ROW_TOLERANCE_PX, x 범위가 서로 겹치지 않음
- 같은 column: left 차이 ≤ _COL_TOLERANCE_PX, y 범위가 서로 겹치지 않음
- 카드 후보: shape_type in {rectangle, rounded_rectangle} + fill_color 보유 + 텍스트 보유

3개 이상의 카드가 같은 row/column 에 있을 때만 검사 (2개는 의도적 비대칭일
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
    cards: list[tuple[int, PptxShape]] = [
        (idx, s) for idx, s in enumerate(spec.shapes) if _is_card(s)
    ]
    if len(cards) < _MIN_GROUP_SIZE:
        return

    _check_row_height_uniformity(cards, result)
    _check_column_width_uniformity(cards, result)


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
