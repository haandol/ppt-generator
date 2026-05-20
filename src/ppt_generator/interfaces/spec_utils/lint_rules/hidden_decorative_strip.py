"""hidden-decorative-strip: 장식 strip이 더 큰 카드 뒤에 가려지는지 검사.

가는 강조 바/사이드바/언더라인이 같은 좌표에 있는 더 큰 카드/컨테이너의
**뒤에** 렌더되어 화면에서 보이지 않게 되는 케이스를 차단한다.

판정 기준:
1. 후보 strip: ``is_decorative`` (텍스트 없고 한 변 ≤ 10px) 도형
2. 동일 슬라이드에서 strip의 bounding rect를 완전히 포함하는 더 큰
   sibling 도형이 존재
3. strip의 z-order가 큰 도형의 z-order보다 같거나 낮음
   (z_index가 모두 ``None`` 이면 ``shapes`` 배열의 인덱스를 z-order로 사용)
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)


def _rect(shape: PptxShape) -> tuple[float, float, float, float]:
    return (
        shape.left_px,
        shape.top_px,
        shape.left_px + shape.width_px,
        shape.top_px + shape.height_px,
    )


def _contains(outer: PptxShape, inner: PptxShape) -> bool:
    ol, ot, orx, ob = _rect(outer)
    il, it, irx, ib = _rect(inner)
    return ol <= il and ot <= it and orx >= irx and ob >= ib


def _z_key(shape: PptxShape, fallback_index: int) -> tuple[int, int]:
    """렌더 순서 키: (z_index 그룹, 배열 인덱스).

    z_index가 ``None`` 인 도형은 그룹 0(아래쪽), 명시된 도형은 그룹 1(위쪽).
    같은 그룹 안에서는 배열 인덱스가 큰 쪽이 위에 렌더된다.
    """
    if shape.z_index is None:
        return (0, fallback_index)
    return (1, shape.z_index)


def check_hidden_decorative_strip(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    shapes = spec.shapes
    for s_idx, strip in enumerate(shapes):
        if not is_decorative(strip):
            continue
        # 너무 작은 도형(점, 1×1 등)은 무시
        if strip.width_px <= 0 or strip.height_px <= 0:
            continue
        strip_z = _z_key(strip, s_idx)
        for o_idx, other in enumerate(shapes):
            if o_idx == s_idx:
                continue
            # other가 strip을 완전히 포함해야 함
            if not _contains(other, strip):
                continue
            # other가 strip보다 의미 있게 커야 함(같은 도형 사이즈는 제외)
            if other.width_px <= strip.width_px and other.height_px <= strip.height_px:
                continue
            other_z = _z_key(other, o_idx)
            if strip_z >= other_z:
                continue  # strip이 위에 있으므로 OK
            result.violations.append(
                LintViolation(
                    rule="hidden-decorative-strip",
                    severity="warning",
                    message=(
                        f"장식 strip(shape[{s_idx}], "
                        f"{strip.width_px}×{strip.height_px})가 더 큰 "
                        f"shape[{o_idx}]({other.width_px}×{other.height_px}) "
                        "뒤에 렌더되어 가려질 수 있습니다."
                    ),
                    element_index=s_idx,
                    element_type="shape",
                    current_value=strip.z_index,
                    expected=(
                        f"strip의 z_index를 shape[{o_idx}]의 z-order보다 "
                        "크게 설정하거나 shapes 배열의 더 뒤로 이동"
                    ),
                )
            )
            break  # strip 하나당 한 번만 보고
