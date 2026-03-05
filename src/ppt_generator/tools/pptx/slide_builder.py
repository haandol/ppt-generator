"""python-pptx 슬라이드 객체를 생성/조작하는 빌더 모듈."""

from __future__ import annotations

from io import BytesIO

from lxml.etree import SubElement
from pptx.enum.shapes import MSO_CONNECTOR_TYPE, MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
    PPTX_FONT_NAME,
    PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU,
    PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU,
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
            self._add_connector_from_spec(slide, shape_spec)
            return
        if shape_spec.shape_type == "custom" and shape_spec.svg_path:
            self._add_freeform_from_svg(slide, shape_spec)
            return

        left = shape_spec.left_px * EXPORT_PX_TO_INCHES_X
        top = shape_spec.top_px * EXPORT_PX_TO_INCHES_Y
        width = shape_spec.width_px * EXPORT_PX_TO_INCHES_X
        height = shape_spec.height_px * EXPORT_PX_TO_INCHES_Y

        shape_type_map = {
            "rectangle": MSO_SHAPE.RECTANGLE,
            "rounded_rectangle": MSO_SHAPE.ROUNDED_RECTANGLE,
            "ellipse": MSO_SHAPE.OVAL,
            # Arrows
            "up_arrow": MSO_SHAPE.UP_ARROW,
            "down_arrow": MSO_SHAPE.DOWN_ARROW,
            "left_arrow": MSO_SHAPE.LEFT_ARROW,
            "right_arrow": MSO_SHAPE.RIGHT_ARROW,
            "chevron": MSO_SHAPE.CHEVRON,
            # Polygons
            "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
            "diamond": MSO_SHAPE.DIAMOND,
            "pentagon": MSO_SHAPE.PENTAGON,
            "hexagon": MSO_SHAPE.HEXAGON,
            "trapezoid": MSO_SHAPE.TRAPEZOID,
            "parallelogram": MSO_SHAPE.PARALLELOGRAM,
            "cross": MSO_SHAPE.CROSS,
            # Stars
            "star_4": MSO_SHAPE.STAR_4_POINT,
            "star_5": MSO_SHAPE.STAR_5_POINT,
            "heart": MSO_SHAPE.HEART,
            # Flowchart
            "flowchart_process": MSO_SHAPE.FLOWCHART_PROCESS,
            "flowchart_decision": MSO_SHAPE.FLOWCHART_DECISION,
            "flowchart_terminator": MSO_SHAPE.FLOWCHART_TERMINATOR,
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
                apply_line_spacing(tf, shape_spec.line_spacing_pt, shape_spec.paragraphs)

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

    def _add_freeform_from_svg(self, slide, shape_spec: PptxShape) -> None:
        """SVG path data → python-pptx freeform 도형 생성."""
        import re as _re

        svg_path = shape_spec.svg_path or ""
        parts = svg_path.split(" ", 2)
        if len(parts) < 3:
            return
        vb_w, vb_h, path_d = int(parts[0]), int(parts[1]), parts[2]
        if vb_w <= 0 or vb_h <= 0:
            return

        left_emu = int(shape_spec.left_px * EXPORT_PX_TO_INCHES_X * 914400)
        top_emu = int(shape_spec.top_px * EXPORT_PX_TO_INCHES_Y * 914400)
        width_emu = int(shape_spec.width_px * EXPORT_PX_TO_INCHES_X * 914400)
        height_emu = int(shape_spec.height_px * EXPORT_PX_TO_INCHES_Y * 914400)

        # SVG path를 OOXML custGeom으로 직접 구축
        sp_tree = slide.shapes._spTree
        sp = SubElement(sp_tree, qn("p:sp"))
        nvSpPr = SubElement(sp, qn("p:nvSpPr"))
        cNvPr = SubElement(nvSpPr, qn("p:cNvPr"))
        cNvPr.set("id", str(len(slide.shapes) + 100))
        cNvPr.set("name", "Freeform")
        SubElement(nvSpPr, qn("p:cNvSpPr"))
        SubElement(nvSpPr, qn("p:nvPr"))

        spPr = SubElement(sp, qn("p:spPr"))
        xfrm = SubElement(spPr, qn("a:xfrm"))
        off = SubElement(xfrm, qn("a:off"))
        off.set("x", str(left_emu))
        off.set("y", str(top_emu))
        ext = SubElement(xfrm, qn("a:ext"))
        ext.set("cx", str(width_emu))
        ext.set("cy", str(height_emu))

        custGeom = SubElement(spPr, qn("a:custGeom"))
        SubElement(custGeom, qn("a:avLst"))
        SubElement(custGeom, qn("a:gdLst"))
        SubElement(custGeom, qn("a:ahLst"))
        SubElement(custGeom, qn("a:cxnLst"))
        rect = SubElement(custGeom, qn("a:rect"))
        rect.set("l", "l")
        rect.set("t", "t")
        rect.set("r", "r")
        rect.set("b", "b")
        pathLst = SubElement(custGeom, qn("a:pathLst"))
        path_el = SubElement(pathLst, qn("a:path"))
        path_el.set("w", str(vb_w))
        path_el.set("h", str(vb_h))

        # SVG path data 파싱: M, L, C, Z 명령
        tokens = _re.findall(r"[MLCZ]|[-]?\d+", path_d)
        i = 0
        while i < len(tokens):
            cmd = tokens[i]
            if cmd == "M" and i + 2 < len(tokens):
                move = SubElement(path_el, qn("a:moveTo"))
                pt = SubElement(move, qn("a:pt"))
                pt.set("x", tokens[i + 1])
                pt.set("y", tokens[i + 2])
                i += 3
            elif cmd == "L" and i + 2 < len(tokens):
                ln = SubElement(path_el, qn("a:lnTo"))
                pt = SubElement(ln, qn("a:pt"))
                pt.set("x", tokens[i + 1])
                pt.set("y", tokens[i + 2])
                i += 3
            elif cmd == "C" and i + 6 < len(tokens):
                bez = SubElement(path_el, qn("a:cubicBezTo"))
                for j in range(3):
                    pt = SubElement(bez, qn("a:pt"))
                    pt.set("x", tokens[i + 1 + j * 2])
                    pt.set("y", tokens[i + 2 + j * 2])
                i += 7
            elif cmd == "Z":
                SubElement(path_el, qn("a:close"))
                i += 1
            else:
                i += 1

        # fill
        if shape_spec.fill_color:
            rgb = parse_color(shape_spec.fill_color)
            if rgb:
                solid = SubElement(spPr, qn("a:solidFill"))
                srgb = SubElement(solid, qn("a:srgbClr"))
                srgb.set("val", str(rgb))
        else:
            SubElement(spPr, qn("a:noFill"))

        # border
        if shape_spec.border_color:
            rgb = parse_color(shape_spec.border_color)
            if rgb:
                ln = SubElement(spPr, qn("a:ln"))
                if shape_spec.border_width_pt:
                    ln.set("w", str(int(shape_spec.border_width_pt * 12700)))
                solid = SubElement(ln, qn("a:solidFill"))
                srgb = SubElement(solid, qn("a:srgbClr"))
                srgb.set("val", str(rgb))
        else:
            ln = SubElement(spPr, qn("a:ln"))
            SubElement(ln, qn("a:noFill"))

    # 선/화살표 전용 dash_style 매핑
    _DASH_STYLE_MAP = {
        "dash": "dash",
        "dot": "dot",
    }

    # 수평/수직 스냅 임계값 (px): 이 값 이하면 의도하지 않은 오차로 판단
    _SNAP_THRESHOLD = 12

    def _add_connector_from_spec(self, slide, shape_spec: PptxShape) -> None:
        """Line shape를 python-pptx Connector(직선)로 생성하고 화살표 머리를 설정."""
        w = shape_spec.width_px
        h = shape_spec.height_px
        if w > 0 and 0 < h <= self._SNAP_THRESHOLD:
            h = 0  # 수평선 보정
        elif h > 0 and 0 < w <= self._SNAP_THRESHOLD:
            w = 0  # 수직선 보정

        start_x = Inches(shape_spec.left_px * EXPORT_PX_TO_INCHES_X)
        start_y = Inches(shape_spec.top_px * EXPORT_PX_TO_INCHES_Y)
        end_x = Inches((shape_spec.left_px + w) * EXPORT_PX_TO_INCHES_X)
        end_y = Inches((shape_spec.top_px + h) * EXPORT_PX_TO_INCHES_Y)

        connector = slide.shapes.add_connector(
            MSO_CONNECTOR_TYPE.STRAIGHT, start_x, start_y, end_x, end_y,
        )

        # 선 색상/굵기
        if shape_spec.border_color:
            rgb = parse_color(shape_spec.border_color)
            if rgb:
                connector.line.color.rgb = rgb
        if shape_spec.border_width_pt:
            connector.line.width = Pt(shape_spec.border_width_pt)

        # 화살표 머리 설정 (a:ln 안에 headEnd/tailEnd XML 추가)
        spPr = connector._element.find(qn("p:spPr"))
        ln = spPr.find(qn("a:ln"))
        if ln is None:
            ln = SubElement(spPr, qn("a:ln"))

        if shape_spec.end_arrow:
            tail = SubElement(ln, qn("a:tailEnd"))
            tail.set("type", "triangle")
            tail.set("w", "med")
            tail.set("len", "med")

        if shape_spec.start_arrow:
            head = SubElement(ln, qn("a:headEnd"))
            head.set("type", "triangle")
            head.set("w", "med")
            head.set("len", "med")

        # 대시 스타일
        dash_key = (shape_spec.dash_style or "").lower()
        prstDash = self._DASH_STYLE_MAP.get(dash_key)
        if prstDash:
            dash_el = SubElement(ln, qn("a:prstDash"))
            dash_el.set("val", prstDash)
