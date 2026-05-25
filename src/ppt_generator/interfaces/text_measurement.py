"""폰트 메트릭 기반 텍스트 크기 추정 모듈.

외부 의존성 없이 순수 함수로 구현.
CJK/한글 전각 문자와 Latin 반각 문자의 폭 차이를 반영하여
텍스트 줄바꿈 후 필요 높이를 계산한다.
"""

from __future__ import annotations

import math
import unicodedata

from ppt_generator.interfaces.constants import (
    TEXT_MEASURE_BULLET_INDENT_L0_PX,
    TEXT_MEASURE_BULLET_INDENT_L1_PX,
    TEXT_MEASURE_CJK_WIDTH_RATIO,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX,
    TEXT_MEASURE_LATIN_WIDTH_RATIO,
    TEXT_MEASURE_MONOSPACE_WIDTH_RATIO,
    TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO,
    TEXT_MEASURE_PX_PER_PT,
)


def _is_wide_char(ch: str) -> bool:
    """CJK/전각 문자 여부를 판별한다."""
    width = unicodedata.east_asian_width(ch)
    return width in ("W", "F")


def estimate_text_width_px(
    text: str,
    font_size_pt: float,
    is_monospace: bool = False,
) -> float:
    """텍스트의 렌더링 폭(px)을 추정한다.

    - CJK/한글: font_size_pt × PX_PER_PT × CJK_WIDTH_RATIO
    - Latin/숫자: font_size_pt × PX_PER_PT × LATIN_WIDTH_RATIO
    - Monospace: font_size_pt × PX_PER_PT × MONOSPACE_WIDTH_RATIO (모든 글자 동일)
    """
    if not text:
        return 0.0

    base = font_size_pt * TEXT_MEASURE_PX_PER_PT
    total = 0.0

    for ch in text:
        if is_monospace:
            total += base * TEXT_MEASURE_MONOSPACE_WIDTH_RATIO
        elif _is_wide_char(ch):
            total += base * TEXT_MEASURE_CJK_WIDTH_RATIO
        else:
            total += base * TEXT_MEASURE_LATIN_WIDTH_RATIO

    return total


def estimate_paragraph_wrapped_lines(
    paragraph: "PptxParagraph",
    available_width_px: float,
) -> int:
    """paragraph의 run들을 이어 붙여 available_width_px 안에서 몇 줄로 줄바꿈되는지 계산한다.

    최소 1줄 반환.
    """
    from ppt_generator.interfaces.schemas import PptxParagraph  # noqa: F811

    if available_width_px <= 0:
        return 1

    total_width = 0.0
    has_text = False

    for run in paragraph.runs:
        if not run.text:
            continue
        has_text = True
        font_pt = run.font_size_pt or 16
        is_mono = run.font_family == "monospace"
        total_width += estimate_text_width_px(run.text, font_pt, is_mono)

    if not has_text:
        return 1

    return max(1, math.ceil(total_width / available_width_px))


def _get_bullet_indent_px(bullet_level: int) -> float:
    """bullet_level에 따른 indent px를 반환한다."""
    if bullet_level == 0:
        return TEXT_MEASURE_BULLET_INDENT_L0_PX
    elif bullet_level >= 1:
        return TEXT_MEASURE_BULLET_INDENT_L1_PX
    return 0.0


