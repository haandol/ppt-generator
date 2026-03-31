"""python-pptx 텍스트 포매팅 공통 유틸리티.

textbox와 shape에서 공통으로 사용하는 run/paragraph 포매팅 로직을 제공한다.
"""

from __future__ import annotations

import re

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from ppt_generator.interfaces.constants import (
    PPTX_BULLET_CHAR_L0,
    PPTX_BULLET_INDENT_EMU_L0,
    PPTX_BULLET_INDENT_EMU_L1,
    PPTX_BULLET_MARGIN_EMU_L0,
    PPTX_BULLET_MARGIN_EMU_L1,
    PPTX_FONT_NAME,
    PPTX_MONOSPACE_FONT_NAME,
)
from ppt_generator.interfaces.schemas import PptxParagraph, PptxTextRun


_ALIGN_MAP = {
    "center": PP_ALIGN.CENTER,
    "right": PP_ALIGN.RIGHT,
    "left": PP_ALIGN.LEFT,
}

_ANCHOR_MAP = {"top": "t", "middle": "ctr", "bottom": "b"}


def parse_color(color_str: str) -> RGBColor | None:
    """CSS 색상 문자열을 python-pptx RGBColor로 변환."""
    if not color_str:
        return None
    # #RRGGBB or #RGB
    hex_match = re.match(r"#([0-9a-fA-F]{6})", color_str)
    if hex_match:
        hex_val = hex_match.group(1)
        return RGBColor(int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16))
    short_hex = re.match(r"#([0-9a-fA-F]{3})(?:\s|;|$)", color_str)
    if short_hex:
        h = short_hex.group(1)
        return RGBColor(int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
    # rgb(r, g, b)
    rgb_match = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color_str)
    if rgb_match:
        return RGBColor(int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))
    return None


def format_run(run_obj, run_spec: PptxTextRun) -> None:
    """run에 폰트/색상/볼드/이탤릭을 적용한다."""
    run_obj.text = run_spec.text
    if run_spec.font_family == "monospace":
        run_obj.font.name = PPTX_MONOSPACE_FONT_NAME
    else:
        run_obj.font.name = PPTX_FONT_NAME
    if run_spec.font_size_pt:
        run_obj.font.size = Pt(run_spec.font_size_pt)
    run_obj.font.bold = run_spec.bold
    run_obj.font.italic = run_spec.italic
    if run_spec.color:
        rgb = parse_color(run_spec.color)
        if rgb:
            run_obj.font.color.rgb = rgb
    if run_spec.href:
        run_obj.hyperlink.address = run_spec.href


def apply_bullet(paragraph, level: int) -> None:
    """paragraph에 불릿 마커와 들여쓰기를 XML로 설정."""
    pPr = paragraph._p.get_or_add_pPr()

    if level == 0:
        margin = PPTX_BULLET_MARGIN_EMU_L0
        indent = PPTX_BULLET_INDENT_EMU_L0
    else:
        margin = PPTX_BULLET_MARGIN_EMU_L1
        indent = PPTX_BULLET_INDENT_EMU_L1

    pPr.set("marL", str(margin))
    pPr.set("indent", str(indent))

    buNone = pPr.find(qn("a:buNone"))
    if buNone is not None:
        pPr.remove(buNone)

    buChar = pPr.find(qn("a:buChar"))
    if buChar is None:
        buChar = pPr.makeelement(qn("a:buChar"), {})
        pPr.append(buChar)
    buChar.set("char", PPTX_BULLET_CHAR_L0)


def format_paragraphs(
    text_frame,
    paragraphs: list[PptxParagraph],
) -> None:
    """paragraph 반복 + run 포매팅 + 불릿/정렬 적용."""
    for p_idx, para_spec in enumerate(paragraphs):
        if p_idx == 0:
            para = text_frame.paragraphs[0]
        else:
            para = text_frame.add_paragraph()

        for run_spec in para_spec.runs:
            if not run_spec.text:
                continue
            run = para.add_run()
            format_run(run, run_spec)

        if para_spec.bullet_level >= 0:
            apply_bullet(para, para_spec.bullet_level)

        if para_spec.alignment and para_spec.alignment in _ALIGN_MAP:
            para.alignment = _ALIGN_MAP[para_spec.alignment]


def apply_line_spacing(
    text_frame,
    line_spacing_pt: float,
    paragraphs: list[PptxParagraph] | None = None,
) -> None:
    """줄간격을 적용한다.

    paragraph 스펙이 제공되면, 해당 paragraph 내 최대 font_size_pt보다
    line_spacing_pt가 작은 경우 해당 paragraph에는 줄간격을 적용하지 않는다.
    (PPTX line_spacing은 절대값이므로 폰트보다 작으면 텍스트가 겹침)
    """
    tf_paras = list(text_frame.paragraphs)
    for i, para in enumerate(tf_paras):
        if paragraphs and i < len(paragraphs):
            max_font = max(
                (r.font_size_pt for r in paragraphs[i].runs if r.font_size_pt),
                default=0,
            )
            if max_font and line_spacing_pt < max_font * 1.2:
                continue
        para.line_spacing = Pt(line_spacing_pt)


def apply_vertical_alignment(text_frame, alignment: str) -> None:
    """수직 정렬을 적용한다."""
    if alignment not in _ANCHOR_MAP:
        return
    bodyPr = text_frame._txBody.find(qn("a:bodyPr"))
    if bodyPr is not None:
        bodyPr.set("anchor", _ANCHOR_MAP[alignment])
