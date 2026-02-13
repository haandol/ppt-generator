"""python-pptx 슬라이드 객체를 생성/조작하는 빌더 모듈."""

from __future__ import annotations

import re
from io import BytesIO

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
    PPTX_BULLET_CHAR_L0,
    PPTX_BULLET_INDENT_EMU_L0,
    PPTX_BULLET_INDENT_EMU_L1,
    PPTX_BULLET_MARGIN_EMU_L0,
    PPTX_BULLET_MARGIN_EMU_L1,
    PPTX_FONT_NAME,
    PPTX_MONOSPACE_FONT_NAME,
    PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU,
    PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU,
    PX_TO_EMU,
)
from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)


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


class SlideBuilder:
    """python-pptx 슬라이드에 요소를 배치하는 빌더."""

    @staticmethod
    def remove_placeholders(slide) -> None:
        """슬라이드에서 모든 placeholder shape을 제거한다."""
        sp_tree = slide.shapes._spTree
        for ph in list(slide.placeholders):
            sp_tree.remove(ph._element)

    @staticmethod
    def ensure_textboxes_on_top(slide) -> None:
        """spTree XML을 재정렬하여 텍스트박스가 항상 도형 위(z-order 최상위)에 오도록 보장.

        z-order: shapes(최하단) → pictures(중간) → textboxes(최상단)
        """
        sp_tree = slide.shapes._spTree
        shape_elements = []
        picture_elements = []
        textbox_elements = []

        shape_map = {}
        for shape in slide.shapes:
            shape_map[id(shape._element)] = shape

        sp_tag = qn("p:sp")
        pic_tag = qn("p:pic")
        for child in list(sp_tree):
            if child.tag == pic_tag:
                picture_elements.append(child)
                continue
            if child.tag != sp_tag:
                continue
            shape_obj = shape_map.get(id(child))
            if shape_obj is None:
                continue
            try:
                is_textbox = shape_obj.shape_type == MSO_SHAPE_TYPE.TEXT_BOX
            except Exception:
                is_textbox = False

            if is_textbox:
                textbox_elements.append(child)
            else:
                shape_elements.append(child)

        for el in shape_elements + picture_elements + textbox_elements:
            sp_tree.remove(el)
        for el in shape_elements:
            sp_tree.append(el)
        for el in picture_elements:
            sp_tree.append(el)
        for el in textbox_elements:
            sp_tree.append(el)

    @staticmethod
    def set_slide_background(slide, color: str) -> None:
        """슬라이드 배경색을 설정한다."""
        rgb = parse_color(color)
        if rgb is None:
            return
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = rgb

    @staticmethod
    def set_speaker_notes(slide, notes: str) -> None:
        """슬라이드에 발표자 노트를 설정한다."""
        if not notes:
            return
        notes_slide = slide.notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = notes

    def build_slide_from_spec(self, slide, spec: PptxSlideSpec) -> None:
        """PptxSlideSpec을 python-pptx 슬라이드 요소로 배치."""
        for shape in spec.shapes:
            self._add_shape_from_spec(slide, shape)
        for image in spec.images:
            self._add_image_from_spec(slide, image)
        for tb in spec.textboxes:
            self._add_textbox_from_spec(slide, tb)

    _ALIGN_MAP = {
        "center": PP_ALIGN.CENTER,
        "right": PP_ALIGN.RIGHT,
        "left": PP_ALIGN.LEFT,
    }

    _ANCHOR_MAP = {"top": "t", "middle": "ctr", "bottom": "b"}

    def _add_image_from_spec(self, slide, image_spec: PptxImage) -> None:
        """PptxImage spec으로 이미지를 슬라이드에 삽입."""
        if not image_spec.image_bytes:
            return
        image_stream = BytesIO(image_spec.image_bytes)
        slide.shapes.add_picture(
            image_stream,
            Inches(image_spec.left_px * EXPORT_PX_TO_INCHES_X),
            Inches(image_spec.top_px * EXPORT_PX_TO_INCHES_Y),
            Inches(image_spec.width_px * EXPORT_PX_TO_INCHES_X),
            Inches(image_spec.height_px * EXPORT_PX_TO_INCHES_Y),
        )

    def _add_textbox_from_spec(self, slide, tb: PptxTextBox) -> None:
        """PptxTextBox spec으로 텍스트박스를 생성."""
        left = tb.left_px * EXPORT_PX_TO_INCHES_X
        top = tb.top_px * EXPORT_PX_TO_INCHES_Y
        width = tb.width_px * EXPORT_PX_TO_INCHES_X
        height = tb.height_px * EXPORT_PX_TO_INCHES_Y

        txbox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txbox.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE

        tf.margin_left = Emu(0)
        tf.margin_right = Emu(0)
        tf.margin_top = Emu(0)
        tf.margin_bottom = Emu(0)

        for p_idx, para_spec in enumerate(tb.paragraphs):
            if p_idx == 0:
                para = tf.paragraphs[0]
            else:
                para = tf.add_paragraph()

            for run_spec in para_spec.runs:
                if not run_spec.text:
                    continue
                run = para.add_run()
                run.text = run_spec.text
                if run_spec.font_family == "monospace":
                    run.font.name = PPTX_MONOSPACE_FONT_NAME
                else:
                    run.font.name = PPTX_FONT_NAME
                if run_spec.font_size_pt:
                    run.font.size = Pt(run_spec.font_size_pt)
                run.font.bold = run_spec.bold
                run.font.italic = run_spec.italic
                if run_spec.color:
                    rgb = parse_color(run_spec.color)
                    if rgb:
                        run.font.color.rgb = rgb

            if para_spec.bullet_level >= 0:
                self._apply_bullet(para, para_spec.bullet_level)

            if para_spec.alignment and para_spec.alignment in self._ALIGN_MAP:
                para.alignment = self._ALIGN_MAP[para_spec.alignment]

        if tb.line_spacing_pt:
            for para in tf.paragraphs:
                para.line_spacing = Pt(tb.line_spacing_pt)

        if tb.vertical_alignment and tb.vertical_alignment in self._ANCHOR_MAP:
            bodyPr = tf._txBody.find(qn("a:bodyPr"))
            if bodyPr is not None:
                bodyPr.set("anchor", self._ANCHOR_MAP[tb.vertical_alignment])

    def _add_shape_from_spec(self, slide, shape_spec: PptxShape) -> None:
        """PptxShape spec으로 도형을 생성."""
        left = shape_spec.left_px * EXPORT_PX_TO_INCHES_X
        top = shape_spec.top_px * EXPORT_PX_TO_INCHES_Y
        width = shape_spec.width_px * EXPORT_PX_TO_INCHES_X
        height = shape_spec.height_px * EXPORT_PX_TO_INCHES_Y

        shape_type_map = {
            "rectangle": MSO_SHAPE.RECTANGLE,
            "rounded_rectangle": MSO_SHAPE.ROUNDED_RECTANGLE,
            "ellipse": MSO_SHAPE.OVAL,
            "line": MSO_SHAPE.RECTANGLE,
        }
        mso_shape = shape_type_map.get(shape_spec.shape_type, MSO_SHAPE.RECTANGLE)

        shape = slide.shapes.add_shape(
            mso_shape, Inches(left), Inches(top), Inches(width), Inches(height),
        )

        if shape_spec.fill_color:
            rgb = parse_color(shape_spec.fill_color)
            if rgb:
                shape.fill.solid()
                shape.fill.fore_color.rgb = rgb
        else:
            shape.fill.background()

        if shape_spec.border_color:
            rgb = parse_color(shape_spec.border_color)
            if rgb:
                shape.line.color.rgb = rgb
            if shape_spec.border_width_pt:
                shape.line.width = Pt(shape_spec.border_width_pt)
        else:
            shape.line.fill.background()

        if shape_spec.paragraphs:
            tf = shape.text_frame
            tf.word_wrap = True
            tf.auto_size = MSO_AUTO_SIZE.NONE

            if shape_spec.padding_left_px is not None:
                tf.margin_left = Emu(int(shape_spec.padding_left_px * PX_TO_EMU))
            else:
                tf.margin_left = Emu(PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU)
            if shape_spec.padding_right_px is not None:
                tf.margin_right = Emu(int(shape_spec.padding_right_px * PX_TO_EMU))
            else:
                tf.margin_right = Emu(PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU)
            if shape_spec.padding_top_px is not None:
                tf.margin_top = Emu(int(shape_spec.padding_top_px * PX_TO_EMU))
            else:
                tf.margin_top = Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)
            if shape_spec.padding_bottom_px is not None:
                tf.margin_bottom = Emu(int(shape_spec.padding_bottom_px * PX_TO_EMU))
            else:
                tf.margin_bottom = Emu(PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU)

            for p_idx, para_spec in enumerate(shape_spec.paragraphs):
                if p_idx == 0:
                    para = tf.paragraphs[0]
                else:
                    para = tf.add_paragraph()

                for run_spec in para_spec.runs:
                    if not run_spec.text:
                        continue
                    run = para.add_run()
                    run.text = run_spec.text
                    if run_spec.font_family == "monospace":
                        run.font.name = PPTX_MONOSPACE_FONT_NAME
                    else:
                        run.font.name = PPTX_FONT_NAME
                    if run_spec.font_size_pt:
                        run.font.size = Pt(run_spec.font_size_pt)
                    run.font.bold = run_spec.bold
                    run.font.italic = run_spec.italic
                    if run_spec.color:
                        rgb = parse_color(run_spec.color)
                        if rgb:
                            run.font.color.rgb = rgb

                if para_spec.bullet_level >= 0:
                    self._apply_bullet(para, para_spec.bullet_level)

                if para_spec.alignment and para_spec.alignment in self._ALIGN_MAP:
                    para.alignment = self._ALIGN_MAP[para_spec.alignment]

            if shape_spec.line_spacing_pt:
                for para in tf.paragraphs:
                    para.line_spacing = Pt(shape_spec.line_spacing_pt)

            if shape_spec.vertical_alignment and shape_spec.vertical_alignment in self._ANCHOR_MAP:
                bodyPr = tf._txBody.find(qn("a:bodyPr"))
                if bodyPr is not None:
                    bodyPr.set("anchor", self._ANCHOR_MAP[shape_spec.vertical_alignment])

        elif shape_spec.text:
            tf = shape.text_frame
            tf.word_wrap = True
            tf.auto_size = MSO_AUTO_SIZE.NONE

            tf.margin_left = Emu(45720)
            tf.margin_right = Emu(45720)
            tf.margin_top = Emu(22860)
            tf.margin_bottom = Emu(22860)

            txBody = tf._txBody
            bodyPr = txBody.find(qn("a:bodyPr"))
            if bodyPr is not None:
                bodyPr.set("anchor", "ctr")

            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = shape_spec.text
            run.font.name = PPTX_FONT_NAME
            if shape_spec.text_size_pt:
                run.font.size = Pt(shape_spec.text_size_pt)
            run.font.bold = shape_spec.text_bold
            if shape_spec.text_color:
                rgb = parse_color(shape_spec.text_color)
                if rgb:
                    run.font.color.rgb = rgb

    @staticmethod
    def _apply_bullet(paragraph, level: int) -> None:
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
