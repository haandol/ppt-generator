"""sibling-gap-minimum: 수평/수직으로 인접한 형제 shape 간 최소 간격 검사.

텍스트 있는 shape 두 개가 가로 또는 세로로 이웃해 있으면서 둘 사이 간격이
MIN_GAP 미만이면 경고. line shape 가 중간에 끼어 있어도 두께가 얇으면(3px 이하)
실질적 0 간격으로 간주한다 (스텝 카드 간 화살표는 시각적으로 카드를 분리하지 못함).

HTML 렌더 결과에서 박스들이 "붙어 있거나 겹쳐 있는 것처럼" 보이는 대표적 원인.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)

_MIN_GAP_PX = 8.0  # 형제 shape 사이 최소 간격 (시각적 분리 필요)
_LINE_THIN_PX = 3.0  # 이 두께 이하의 line 은 "공간을 만들지 못하는" 장식으로 간주


def _has_text(shape: PptxShape) -> bool:
    if shape.text and shape.text.strip():
        return True
    return any(run.text.strip() for para in shape.paragraphs for run in para.runs)


def _is_thin_line(shape: PptxShape) -> bool:
    if shape.shape_type != "line":
        return False
    h = abs(shape.height_px)
    w = abs(shape.width_px)
    return min(h, w) <= _LINE_THIN_PX


def _overlaps_range(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    """두 구간의 중첩 길이. 0 이하면 겹치지 않음."""
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


def check_sibling_gap(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    # 텍스트가 있는 non-decorative shape 만 대상
    targets: list[tuple[int, PptxShape, float, float, float, float]] = []
    for idx, shape in enumerate(spec.shapes):
        if is_decorative(shape):
            continue
        if _is_thin_line(shape):
            continue
        if not _has_text(shape) and shape.shape_type not in {
            "rounded_rectangle",
            "rectangle",
        }:
            # 텍스트도 없고 카드 모양도 아니면 검사 제외 (아이콘/배경 등)
            continue
        left = shape.left_px
        right = left + abs(shape.width_px)
        top = shape.top_px
        bottom = top + abs(shape.height_px)
        targets.append((idx, shape, left, right, top, bottom))

    reported: set[tuple[int, int, str]] = set()

    for i, (idx_a, _sa, la, ra, ta, ba) in enumerate(targets):
        for idx_b, _sb, lb, rb, tb_, bb in targets[i + 1 :]:
            # 수평 이웃: y 범위가 상당히 겹치고 x 기준 gap
            v_overlap = _overlaps_range(ta, ba, tb_, bb)
            min_height = min(ba - ta, bb - tb_)
            if v_overlap > min_height * 0.5:  # y가 절반 이상 겹치면 수평 이웃
                if la < lb:
                    gap = lb - ra
                else:
                    gap = la - rb
                if -0.5 <= gap < _MIN_GAP_PX:
                    key = (min(idx_a, idx_b), max(idx_a, idx_b), "horizontal")
                    if key in reported:
                        continue
                    reported.add(key)
                    result.violations.append(
                        LintViolation(
                            rule="sibling-gap-minimum",
                            severity="warning",
                            message=(
                                f"shape[{idx_a}] 와 shape[{idx_b}] 가 수평으로 "
                                f"{gap:.0f}px 간격으로 붙음 (>={_MIN_GAP_PX:.0f}px 필요)"
                            ),
                            element_index=idx_a,
                            element_type="shape",
                            current_value={
                                "other_index": idx_b,
                                "direction": "horizontal",
                                "gap_px": round(gap, 1),
                            },
                            expected=f">= {_MIN_GAP_PX:.0f}px",
                        )
                    )
                continue

            # 수직 이웃: x 범위가 상당히 겹치고 y 기준 gap
            h_overlap = _overlaps_range(la, ra, lb, rb)
            min_width = min(ra - la, rb - lb)
            if h_overlap > min_width * 0.5:
                if ta < tb_:
                    gap = tb_ - ba
                else:
                    gap = ta - bb
                if -0.5 <= gap < _MIN_GAP_PX:
                    key = (min(idx_a, idx_b), max(idx_a, idx_b), "vertical")
                    if key in reported:
                        continue
                    reported.add(key)
                    result.violations.append(
                        LintViolation(
                            rule="sibling-gap-minimum",
                            severity="warning",
                            message=(
                                f"shape[{idx_a}] 와 shape[{idx_b}] 가 수직으로 "
                                f"{gap:.0f}px 간격으로 붙음 (>={_MIN_GAP_PX:.0f}px 필요)"
                            ),
                            element_index=idx_a,
                            element_type="shape",
                            current_value={
                                "other_index": idx_b,
                                "direction": "vertical",
                                "gap_px": round(gap, 1),
                            },
                            expected=f">= {_MIN_GAP_PX:.0f}px",
                        )
                    )
