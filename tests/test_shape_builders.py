"""Tests for shape_builders: padding and vertical_alignment."""

from __future__ import annotations

from pptx.oxml.ns import qn
from pptx.util import Emu

from ppt_generator.interfaces.constants import (
    PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU,
    PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU,
    PX_TO_EMU,
)
from ppt_generator.interfaces.schemas import PptxParagraph, PptxShape, PptxTextRun
from ppt_generator.tools.pptx.shape_builders import add_auto_shape_from_spec


# ── padding: text 경로 ─────────────────────────────────────────


class TestTextPathPadding:
    """shape_spec.text 경로에서 padding 적용 검증."""

    def test_default_padding_when_none(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(left_px=0, top_px=0, width_px=200, height_px=100, text="hello")
        add_auto_shape_from_spec(slide, spec)

        tf = slide.shapes[0].text_frame
        assert tf.margin_left == Emu(PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU)
        assert tf.margin_right == Emu(PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU)
        assert tf.margin_top == Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)
        assert tf.margin_bottom == Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)

    def test_custom_padding(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            text="hello",
            padding_left_px=20,
            padding_right_px=10,
            padding_top_px=15,
            padding_bottom_px=5,
        )
        add_auto_shape_from_spec(slide, spec)

        tf = slide.shapes[0].text_frame
        assert tf.margin_left == Emu(int(20 * PX_TO_EMU))
        assert tf.margin_right == Emu(int(10 * PX_TO_EMU))
        assert tf.margin_top == Emu(int(15 * PX_TO_EMU))
        assert tf.margin_bottom == Emu(int(5 * PX_TO_EMU))

    def test_partial_padding_uses_default_for_missing(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            text="hello",
            padding_left_px=30,
        )
        add_auto_shape_from_spec(slide, spec)

        tf = slide.shapes[0].text_frame
        assert tf.margin_left == Emu(int(30 * PX_TO_EMU))
        assert tf.margin_right == Emu(PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU)
        assert tf.margin_top == Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)
        assert tf.margin_bottom == Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)


# ── padding: paragraphs 경로 ───────────────────────────────────


class TestParagraphsPathPadding:
    """shape_spec.paragraphs 경로에서 padding 적용 검증."""

    def _make_paragraph(self, text="test"):
        return PptxParagraph(runs=[PptxTextRun(text=text)])

    def test_default_padding_when_none(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            paragraphs=[self._make_paragraph()],
        )
        add_auto_shape_from_spec(slide, spec)

        tf = slide.shapes[0].text_frame
        assert tf.margin_left == Emu(PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU)
        assert tf.margin_right == Emu(PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU)
        assert tf.margin_top == Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)
        assert tf.margin_bottom == Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)

    def test_custom_padding(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            paragraphs=[self._make_paragraph()],
            padding_left_px=16,
            padding_right_px=16,
            padding_top_px=14,
            padding_bottom_px=14,
        )
        add_auto_shape_from_spec(slide, spec)

        tf = slide.shapes[0].text_frame
        assert tf.margin_left == Emu(int(16 * PX_TO_EMU))
        assert tf.margin_right == Emu(int(16 * PX_TO_EMU))
        assert tf.margin_top == Emu(int(14 * PX_TO_EMU))
        assert tf.margin_bottom == Emu(int(14 * PX_TO_EMU))


# ── vertical_alignment: text 경로 ─────────────────────────────


def _get_anchor(text_frame):
    bodyPr = text_frame._txBody.find(qn("a:bodyPr"))
    return bodyPr.get("anchor") if bodyPr is not None else None


class TestTextPathVerticalAlignment:
    """shape_spec.text 경로에서 vertical_alignment 검증."""

    def test_default_is_top(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(left_px=0, top_px=0, width_px=200, height_px=100, text="hello")
        add_auto_shape_from_spec(slide, spec)

        assert _get_anchor(slide.shapes[0].text_frame) == "t"

    def test_middle_alignment(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            text="hello",
            vertical_alignment="middle",
        )
        add_auto_shape_from_spec(slide, spec)

        assert _get_anchor(slide.shapes[0].text_frame) == "ctr"

    def test_bottom_alignment(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            text="hello",
            vertical_alignment="bottom",
        )
        add_auto_shape_from_spec(slide, spec)

        assert _get_anchor(slide.shapes[0].text_frame) == "b"


# ── vertical_alignment: paragraphs 경로 ───────────────────────


class TestParagraphsPathVerticalAlignment:
    """shape_spec.paragraphs 경로에서 vertical_alignment 검증."""

    def _make_paragraph(self, text="test"):
        return PptxParagraph(runs=[PptxTextRun(text=text)])

    def test_default_is_top(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            paragraphs=[self._make_paragraph()],
        )
        add_auto_shape_from_spec(slide, spec)

        assert _get_anchor(slide.shapes[0].text_frame) == "t"

    def test_middle_alignment(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            paragraphs=[self._make_paragraph()],
            vertical_alignment="middle",
        )
        add_auto_shape_from_spec(slide, spec)

        assert _get_anchor(slide.shapes[0].text_frame) == "ctr"

    def test_bottom_alignment(self, blank_slide):
        slide = blank_slide
        spec = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=100,
            paragraphs=[self._make_paragraph()],
            vertical_alignment="bottom",
        )
        add_auto_shape_from_spec(slide, spec)

        assert _get_anchor(slide.shapes[0].text_frame) == "b"
