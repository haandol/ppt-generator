"""python-pptx 슬라이드 객체를 생성/조작하는 빌더 모듈."""

from __future__ import annotations

from io import BytesIO

from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
    PPTX_FONT_NAME,
    PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU,
    PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU,
    PPTX_SLIDE_HEIGHT_EMU,
    PPTX_SLIDE_WIDTH_EMU,
    PX_TO_EMU,
)
from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.tools.pptx.text_formatter import (
    apply_line_spacing,
    apply_vertical_alignment,
    format_paragraphs,
    parse_color,
)


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
    def set_slide_background_image(slide, image_bytes: bytes) -> None:
        """슬라이드 배경에 이미지를 설정한다.

        전체 슬라이드 크기의 이미지를 z-order 최하단(spTree 맨 앞)에 삽입한다.
        """
        image_stream = BytesIO(image_bytes)
        pic = slide.shapes.add_picture(
            image_stream,
            Emu(0),
            Emu(0),
            Emu(PPTX_SLIDE_WIDTH_EMU),
            Emu(PPTX_SLIDE_HEIGHT_EMU),
        )
        # z-order 최하단으로 이동: spTree에서 제거 후 맨 앞(nvGrpSpPr 뒤)에 삽입
        sp_tree = slide.shapes._spTree
        sp_tree.remove(pic._element)
        # spTree의 첫 번째 자식은 nvGrpSpPr이므로 그 뒤에 삽입
        sp_tree.insert(1, pic._element)

    @staticmethod
    def add_logo_image(slide, image_bytes: bytes, width_px: int = 100) -> None:
        """슬라이드 우측 하단에 로고 이미지를 배치한다.

        width_px 기준으로 크기를 설정하고, 높이는 원본 비율에 맞춰 자동 계산된다.
        z-order 최상단에 위치하도록 spTree 맨 끝에 추가한다.
        """
        import struct

        # PNG IHDR 청크에서 width/height 읽기 (offset 16~24)
        orig_w, orig_h = struct.unpack(">II", image_bytes[16:24])
        aspect_ratio = orig_h / orig_w

        width_emu = int(width_px * PX_TO_EMU)
        height_emu = int(width_emu * aspect_ratio)

        margin_right_px = 50
        margin_bottom_px = 45
        left_emu = PPTX_SLIDE_WIDTH_EMU - width_emu - int(margin_right_px * PX_TO_EMU)
        top_emu = PPTX_SLIDE_HEIGHT_EMU - height_emu - int(margin_bottom_px * PX_TO_EMU)

        image_stream = BytesIO(image_bytes)
        slide.shapes.add_picture(
            image_stream,
            Emu(left_emu),
            Emu(top_emu),
            Emu(width_emu),
            Emu(height_emu),
        )

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

        format_paragraphs(tf, tb.paragraphs)

        if tb.line_spacing_pt:
            apply_line_spacing(tf, tb.line_spacing_pt)

        if tb.vertical_alignment:
            apply_vertical_alignment(tf, tb.vertical_alignment)

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

            format_paragraphs(tf, shape_spec.paragraphs)

            if shape_spec.line_spacing_pt:
                apply_line_spacing(tf, shape_spec.line_spacing_pt)

            if shape_spec.vertical_alignment:
                apply_vertical_alignment(tf, shape_spec.vertical_alignment)

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
