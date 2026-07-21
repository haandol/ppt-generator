"""폰트 메트릭 기반 텍스트 크기 추정 모듈.

외부 의존성 없이 순수 함수로 구현.
CJK/한글 전각 문자와 Latin 반각 문자의 폭 차이를 반영하여
텍스트 줄바꿈 후 필요 높이를 계산한다.
"""

from __future__ import annotations

import math
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ppt_generator.interfaces.schemas import PptxParagraph

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


# lint(text-overflow) 가 "넘쳤다" 고 경고하기까지 허용하는 높이 여유.
# 폰트 메트릭이 브라우저/PowerPoint 실제 렌더와 다를 수 있으므로, 경계 케이스에서
# 노이즈 경고를 줄이려 15% 여유를 둔다. 이 여유는 "경고 판정" 에만 쓴다.
AUTOFIT_HEIGHT_TOLERANCE = 1.15

# shrink_text autofit 이 폰트를 축소할 때 맞추는 목표 높이 여유.
# PPTX 는 도형에 클리핑이 없어 넘친 텍스트가 그대로 박스 밖으로 삐져나온다
# (HTML 은 overflow:hidden 으로 가려질 뿐 실제로는 넘친다). 따라서 축소 목표는
# 실제 박스 높이(1.0) 여야 넘침이 없다 — lint tolerance(1.15) 를 축소 목표로 쓰면
# 박스보다 15% 큰 높이까지 허용해 그만큼 하단으로 새어 나온다.
AUTOFIT_SHRINK_TARGET_TOLERANCE = 1.0


def max_paragraph_font_pt(
    paragraphs: list["PptxParagraph"], default: float = 16.0
) -> float:
    """paragraph 리스트에서 가장 큰 run 폰트 크기(pt)를 반환한다.

    shrink 축소 하한을 절대 10pt 로 만들기 위해 calculate_autofit_font_scale 의
    max_font_pt 인자로 사용한다 (min_scale = 10 / max_font_pt).
    """
    sizes = [
        r.font_size_pt
        for p in paragraphs
        for r in p.runs
        if getattr(r, "font_size_pt", None)
    ]
    return max(sizes) if sizes else default


def calculate_shrink_font_scale(
    paragraphs: list["PptxParagraph"],
    box_width_px: float,
    box_height_px: float,
    line_spacing_pt: float | None = None,
    padding_left_px: float = 0.0,
    padding_right_px: float = 0.0,
    padding_top_px: float = 0.0,
    padding_bottom_px: float = 0.0,
    height_tolerance: float = AUTOFIT_SHRINK_TARGET_TOLERANCE,
) -> float:
    """shrink_text autofit 폰트 축소 비율을 계산한다.

    필요 높이가 box_height_px(× height_tolerance)를 넘으면 1.0 미만의 scale 을
    반환한다. 축소 하한은 paragraph 내 최대 폰트 기준 절대 10pt 다.

    height_tolerance 기본값은 실제 박스(1.0) 다 — PPTX 는 클리핑이 없어 축소 목표를
    박스보다 크게 잡으면 그만큼 텍스트가 박스 밖으로 삐져나온다. lint 의 경고
    tolerance(1.15) 와 다르며, 축소는 실제 박스에 맞춰야 넘침이 없다.

    HTML 렌더러(shape_renderer/html_renderer)와 PPTX 빌더(shape_builders/
    slide_builder)가 동일한 폰트 크기를 산출하도록 이 헬퍼를 공유한다.
    """
    if not paragraphs:
        return 1.0

    required_h = calculate_required_height(
        paragraphs,
        box_width_px,
        line_spacing_pt=line_spacing_pt,
        padding_left_px=padding_left_px,
        padding_right_px=padding_right_px,
        padding_top_px=padding_top_px,
        padding_bottom_px=padding_bottom_px,
    )
    # 상하 padding 은 폰트/줄간격 축소로 줄지 않는 고정분이다. 축소 대상은 텍스트
    # 줄 높이(required_h - padding)뿐이므로, padding 을 양변에서 빼고 텍스트분끼리
    # 비율을 잡아야 축소 후 실제 소비 높이가 박스에 수렴한다 (padding 을 포함해
    # 비율을 잡으면 다행 텍스트에서 여전히 미세하게 넘친다).
    fixed_padding = padding_top_px + padding_bottom_px
    text_required_h = required_h - fixed_padding
    text_available_h = box_height_px * height_tolerance - fixed_padding
    return calculate_autofit_font_scale(
        text_required_h,
        text_available_h,
        max_font_pt=max_paragraph_font_pt(paragraphs),
    )