def calculate_required_height(
    paragraphs: list["PptxParagraph"],
    box_width_px: float,
    line_spacing_pt: float | None = None,
    padding_left_px: float = 0.0,
    padding_right_px: float = 0.0,
    padding_top_px: float = 0.0,
    padding_bottom_px: float = 0.0,
) -> float:
    """paragraph 리스트의 렌더링에 필요한 전체 높이(px)를 산출한다.

    각 paragraph의 줄바꿈 수를 계산하고, line_height를 곱한다.
    """
    if not paragraphs:
        return 0.0

    usable_width = box_width_px - padding_left_px - padding_right_px
    if usable_width <= 0:
        usable_width = 10.0

    total_height = padding_top_px + padding_bottom_px

    for para in paragraphs:
        indent = _get_bullet_indent_px(para.bullet_level)
        para_width = usable_width - indent
        if para_width <= 0:
            para_width = 10.0

        wrapped_lines = estimate_paragraph_wrapped_lines(para, para_width)

        # paragraph 내 최대 폰트 크기 결정
        max_font_pt = 16.0
        for run in para.runs:
            if run.font_size_pt and run.font_size_pt > max_font_pt:
                max_font_pt = run.font_size_pt

        # 줄 높이 결정: line_spacing_pt가 있으면 사용, 없으면 font_size × 2.0
        if line_spacing_pt and line_spacing_pt > 0:
            line_height_px = line_spacing_pt * TEXT_MEASURE_PX_PER_PT
        else:
            line_height_px = max_font_pt * 2.0

        total_height += wrapped_lines * line_height_px

    return total_height


def calculate_required_height_simple_text(
    text: str,
    font_size_pt: float,
    box_width_px: float,
    is_monospace: bool = False,
    line_spacing_pt: float | None = None,
    padding_left_px: float = TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX,
    padding_right_px: float = TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX,
    padding_top_px: float = TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX,
    padding_bottom_px: float = TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX,
) -> float:
    """shape.text (단순 텍스트)의 렌더링에 필요한 높이(px)를 산출한다.

    줄바꿈 문자('\\n')를 기준으로 분리하고, 각 줄의 줄바꿈 수를 계산한다.
    """
    if not text:
        return 0.0

    usable_width = box_width_px - padding_left_px - padding_right_px
    if usable_width <= 0:
        usable_width = 10.0

    if line_spacing_pt and line_spacing_pt > 0:
        line_height_px = line_spacing_pt * TEXT_MEASURE_PX_PER_PT
    else:
        line_height_px = font_size_pt * 2.0

    total_lines = 0
    for line in text.split("\n"):
        if not line.strip():
            total_lines += 1
            continue
        line_width = estimate_text_width_px(line, font_size_pt, is_monospace)
        total_lines += max(1, math.ceil(line_width / usable_width))

    total_height = padding_top_px + padding_bottom_px + total_lines * line_height_px
    return total_height


def should_apply_nowrap_to_paragraph(
    paragraph: "PptxParagraph",
    available_width_px: float,
    tolerance_ratio: float = TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO,
) -> bool:
    """단일 paragraph가 PPT에서는 한 줄로 표시되지만 브라우저 메트릭 차이로
    wrap되는 경계 케이스인지 판정한다.

    추정 텍스트 폭이 사용 가능 폭의 tolerance_ratio 배 이내면 nowrap을 적용해야
    PPT와 같은 한 줄 레이아웃을 유지할 수 있다.

    명시적 줄바꿈(텍스트 안의 '\\n')이 있으면 nowrap을 적용하지 않는다.
    """
    if available_width_px <= 0:
        return False

    total_width = 0.0
    has_text = False

    for run in paragraph.runs:
        if not run.text:
            continue
        if "\n" in run.text:
            return False
        has_text = True
        font_pt = run.font_size_pt or 16
        is_mono = run.font_family == "monospace"
        total_width += estimate_text_width_px(run.text, font_pt, is_mono)

    if not has_text:
        return False

    return total_width <= available_width_px * tolerance_ratio


def calculate_autofit_font_scale(
    required_h: float,
    available_h: float,
    min_font_pt: float = 10.0,
    max_font_pt: float = 44.0,
) -> float:
    """텍스트가 available_h에 맞도록 폰트 축소 비율을 계산한다.

    반환값: 0.0 < scale <= 1.0
    min_font_pt/max_font_pt 비율 이하로는 축소하지 않는다.
    """
    if required_h <= 0 or available_h <= 0:
        return 1.0

    if required_h <= available_h:
        return 1.0

    scale = available_h / required_h
    min_scale = min_font_pt / max_font_pt
    return max(scale, min_scale)
