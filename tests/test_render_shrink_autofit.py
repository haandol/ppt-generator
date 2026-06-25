"""shrink_text autofit 의 HTML 렌더 반영 테스트.

HTML 렌더 경로에서 shrink_text 요소가 박스 높이를 넘으면 폰트를 비례 축소하고,
넘치지 않으면 spec 폰트 크기를 그대로 유지하는지 검증한다.
"""

from __future__ import annotations

import re

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.slides.html_renderer import textbox_to_html
from ppt_generator.tools.slides.shape_renderer import shape_to_html


def _font_sizes_pt(html: str) -> list[float]:
    return [float(m) for m in re.findall(r"font-size:([\d.]+)pt", html)]


def _long_paragraphs(n_runs: int = 1) -> list[PptxParagraph]:
    long_text = (
        "이것은 박스 높이를 한참 넘기도록 의도적으로 길게 작성한 텍스트입니다. "
        "여러 줄로 줄바꿈되어 컨테이너를 넘칩니다. " * 6
    )
    runs = [PptxTextRun(text=long_text, font_size_pt=18) for _ in range(n_runs)]
    return [PptxParagraph(runs=runs)]


class TestShapeShrinkAutofit:
    def test_overflowing_shrink_text_scales_font_down(self):
        # 작은 박스에 긴 텍스트 -> 폰트가 18pt 보다 작아져야 한다.
        shape = PptxShape(
            left_px=0,
            top_px=0,
            width_px=400,
            height_px=60,
            shape_type="rounded_rectangle",
            paragraphs=_long_paragraphs(),
            autofit_mode="shrink_text",
        )
        html = shape_to_html(shape)
        sizes = _font_sizes_pt(html)
        assert sizes, "font-size 가 렌더되어야 한다"
        assert all(s < 18.0 for s in sizes), f"폰트가 축소되어야 함: {sizes}"

    def test_fitting_text_keeps_original_font(self):
        # 충분히 큰 박스 -> 축소 없이 18pt 유지.
        shape = PptxShape(
            left_px=0,
            top_px=0,
            width_px=1000,
            height_px=400,
            shape_type="rounded_rectangle",
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="짧은 텍스트", font_size_pt=18)])
            ],
            autofit_mode="shrink_text",
        )
        html = shape_to_html(shape)
        sizes = _font_sizes_pt(html)
        assert sizes == [18.0], f"원본 폰트 유지되어야 함: {sizes}"

    def test_expand_height_does_not_shrink(self):
        # expand_height 는 박스가 늘어나므로 폰트를 줄이지 않는다.
        shape = PptxShape(
            left_px=0,
            top_px=0,
            width_px=400,
            height_px=60,
            shape_type="rounded_rectangle",
            paragraphs=_long_paragraphs(),
            autofit_mode="expand_height",
        )
        html = shape_to_html(shape)
        sizes = _font_sizes_pt(html)
        assert sizes, "font-size 가 렌더되어야 한다"
        assert all(s == 18.0 for s in sizes), f"expand_height 는 원본 유지: {sizes}"

    def test_scale_has_absolute_10pt_floor(self):
        # 극단적으로 긴 텍스트라도 절대 10pt(가독성 floor) 아래로는 내려가지 않는다.
        # base font 가 작아도(15pt) 비율이 아닌 절대 10pt 가 하한이어야 한다.
        huge = [PptxParagraph(runs=[PptxTextRun(text="가" * 4000, font_size_pt=15)])]
        shape = PptxShape(
            left_px=0,
            top_px=0,
            width_px=300,
            height_px=40,
            shape_type="rounded_rectangle",
            paragraphs=huge,
            autofit_mode="shrink_text",
        )
        html = shape_to_html(shape)
        sizes = _font_sizes_pt(html)
        assert sizes and min(sizes) >= 10.0 - 0.01, f"절대 하한 10pt 보장: {sizes}"


class TestTextboxShrinkAutofit:
    def test_overflowing_textbox_scales_font_down(self):
        # 헤더/푸터처럼 낮은 textbox 에 긴 텍스트 -> 축소.
        tb = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=400,
            height_px=48,
            paragraphs=_long_paragraphs(),
        )
        html = textbox_to_html(tb)
        sizes = _font_sizes_pt(html)
        assert sizes, "font-size 가 렌더되어야 한다"
        assert all(s < 18.0 for s in sizes), f"폰트가 축소되어야 함: {sizes}"

    def test_fitting_textbox_keeps_original_font(self):
        tb = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=1000,
            height_px=200,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="제목", font_size_pt=32)])
            ],
        )
        html = textbox_to_html(tb)
        sizes = _font_sizes_pt(html)
        assert sizes == [32.0], f"원본 폰트 유지되어야 함: {sizes}"
