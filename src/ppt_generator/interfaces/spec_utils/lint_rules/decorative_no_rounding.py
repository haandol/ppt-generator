"""decorative-no-rounding: 장식 요소(꾸밈선)에 라운딩이 설정되면 위반."""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)


def check_decorative_no_rounding(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, shape in enumerate(spec.shapes):
        if not is_decorative(shape):
            continue
        if shape.corner_radius_px is not None and shape.corner_radius_px > 0:
            result.violations.append(
                LintViolation(
                    rule="decorative-no-rounding",
                    severity="warning",
                    message=(
                        f"장식 요소에 corner_radius_px={shape.corner_radius_px}가 "
                        f"설정됨 — 꾸밈선은 라운딩 없이 직선이어야 합니다"
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value=shape.corner_radius_px,
                    expected="corner_radius_px=None 또는 0",
                )
            )
