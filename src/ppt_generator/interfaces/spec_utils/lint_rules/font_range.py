"""font-range: 모든 텍스트 폰트가 허용 범위(10~44pt) 내인지 검사."""

from __future__ import annotations

from ppt_generator.interfaces.constants import (
    PPTX_VALIDATE_FONT_MAX_PT,
    PPTX_VALIDATE_FONT_MIN_PT,
)
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

_FONT_MIN = PPTX_VALIDATE_FONT_MIN_PT  # 10
_FONT_MAX = PPTX_VALIDATE_FONT_MAX_PT  # 44


def _check_run_font(
    font_pt: int | float,
    idx: int,
    element_type: str,
    label: str,
    result: SlideLintResult,
) -> None:
    if font_pt < _FONT_MIN:
        result.violations.append(
            LintViolation(
                rule="font-range",
                severity="warning",
                message=f"{label} 폰트 {font_pt}pt가 최소 {_FONT_MIN}pt 미만입니다",
                element_index=idx,
                element_type=element_type,
                current_value=font_pt,
                expected=f"{_FONT_MIN}~{_FONT_MAX}pt",
            )
        )
    elif font_pt > _FONT_MAX:
        result.violations.append(
            LintViolation(
                rule="font-range",
                severity="warning",
                message=f"{label} 폰트 {font_pt}pt가 최대 {_FONT_MAX}pt를 초과합니다",
                element_index=idx,
                element_type=element_type,
                current_value=font_pt,
                expected=f"{_FONT_MIN}~{_FONT_MAX}pt",
            )
        )


def check_font_range(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, tb in enumerate(spec.textboxes):
        for para in tb.paragraphs:
            for run in para.runs:
                if run.font_size_pt is None or not run.text.strip():
                    continue
                _check_run_font(run.font_size_pt, idx, "textbox", "", result)

    for idx, shape in enumerate(spec.shapes):
        if shape.text_size_pt is not None:
            _check_run_font(shape.text_size_pt, idx, "shape", "shape", result)
        for para in shape.paragraphs:
            for run in para.runs:
                if run.font_size_pt is None or not run.text.strip():
                    continue
                _check_run_font(
                    run.font_size_pt, idx, "shape", "shape 내 텍스트", result
                )
