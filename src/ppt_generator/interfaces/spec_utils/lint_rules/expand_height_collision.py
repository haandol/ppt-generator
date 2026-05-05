"""expand-height-collision: autofit_mode='expand_height' shape 가 텍스트 확장 시
아래 형제 요소(shape/textbox)와 세로로 겹치는지 검사.

HTML 렌더러는 autofit_mode='expand_height' 를 `min-height` 로 변환하므로,
텍스트가 선언된 height_px 를 넘치면 박스가 아래로 늘어나 다음 요소와 실제 충돌한다.
기존 text-overflow 규칙은 "필요 높이 > 고정 높이" 만 경고하고 실제 이웃과의
충돌은 확인하지 않으므로, 이 규칙이 그 공백을 메운다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec, PptxTextBox
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)
from ppt_generator.interfaces.text_measurement import (
    calculate_required_height,
    calculate_required_height_simple_text,
)

_EXPAND_TOLERANCE_PX = 2.0  # 2px 이하 겹침은 렌더 반올림 허용


def _required_shape_height(shape: PptxShape) -> float:
    pad_l = shape.padding_left_px or 0.0
    pad_r = shape.padding_right_px or 0.0
    pad_t = shape.padding_top_px or 0.0
    pad_b = shape.padding_bottom_px or 0.0

    has_paragraphs = any(
        run.text.strip() for para in shape.paragraphs for run in para.runs
    )
    if has_paragraphs:
        return calculate_required_height(
            shape.paragraphs,
            abs(shape.width_px),
            line_spacing_pt=shape.line_spacing_pt,
            padding_left_px=pad_l,
            padding_right_px=pad_r,
            padding_top_px=pad_t,
            padding_bottom_px=pad_b,
        )
    if shape.text and shape.text.strip():
        font_pt = shape.text_size_pt or 16
        return calculate_required_height_simple_text(
            shape.text,
            font_pt,
            abs(shape.width_px),
            line_spacing_pt=shape.line_spacing_pt,
            padding_left_px=pad_l,
            padding_right_px=pad_r,
            padding_top_px=pad_t,
            padding_bottom_px=pad_b,
        )
    return 0.0


def _horizontally_overlaps(
    a_left: float, a_right: float, b_left: float, b_right: float
) -> bool:
    return a_left < b_right and b_left < a_right


def check_expand_height_collision(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    """autofit_mode='expand_height' shape 가 텍스트 확장 시 아래 요소와 겹치면 위반."""
    neighbors: list[tuple[str, int, float, float, float, float]] = []
    # (kind, idx, left, right, top, bottom)
    for idx, tb in enumerate(spec.textboxes):
        neighbors.append(
            (
                "textbox",
                idx,
                tb.left_px,
                tb.left_px + tb.width_px,
                tb.top_px,
                tb.top_px + tb.height_px,
            )
        )
    for idx, shape in enumerate(spec.shapes):
        if is_decorative(shape):
            continue
        right = shape.left_px + abs(shape.width_px)
        bottom = shape.top_px + abs(shape.height_px)
        neighbors.append(("shape", idx, shape.left_px, right, shape.top_px, bottom))

    for idx, shape in enumerate(spec.shapes):
        if is_decorative(shape):
            continue
        autofit = getattr(shape, "autofit_mode", None)
        if autofit != "expand_height":
            continue

        required_h = _required_shape_height(shape)
        declared_h = abs(shape.height_px)
        if required_h <= declared_h:
            continue  # 확장 없음 — 충돌 위험 없음

        expanded_bottom = shape.top_px + required_h
        shape_left = shape.left_px
        shape_right = shape.left_px + abs(shape.width_px)

        for kind, nidx, n_left, n_right, n_top, _n_bottom in neighbors:
            if kind == "shape" and nidx == idx:
                continue
            if n_top <= shape.top_px:
                continue  # 아래쪽 이웃만 검사 (위로는 확장하지 않음)
            if n_top >= expanded_bottom - _EXPAND_TOLERANCE_PX:
                continue  # 확장 후에도 닿지 않음
            if not _horizontally_overlaps(shape_left, shape_right, n_left, n_right):
                continue

            overlap_px = expanded_bottom - n_top
            result.violations.append(
                LintViolation(
                    rule="expand-height-collision",
                    severity="warning",
                    message=(
                        f"shape[{idx}] (autofit=expand_height) 텍스트가 높이를 초과해 "
                        f"확장 시 아래 {kind}[{nidx}] 와 {overlap_px:.0f}px 겹침 "
                        f"(확장 bottom={expanded_bottom:.0f}, 이웃 top={n_top:.0f})"
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={
                        "required_height": round(required_h),
                        "declared_height": round(declared_h),
                        "expanded_bottom": round(expanded_bottom),
                        "neighbor_kind": kind,
                        "neighbor_index": nidx,
                        "neighbor_top": round(n_top),
                        "overlap_px": round(overlap_px),
                    },
                    expected=(
                        f"declared height >= required ({required_h:.0f}px) "
                        f"또는 아래 요소를 {required_h - declared_h:.0f}px 이상 아래로 이동"
                    ),
                )
            )
