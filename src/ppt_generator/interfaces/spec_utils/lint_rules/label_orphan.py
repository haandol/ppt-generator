"""label-orphan: 짧은 라벨 textbox 가 어떤 박스에도 부착되지 않고 떠있는지 검사.

. 박스를 재배치할 때 'Yes', 'No' 같은 짧은 라벨 textbox 의 좌표 갱신을
빠뜨려 빈 공간에 라벨이 floating 하는 회귀를 좌표 기반으로 사전 차단한다.

라벨 정의 (모두 만족):
- 텍스트 총 길이 <= LINT_LABEL_ORPHAN_MAX_CHARS (12)
- 모든 run 중 최대 font_size_pt <= LINT_LABEL_ORPHAN_MAX_FONT_PT (14)
- height_px <= LINT_LABEL_ORPHAN_MAX_HEIGHT_PX (32)

제외 대상:
- header region cell 에 매핑된 textbox (제목)
- footer region cell 에 매핑된 textbox (페이지 라벨 등)

검사: 라벨 textbox 의 외곽 사각형이 어떤 non-decorative shape 의 외곽 사각형과
LINT_LABEL_ORPHAN_PROXIMITY_PX 이내로 가까이 있는지.
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import (
    LINT_LABEL_ORPHAN_MAX_CHARS,
    LINT_LABEL_ORPHAN_MAX_FONT_PT,
    LINT_LABEL_ORPHAN_MAX_HEIGHT_PX,
    LINT_LABEL_ORPHAN_PROXIMITY_PX,
)
from ppt_generator.interfaces.schemas import (
    GridPlan,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)


def _textbox_total_chars(tb: PptxTextBox) -> int:
    total = 0
    for para in tb.paragraphs:
        for run in para.runs:
            if run.text:
                total += len(run.text)
    return total


def _textbox_max_font_pt(tb: PptxTextBox) -> float:
    max_pt = 0.0
    for para in tb.paragraphs:
        for run in para.runs:
            if run.font_size_pt and run.font_size_pt > max_pt:
                max_pt = float(run.font_size_pt)
    return max_pt


def _is_label(tb: PptxTextBox) -> bool:
    chars = _textbox_total_chars(tb)
    if chars == 0 or chars > LINT_LABEL_ORPHAN_MAX_CHARS:
        return False
    max_pt = _textbox_max_font_pt(tb)
    if max_pt == 0 or max_pt > LINT_LABEL_ORPHAN_MAX_FONT_PT:
        return False
    if abs(tb.height_px) > LINT_LABEL_ORPHAN_MAX_HEIGHT_PX:
        return False
    return True


def _cell_region(plan: GridPlan | None, cell_id: str | None) -> str | None:
    if plan is None or cell_id is None:
        return None
    for cell in plan.cells:
        if cell.id == cell_id:
            return cell.region
    return None


def _is_attachable_shape(shape: PptxShape) -> bool:
    if shape.shape_type == "line":
        return False
    if is_decorative(shape):
        return False
    has_text = bool(shape.text and shape.text.strip()) or any(
        run.text.strip() for para in shape.paragraphs for run in para.runs
    )
    if not has_text and shape.fill_color is None:
        return False
    return True


def _bounds(
    left: float, top: float, width: float, height: float
) -> tuple[float, float, float, float]:
    return left, top, left + abs(width), top + abs(height)


def _rect_distance(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    """두 사각형 사이 최단 거리. 겹치면 0."""
    a_l, a_t, a_r, a_b = a
    b_l, b_t, b_r, b_b = b
    dx = max(b_l - a_r, a_l - b_r, 0.0)
    dy = max(b_t - a_b, a_t - b_b, 0.0)
    return (dx * dx + dy * dy) ** 0.5


def check_label_orphan(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    boxes: list[tuple[float, float, float, float]] = [
        _bounds(s.left_px, s.top_px, s.width_px, s.height_px)
        for s in spec.shapes
        if _is_attachable_shape(s)
    ]
    if not boxes:
        return

    for idx, tb in enumerate(spec.textboxes):
        if not _is_label(tb):
            continue
        region = _cell_region(spec.grid_plan, tb.grid_cell)
        if region in ("header", "footer"):
            continue
        tb_bounds = _bounds(tb.left_px, tb.top_px, tb.width_px, tb.height_px)
        nearest = min(_rect_distance(tb_bounds, b) for b in boxes)
        if nearest <= LINT_LABEL_ORPHAN_PROXIMITY_PX:
            continue
        result.violations.append(
            LintViolation(
                rule="label-orphan",
                severity="warning",
                message=(
                    f"textbox[{idx}] 라벨이 어떤 박스에서도 "
                    f"{LINT_LABEL_ORPHAN_PROXIMITY_PX:.0f}px 이내에 부착되지 않음 "
                    f"(최단 거리 {nearest:.0f}px) — 회귀 가능성"
                ),
                element_index=idx,
                element_type="textbox",
                current_value={
                    "nearest_distance_px": round(nearest, 1),
                },
                expected=(
                    f"가장 가까운 박스와 {LINT_LABEL_ORPHAN_PROXIMITY_PX:.0f}px 이내"
                ),
            )
        )