def scaled_line_spacing_pt(
    line_spacing_pt: float | None, font_scale: float
) -> float | None:
    """shrink_text autofit 시 line_spacing 도 폰트와 같은 비율로 축소한다.

    줄 높이가 폰트와 함께 줄어야 소비 높이가 실제로 감소해 autofit 이
    오버플로를 해소한다 (line_spacing 을 상수로 두면 폰트만 줄고 줄 높이는
    그대로라 다행 텍스트가 계속 넘친다). HTML·PPTX 두 출력 경로가 이 헬퍼를
    공유해 동일한 줄 높이를 산출한다.
    """
    if not line_spacing_pt or line_spacing_pt <= 0:
        return line_spacing_pt
    if not (0 < font_scale < 1.0):
        return line_spacing_pt
    return line_spacing_pt * font_scale


def required_height_after_shrink(
    paragraphs: list["PptxParagraph"],
    box_width_px: float,
    box_height_px: float,
    line_spacing_pt: float | None = None,
    padding_left_px: float = 0.0,
    padding_right_px: float = 0.0,
    padding_top_px: float = 0.0,
    padding_bottom_px: float = 0.0,
) -> float:
    """shrink_text autofit 을 적용한 *뒤* 실제 소비 높이(px)를 산출한다.

    폰트 축소 비율(font_scale)과 그에 맞춰 축소된 line_spacing 을 반영해 다시
    필요 높이를 잰다. 축소 하한(폰트 절대 10pt) 때문에 scale 이 하한에 걸리면
    축소해도 여전히 박스를 넘을 수 있으며, 그 잔여 넘침이 이 값에 드러난다.
    lint(text-overflow) 가 shrink_text shape 의 "축소 후에도 남는" 넘침만
    잡도록 이 헬퍼를 공유한다.
    """
    if not paragraphs:
        return 0.0

    scale = calculate_shrink_font_scale(
        paragraphs,
        box_width_px,
        box_height_px,
        line_spacing_pt=line_spacing_pt,
        padding_left_px=padding_left_px,
        padding_right_px=padding_right_px,
        padding_top_px=padding_top_px,
        padding_bottom_px=padding_bottom_px,
    )
    effective_ls = scaled_line_spacing_pt(line_spacing_pt, scale)
    scaled_paras = _scale_paragraph_fonts(paragraphs, scale)
    return calculate_required_height(
        scaled_paras,
        box_width_px,
        line_spacing_pt=effective_ls,
        padding_left_px=padding_left_px,
        padding_right_px=padding_right_px,
        padding_top_px=padding_top_px,
        padding_bottom_px=padding_bottom_px,
    )


def _scale_paragraph_fonts(
    paragraphs: list["PptxParagraph"], font_scale: float
) -> list["PptxParagraph"]:
    """run 폰트 크기에 font_scale 을 적용한 사본 paragraph 리스트를 만든다.

    측정 전용 — 원본을 변형하지 않는다. scale 이 1.0 이면 원본을 그대로 돌려준다.
    """
    if not (0 < font_scale < 1.0):
        return paragraphs

    from dataclasses import replace

    scaled: list["PptxParagraph"] = []
    for para in paragraphs:
        new_runs = []
        for r in para.runs:
            size = getattr(r, "font_size_pt", None)
            if size:
                new_runs.append(replace(r, font_size_pt=size * font_scale))
            else:
                new_runs.append(r)
        scaled.append(replace(para, runs=new_runs))
    return scaled
