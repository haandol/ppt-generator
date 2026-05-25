"""nowrap-overflow: nowrap 으로 렌더될 paragraph 의 추정 폭이 가용 폭을 초과하는지 검사.

ADR-0017 의 nowrap 게이트 (`should_apply_nowrap_to_paragraph`) 는 PPT↔브라우저 폰트
메트릭 차이로 인한 wrap 회귀를 막기 위해 짧은 한 줄 paragraph 에 `white-space:nowrap`
을 강제 적용한다. 이 규칙은 nowrap 이 적용될 paragraph 의 추정 폭이 박스 가용 폭을
실제로 초과하는 경우, 브라우저에서 박스 좌우로 텍스트가 넘칠 수 있음을 사전에 잡는다.

ADR-0047 에서 tolerance 가 0.95 로 보수화되었으므로 정상 경로에서는 위반이 발생하지
않아야 한다. 본 규칙은 향후 tolerance 가 다시 느슨해지거나, 다른 경로로 nowrap 이
적용되는 경우의 회귀 감지가 목적이다.

bullet (`<li>`) paragraph 는 렌더러에서 nowrap 을 적용하지 않으므로 검사 대상에서
제외한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import (
    PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU,
    PX_TO_EMU,
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)
from ppt_generator.interfaces.text_measurement import (
    estimate_text_width_px,
    should_apply_nowrap_to_paragraph,
)

_SHAPE_DEFAULT_PADDING_LR_PX = PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU / PX_TO_EMU


def _paragraph_estimated_width_px(paragraph: PptxParagraph) -> float:
    total = 0.0
    for run in paragraph.runs:
        if not run.text:
            continue
        font_pt = run.font_size_pt or 16
        is_mono = run.font_family == "monospace"
        total += estimate_text_width_px(run.text, font_pt, is_mono)
    return total


def _check_paragraphs(
    paragraphs: list[PptxParagraph],
    usable_width_px: float,
    element_index: int,
    element_type: str,
    result: SlideLintResult,
) -> None:
    if usable_width_px <= 0:
        return
    for p_idx, para in enumerate(paragraphs):
        if para.bullet_level >= 0:
            # bullet 항목은 렌더러에서 nowrap 을 적용하지 않음 (ADR-0017 §4)
            continue
        if not should_apply_nowrap_to_paragraph(para, usable_width_px):
            continue
        text_width = _paragraph_estimated_width_px(para)
        if text_width <= usable_width_px:
            continue
        result.violations.append(
            LintViolation(
                rule="nowrap-overflow",
                severity="warning",
                message=(
                    f"{element_type}[{element_index}] paragraph[{p_idx}] 가 "
                    f"nowrap 으로 렌더되지만 추정 폭({text_width:.0f}px) 이 "
                    f"가용 폭({usable_width_px:.0f}px) 을 초과 — "
                    f"브라우저에서 박스 좌우로 텍스트가 넘칠 수 있음"
                ),
                element_index=element_index,
                element_type=element_type,
                current_value={
                    "paragraph_index": p_idx,
                    "estimated_width_px": round(text_width, 1),
                    "usable_width_px": round(usable_width_px, 1),
                },
                expected="nowrap paragraph 의 추정 폭이 가용 폭 이하",
            )
        )


def _textbox_usable_width(tb: PptxTextBox) -> float:
    pl = tb.padding_left_px or 0.0
    pr = tb.padding_right_px or 0.0
    return abs(tb.width_px) - pl - pr


def _shape_usable_width(shape: PptxShape) -> float:
    pl = (
        shape.padding_left_px
        if shape.padding_left_px is not None
        else _SHAPE_DEFAULT_PADDING_LR_PX
    )
    pr = (
        shape.padding_right_px
        if shape.padding_right_px is not None
        else _SHAPE_DEFAULT_PADDING_LR_PX
    )
    return abs(shape.width_px) - pl - pr


def check_nowrap_overflow(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, tb in enumerate(spec.textboxes):
        _check_paragraphs(
            paragraphs=tb.paragraphs,
            usable_width_px=_textbox_usable_width(tb),
            element_index=idx,
            element_type="textbox",
            result=result,
        )
    for idx, shape in enumerate(spec.shapes):
        if shape.shape_type == "line":
            continue
        if not shape.paragraphs:
            continue
        _check_paragraphs(
            paragraphs=shape.paragraphs,
            usable_width_px=_shape_usable_width(shape),
            element_index=idx,
            element_type="shape",
            result=result,
        )
