"""python-pptx 슬라이드 객체를 생성/조작하는 빌더 모듈."""

from __future__ import annotations

import re

from bs4 import Tag
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE
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
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.tools.pptx.html_parser import walk_region_content
from ppt_generator.tools.pptx.style_utils import (
    RichTextFragment,
    extract_color,
    extract_font_size,
    get_position_and_size,
    is_bold,
    parse_color,
    parse_inline_style,
    scale_font_size,
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
        """spTree XML을 재정렬하여 텍스트박스가 항상 도형 위(z-order 최상위)에 오도록 보장."""
        sp_tree = slide.shapes._spTree
        shape_elements = []
        textbox_elements = []

        shape_map = {}
        for shape in slide.shapes:
            shape_map[id(shape._element)] = shape

        sp_tag = qn("p:sp")
        for child in list(sp_tree):
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

        for el in shape_elements + textbox_elements:
            sp_tree.remove(el)
        for el in shape_elements:
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
        for tb in spec.textboxes:
            self._add_textbox_from_spec(slide, tb)

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

        tf.margin_left = Emu(45720)
        tf.margin_right = Emu(45720)
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

    def _add_shape_from_spec(self, slide, shape_spec: PptxShape) -> None:
        """PptxShape spec으로 도형을 생성."""
        left = shape_spec.left_px * EXPORT_PX_TO_INCHES_X
        top = shape_spec.top_px * EXPORT_PX_TO_INCHES_Y
        width = shape_spec.width_px * EXPORT_PX_TO_INCHES_X
        height = shape_spec.height_px * EXPORT_PX_TO_INCHES_Y

        shape_type_map = {
            "rectangle": MSO_SHAPE.RECTANGLE,
            "rounded_rectangle": MSO_SHAPE.ROUNDED_RECTANGLE,
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

        if shape_spec.text:
            tf = shape.text_frame
            tf.word_wrap = True
            tf.auto_size = MSO_AUTO_SIZE.NONE

            tf.margin_left = Emu(91440)
            tf.margin_right = Emu(91440)
            tf.margin_top = Emu(45720)
            tf.margin_bottom = Emu(45720)

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

    # --- 룰 기반 요소 추출 ---

    def extract_elements(self, slide, section: Tag) -> None:
        """section에서 요소를 추출하여 슬라이드에 배치."""
        self._extract_legacy_elements(slide, section)

    def _extract_legacy_elements(self, slide, section: Tag) -> None:
        for child in section.children:
            if not isinstance(child, Tag):
                continue
            style = parse_inline_style(child.get("style", ""))

            if child.name in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span", "ul", "ol"):
                if child.get_text(strip=True):
                    self._add_textbox(slide, child, style)
            else:
                text = child.get_text(strip=True)
                if text:
                    self._add_textbox(slide, child, style)

    def _build_textbox_from_fragments(
        self, slide, fragments: list[RichTextFragment],
        left: float, top: float, width: float, height: float,
    ) -> None:
        """RichTextFragment 리스트를 python-pptx 텍스트박스로 변환."""
        txbox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txbox.text_frame
        tf.word_wrap = True

        current_para = tf.paragraphs[0]
        is_first_para = True

        for frag in fragments:
            if not frag.text:
                continue

            if frag.paragraph_break and not is_first_para:
                current_para = tf.add_paragraph()

            run = current_para.add_run()
            run.text = frag.text
            run.font.name = PPTX_FONT_NAME
            scaled_size = scale_font_size(frag.font_size)
            if scaled_size:
                run.font.size = Pt(scaled_size)
            run.font.bold = frag.bold
            run.font.italic = frag.italic
            if frag.color:
                rgb = parse_color(frag.color)
                if rgb:
                    run.font.color.rgb = rgb

            if frag.bullet_level >= 0 and frag.paragraph_break:
                self._apply_bullet(current_para, frag.bullet_level)

            if frag.paragraph_break:
                is_first_para = False

    def extract_flex_columns(
        self, slide, region_div: Tag,
        left: float, top: float, width: float, height: float,
    ) -> bool:
        """flex 컨테이너가 있으면 자식을 개별 텍스트박스로 분할 배치. 처리했으면 True 반환."""
        flex_container = None
        for child in region_div.children:
            if not isinstance(child, Tag):
                continue
            child_style = parse_inline_style(child.get("style", ""))
            display = child_style.get("display", "")
            if "flex" in display and child.name == "div":
                flex_container = child
                break

        if flex_container is None:
            return False

        flex_style = parse_inline_style(flex_container.get("style", ""))
        flex_children = [c for c in flex_container.children if isinstance(c, Tag)]
        if len(flex_children) < 2:
            return False

        gap_str = flex_style.get("gap", "0")
        gap_match = re.match(r"(\d+(?:\.\d+)?)\s*px", gap_str)
        gap_px = float(gap_match.group(1)) if gap_match else 0
        gap_inches = gap_px * EXPORT_PX_TO_INCHES_X

        n = len(flex_children)
        total_gap = gap_inches * (n - 1)
        col_width = (width - total_gap) / n

        for i, col_child in enumerate(flex_children):
            col_left = left + i * (col_width + gap_inches)
            fragments = walk_region_content(col_child, parent_style={}, bullet_level=-1)
            if fragments:
                self._build_textbox_from_fragments(slide, fragments, col_left, top, col_width, height)

        return True

    def _add_textbox(self, slide, element: Tag, style: dict[str, str]) -> None:
        left, top, width, height = get_position_and_size(style)
        txbox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txbox.text_frame
        tf.word_wrap = True

        font_size = extract_font_size(style)
        bold = is_bold(element, style)
        color = extract_color(style)

        text = element.get_text(separator="\n", strip=True)
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = line.strip()
            for run in p.runs:
                run.font.name = PPTX_FONT_NAME
                if font_size:
                    run.font.size = Pt(font_size)
                run.font.bold = bold
                if color:
                    run.font.color.rgb = color

    def add_textbox_at(
        self, slide, element: Tag,
        left: float, top: float, width: float, height: float,
        is_title: bool = False,
    ) -> None:
        """region 좌표를 직접 사용하여 텍스트박스를 배치."""
        txbox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txbox.text_frame
        tf.word_wrap = True

        style = parse_inline_style(element.get("style", ""))
        font_size = extract_font_size(style)
        color = extract_color(style)

        text = element.get_text(separator="\n", strip=True)
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = line.strip()
            for run in p.runs:
                run.font.name = PPTX_FONT_NAME
                if font_size:
                    run.font.size = Pt(font_size)
                run.font.bold = is_title
                if color:
                    run.font.color.rgb = color

    def add_shape(self, slide, element: Tag, style: dict[str, str]) -> None:
        """HTML 요소를 도형으로 변환하여 슬라이드에 추가."""
        left, top, width, height = get_position_and_size(style)
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height),
        )
        text = element.get_text(strip=True)
        if text:
            tf = shape.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = text
            for run in p.runs:
                run.font.name = PPTX_FONT_NAME
