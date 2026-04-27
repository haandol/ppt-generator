"""canvas-overflow: 요소가 캔버스(1280x720) 밖으로 나가는지 검사."""

from __future__ import annotations

from ppt_generator.interfaces.constants import SLIDES_HEIGHT_PX, SLIDES_WIDTH_PX
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)

_CANVAS_W = SLIDES_WIDTH_PX  # 1280
_CANVAS_H = SLIDES_HEIGHT_PX  # 720


def check_canvas_overflow(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, tb in enumerate(spec.textboxes):
        right = tb.left_px + tb.width_px
        bottom = tb.top_px + tb.height_px
        if tb.left_px < 0 or tb.top_px < 0 or right > _CANVAS_W or bottom > _CANVAS_H:
            result.violations.append(
                LintViolation(
                    rule="canvas-overflow",
                    severity="warning",
                    message=(
                        f"textbox가 캔버스 경계를 벗어남 "
                        f"(left={tb.left_px}, top={tb.top_px}, "
                        f"right={right}, bottom={bottom})"
                    ),
                    element_index=idx,
                    element_type="textbox",
                    current_value={
                        "left": tb.left_px,
                        "top": tb.top_px,
                        "right": right,
                        "bottom": bottom,
                    },
                    expected=f"0~{_CANVAS_W} x 0~{_CANVAS_H}",
                )
            )

    for idx, shape in enumerate(spec.shapes):
        if is_decorative(shape):
            continue
        right = shape.left_px + abs(shape.width_px)
        bottom = shape.top_px + abs(shape.height_px)
        if (
            shape.left_px < 0
            or shape.top_px < 0
            or right > _CANVAS_W
            or bottom > _CANVAS_H
        ):
            result.violations.append(
                LintViolation(
                    rule="canvas-overflow",
                    severity="warning",
                    message=(
                        f"shape가 캔버스 경계를 벗어남 "
                        f"(left={shape.left_px}, top={shape.top_px}, "
                        f"right={right}, bottom={bottom})"
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={
                        "left": shape.left_px,
                        "top": shape.top_px,
                        "right": right,
                        "bottom": bottom,
                    },
                    expected=f"0~{_CANVAS_W} x 0~{_CANVAS_H}",
                )
            )
