"""row-autofit-consistency: 같은 행(row aligned) 카드들의 autofit_mode 충돌 검사.

같은 행에 있는 (= 같은 top_px / 같은 height_px / 인접한 left_px 분포) 카드들이
서로 다른 autofit_mode 를 갖거나, ``expand_height`` 를 사용하면 텍스트 양에
따라 카드 높이가 달라져 행 정렬이 시각적으로 깨진다.

판정 기준:

1. row aligned 그룹 식별: ``top_px`` 와 ``height_px`` 가 모두 ±2px 이내로 같은
   비-장식 shape 집단 (≥ 2개) 을 같은 행으로 본다.
2. 같은 행 안에서 ``autofit_mode`` 가 다르면 위반 (`row-autofit-mismatch`).
3. 같은 행에서 모두 ``expand_height`` 인 경우, 텍스트 양 차이로 카드 높이가
   서로 달라질 수 있으므로 위반 (`row-expand-height-unsafe`).
   같은 행은 ``shrink_text`` 로 통일하는 것이 안전하다.
"""

from __future__ import annotations

from collections import defaultdict

from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)

_ROW_TOL_PX = 2.0


def _row_key(shape: PptxShape) -> tuple[int, int]:
    """같은 행 그룹화용 (top, height) 양자화 키."""
    return (
        round(shape.top_px / _ROW_TOL_PX),
        round(shape.height_px / _ROW_TOL_PX),
    )


def check_row_autofit_consistency(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    rows: dict[tuple[int, int], list[tuple[int, PptxShape]]] = defaultdict(list)
    for idx, shape in enumerate(spec.shapes):
        if is_decorative(shape):
            continue
        # 텍스트가 없는 도형(순수 배경/strip)은 제외
        has_text = bool(shape.text and shape.text.strip()) or any(
            run.text.strip() for para in shape.paragraphs for run in para.runs
        )
        if not has_text:
            continue
        rows[_row_key(shape)].append((idx, shape))

    for members in rows.values():
        if len(members) < 2:
            continue

        autofit_modes = {(idx, s.autofit_mode) for idx, s in members}
        unique_modes = {m for _, m in autofit_modes}

        # 1) row 내 mode 불일치
        if len(unique_modes) > 1:
            for idx, shape in members:
                result.violations.append(
                    LintViolation(
                        rule="row-autofit-mismatch",
                        severity="warning",
                        message=(
                            f"shape[{idx}] (top={shape.top_px}, height={shape.height_px}) "
                            f"autofit_mode={shape.autofit_mode!r} 가 같은 행의 "
                            f"다른 카드와 불일치 ({sorted(unique_modes)})"
                        ),
                        element_index=idx,
                        element_type="shape",
                        current_value=shape.autofit_mode,
                        expected=(
                            "같은 행의 모든 카드는 동일한 autofit_mode 사용 "
                            "(권장: shrink_text)"
                        ),
                    )
                )
            continue  # mismatch 보고했으면 unsafe 룰은 생략

        # 2) row 전체가 expand_height — 텍스트 양 차이로 정렬 깨질 위험
        if unique_modes == {"expand_height"}:
            for idx, shape in members:
                result.violations.append(
                    LintViolation(
                        rule="row-expand-height-unsafe",
                        severity="warning",
                        message=(
                            f"shape[{idx}] 가 같은 행 카드와 모두 expand_height — "
                            "텍스트 양에 따라 카드 높이가 달라져 행 정렬이 깨질 수 있음"
                        ),
                        element_index=idx,
                        element_type="shape",
                        current_value="expand_height",
                        expected="같은 행 카드는 shrink_text 로 고정 높이 사용 권장",
                    )
                )
