"""렌더 명세에서 덱의 색상·글꼴 요약을 추출한다."""

from __future__ import annotations

from itertools import chain

from ppt_generator.interfaces.schemas import PptxSlideSpec


def extract_design_summary(spec: PptxSlideSpec) -> dict:
    """텍스트 런과 도형 색상에서 덱 테마를 추출한다."""
    text_colors: set[str] = set()
    title_font: int | None = None
    body_font: int | None = None

    for element in chain(spec.textboxes, spec.shapes):
        for para in element.paragraphs:
            for run in para.runs:
                if run.color:
                    text_colors.add(run.color)
                if run.font_size_pt:
                    if run.bold and (
                        title_font is None or run.font_size_pt > title_font
                    ):
                        title_font = run.font_size_pt
                    elif not run.bold and (
                        body_font is None or run.font_size_pt > body_font
                    ):
                        body_font = run.font_size_pt

    card_fills: set[str] = set()
    card_borders: set[str] = set()
    for s in spec.shapes:
        if s.fill_color:
            card_fills.add(s.fill_color)
        if s.border_color:
            card_borders.add(s.border_color)
        if s.text_color:
            text_colors.add(s.text_color)

    return {
        "background_color": spec.background_color or None,
        "text_colors": sorted(text_colors) if text_colors else [],
        "title_font_pt": title_font,
        "body_font_pt": body_font,
        "card_fills": sorted(card_fills) if card_fills else [],
        "card_borders": sorted(card_borders) if card_borders else [],
    }
