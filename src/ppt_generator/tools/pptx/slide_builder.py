"""python-pptx 슬라이드 객체를 생성/조작하는 빌더 모듈.

도형 생성은 shape_builders 모듈, 텍스트 서식은 text_formatter 모듈로 분리.
"""

from __future__ import annotations

from io import BytesIO

from lxml.etree import SubElement
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
    PX_TO_EMU,
)
from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.tools.pptx.shape_builders import (
    add_auto_shape_from_spec,
    add_connector_from_spec,
    add_freeform_from_svg,
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

        z-order: shapes(최하단) → connectors → pictures(중간) → textboxes(최상단)
        """
        sp_tree = slide.shapes._spTree
        shape_elements = []
        connector_elements = []
        picture_elements = []
        textbox_elements = []

        shape_map = {}
        for shape in slide.shapes:
            shape_map[id(shape._element)] = shape

        sp_tag = qn("p:sp")
        pic_tag = qn("p:pic")
        cxn_tag = qn("p:cxnSp")
        for child in list(sp_tree):
            if child.tag == pic_tag:
                picture_elements.append(child)
                continue
            if child.tag == cxn_tag:
                connector_elements.append(child)
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

        all_sorted = shape_elements + connector_elements + picture_elements + textbox_elements
        for el in all_sorted:
            sp_tree.remove(el)
        for el in all_sorted:
            sp_tree.append(el)

    @staticmethod
    def set_slide_background_image(slide, image_bytes: bytes) -> None:
        """슬라이드 배경(p:bg)에 이미지를 설정한다.

        shape이 아닌 슬라이드 배경 속성(a:blipFill)으로 설정하므로
        z-order 조작이 불필요하고 shapes 컬렉션에 포함되지 않는다.
        """
        image_stream = BytesIO(image_bytes)
        image_part, rId = slide.part.get_or_add_image_part(image_stream)

        # bgPr 접근 (fill 호출 시 자동 생성)
        bg = slide.background
        _ = bg.fill

        cSld = slide._element.find(qn("p:cSld"))
        bgEl = cSld.find(qn("p:bg"))
        bgPr = bgEl.find(qn("p:bgPr"))

        # blipFill로 전환 (기존 solidFill 등 제거)
        blipFill = bgPr.get_or_change_to_blipFill()

        # blip 요소: 이미지 파트 참조
        blip = SubElement(blipFill, qn("a:blip"))
        blip.set(qn("r:embed"), rId)

        # stretch + fillRect: 전체 배경에 이미지 채움
        stretch = SubElement(blipFill, qn("a:stretch"))
        SubElement(stretch, qn("a:fillRect"))

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

        if tb.padding_left_px is not None:
            tf.margin_left = Emu(int(tb.padding_left_px * PX_TO_EMU))
        else:
            tf.margin_left = Emu(0)
        if tb.padding_right_px is not None:
            tf.margin_right = Emu(int(tb.padding_right_px * PX_TO_EMU))
        else:
            tf.margin_right = Emu(0)
        if tb.padding_top_px is not None:
            tf.margin_top = Emu(int(tb.padding_top_px * PX_TO_EMU))
        else:
            tf.margin_top = Emu(0)
        if tb.padding_bottom_px is not None:
            tf.margin_bottom = Emu(int(tb.padding_bottom_px * PX_TO_EMU))
        else:
            tf.margin_bottom = Emu(0)

        format_paragraphs(tf, tb.paragraphs)

        if tb.line_spacing_pt:
            apply_line_spacing(tf, tb.line_spacing_pt, tb.paragraphs)

        if tb.vertical_alignment:
            apply_vertical_alignment(tf, tb.vertical_alignment)

    def _add_shape_from_spec(self, slide, shape_spec: PptxShape) -> None:
        """PptxShape spec으로 도형을 생성."""
        if shape_spec.shape_type == "line":
            add_connector_from_spec(slide, shape_spec)
        elif shape_spec.shape_type == "custom" and shape_spec.svg_path:
            add_freeform_from_svg(slide, shape_spec)
        else:
            add_auto_shape_from_spec(slide, shape_spec)

