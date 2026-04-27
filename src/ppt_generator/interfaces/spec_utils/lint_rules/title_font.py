"""title-font-min: 슬라이드 제목(첫 번째 textbox) 최소 폰트 검사."""

from __future__ import annotations

from ppt_generator.interfaces.constants import SLIDE_TITLE_FONT_MIN_PT
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

_SLIDE_TITLE_MIN = SLIDE_TITLE_FONT_MIN_PT  # 24
_TITLE_SLIDE_TITLE_MIN = 36


def check_title_font(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, tb in enumerate(spec.textboxes):
        has_text = any(run.text.strip() for para in tb.paragraphs for run in para.runs)
        if not has_text:
            continue

        if spec.slide_type in ("title", "closing"):
            min_pt = _TITLE_SLIDE_TITLE_MIN
        else:
            min_pt = _SLIDE_TITLE_MIN

        for para in tb.paragraphs:
            for run in para.runs:
                if run.font_size_pt is not None and run.font_size_pt < min_pt:
                    result.violations.append(
                        LintViolation(
                            rule="title-font-min",
                            severity="error",
                            message=(
                                f"슬라이드 제목 폰트 {run.font_size_pt}pt가 "
                                f"최소 {min_pt}pt 미만입니다"
                            ),
                            element_index=idx,
                            element_type="textbox",
                            current_value=run.font_size_pt,
                            expected=f">= {min_pt}pt",
                        )
                    )
        break  # 첫 번째 텍스트 있는 textbox만 검사
