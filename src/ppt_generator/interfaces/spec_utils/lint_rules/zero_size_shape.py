"""zero-size-shape: 폭 또는 높이가 0 (또는 1px 이하) 인 shape 감지.

화살표/연결선을 의도했으나 height=0 또는 width=0 으로 설정되어 실제로는
렌더링되지 않는 경우가 잦다. line shape 도 두 끝점 좌표가 사실상 같으면
그려지지 않으므로 같이 잡는다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

_MIN_VISIBLE_PX = 1.0  # 이 값 이하면 "보이지 않음" 으로 간주


def check_zero_size_shape(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, shape in enumerate(spec.shapes):
        w = abs(shape.width_px)
        h = abs(shape.height_px)

        if shape.shape_type == "line":
            # line 은 한 축이 0이어도 다른 축이 충분하면 선으로 그려질 수 있음
            longest = max(w, h)
            if longest <= _MIN_VISIBLE_PX:
                result.violations.append(
                    LintViolation(
                        rule="zero-size-shape",
                        severity="warning",
                        message=(
                            f"line shape[{idx}] 의 두 끝점이 사실상 같아 "
                            f"렌더링되지 않음 (width={w:.0f}, height={h:.0f})"
                        ),
                        element_index=idx,
                        element_type="shape",
                        current_value={"width_px": w, "height_px": h},
                        expected=f"width 또는 height > {_MIN_VISIBLE_PX:.0f}px",
                    )
                )
            continue

        if w <= _MIN_VISIBLE_PX or h <= _MIN_VISIBLE_PX:
            result.violations.append(
                LintViolation(
                    rule="zero-size-shape",
                    severity="warning",
                    message=(
                        f"shape[{idx}] ({shape.shape_type}) 가 "
                        f"{w:.0f}x{h:.0f}px 로 렌더링되지 않음"
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={"width_px": w, "height_px": h},
                    expected=f"width, height 모두 > {_MIN_VISIBLE_PX:.0f}px",
                )
            )
