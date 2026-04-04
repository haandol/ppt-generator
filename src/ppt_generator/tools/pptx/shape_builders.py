"""도형(AutoShape, Connector) 생성 모듈.

PptxShape spec을 python-pptx 슬라이드 요소로 변환하는 함수를 제공한다.
- AutoShape: 일반 도형 (rectangle, ellipse, arrow 등) + 텍스트
- Connector: 직선/화살표 + dash style
- Freeform: freeform_builder 모듈에서 re-export
"""

from __future__ import annotations

from lxml.etree import SubElement
from pptx.enum.shapes import MSO_CONNECTOR_TYPE, MSO_SHAPE
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
from ppt_generator.interfaces.schemas import PptxShape
from ppt_generator.tools.pptx.freeform_builder import add_freeform_from_svg
from ppt_generator.tools.pptx.text_formatter import (
    apply_line_spacing,
    apply_vertical_alignment,
    format_paragraphs,
    parse_color,
)

__all__ = [
    "add_auto_shape_from_spec",
    "add_connector_from_spec",
    "add_freeform_from_svg",
]


# shape_type 문자열 → MSO_SHAPE 매핑
_SHAPE_TYPE_MAP = {
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

# 선/화살표 전용 dash_style 매핑 (OOXML prstDash 유효값 사용)
_DASH_STYLE_MAP = {
    "dash": "dash",
    "dot": "sysDot",
}

# 수평/수직 스냅 임계값 (px): 이 값 이하면 의도하지 않은 오차로 판단
_SNAP_THRESHOLD = 12

# rounded_rectangle 기본 라운딩 (corner_radius_px가 null일 때, HTML 렌더러와 동일)
_ROUNDED_RECT_DEFAULT_RADIUS_PX = 8.0


def add_auto_shape_from_spec(slide, shape_spec: PptxShape) -> None:
    """일반 도형(AutoShape) + 텍스트를 슬라이드에 추가."""
    left = shape_spec.left_px * EXPORT_PX_TO_INCHES_X
    top = shape_spec.top_px * EXPORT_PX_TO_INCHES_Y
    width = shape_spec.width_px * EXPORT_PX_TO_INCHES_X
    height = shape_spec.height_px * EXPORT_PX_TO_INCHES_Y

    mso_shape = _SHAPE_TYPE_MAP.get(shape_spec.shape_type, MSO_SHAPE.RECTANGLE)

    shape = slide.shapes.add_shape(
        mso_shape,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(height),
    )

    # rounded_rectangle의 corner_radius 적용 (OOXML adj = radius / shorter_side * 100000)
    # null이면 HTML 렌더러와 동일한 기본값 8px 사용
    if shape_spec.shape_type == "rounded_rectangle":
        radius = shape_spec.corner_radius_px or _ROUNDED_RECT_DEFAULT_RADIUS_PX
        shorter_side = min(shape_spec.width_px, shape_spec.height_px)
        if shorter_side > 0:
            adj_val = int(radius / shorter_side * 100000)
            spPr = shape._element.find(qn("p:spPr"))
            prstGeom = spPr.find(qn("a:prstGeom"))
            if prstGeom is not None:
                avLst = prstGeom.find(qn("a:avLst"))
                if avLst is None:
                    avLst = SubElement(prstGeom, qn("a:avLst"))
                gd = SubElement(avLst, qn("a:gd"))
                gd.set("name", "adj")
                gd.set("fmla", f"val {adj_val}")

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

        apply_vertical_alignment(tf, shape_spec.vertical_alignment or "top")

    elif shape_spec.text:
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

        apply_vertical_alignment(tf, shape_spec.vertical_alignment or "top")

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


def add_connector_from_spec(slide, shape_spec: PptxShape) -> None:
    """Line shape를 python-pptx Connector(직선)로 생성하고 화살표 머리를 설정."""
    w = shape_spec.width_px
    h = shape_spec.height_px
    abs_h = abs(h)
    if w > 0 and 0 < abs_h <= _SNAP_THRESHOLD:
        h = 0  # 수평선 보정
    elif abs_h > 0 and 0 < w <= _SNAP_THRESHOLD:
        w = 0  # 수직선 보정

    need_flip = h < 0
    abs_h = abs(h)

    # 바운딩 박스 좌표 계산: add_connector는 내부에서 xfrm으로 변환하므로
    # 음수 height인 경우 top을 끝점(더 위)으로 맞추고 flipV로 방향 보정
    box_left = shape_spec.left_px
    box_top = shape_spec.top_px + h if need_flip else shape_spec.top_px

    start_x = Inches(box_left * EXPORT_PX_TO_INCHES_X)
    start_y = Inches(box_top * EXPORT_PX_TO_INCHES_Y)
    end_x = Inches((box_left + w) * EXPORT_PX_TO_INCHES_X)
    end_y = Inches((box_top + abs_h) * EXPORT_PX_TO_INCHES_Y)

    connector = slide.shapes.add_connector(
        MSO_CONNECTOR_TYPE.STRAIGHT,
        start_x,
        start_y,
        end_x,
        end_y,
    )

    # 음수 height → flipV 설정 (좌하→우상 대각선)
    if need_flip:
        spPr = connector._element.find(qn("p:spPr"))
        xfrm = spPr.find(qn("a:xfrm"))
        if xfrm is not None:
            xfrm.set("flipV", "1")

    if shape_spec.border_color:
        rgb = parse_color(shape_spec.border_color)
        if rgb:
            connector.line.color.rgb = rgb
    if shape_spec.border_width_pt:
        connector.line.width = Pt(shape_spec.border_width_pt)

    # OOXML a:ln 자식 순서: solidFill → prstDash → round/bevel/miter → headEnd → tailEnd
    spPr = connector._element.find(qn("p:spPr"))
    ln = spPr.find(qn("a:ln"))
    if ln is None:
        ln = SubElement(spPr, qn("a:ln"))

    # 대시 스타일 (headEnd/tailEnd보다 먼저 삽입해야 함)
    dash_key = (shape_spec.dash_style or "").lower()
    prstDash = _DASH_STYLE_MAP.get(dash_key)
    if prstDash:
        dash_el = SubElement(ln, qn("a:prstDash"))
        dash_el.set("val", prstDash)

    # 화살표 머리 설정
    if shape_spec.start_arrow:
        head = SubElement(ln, qn("a:headEnd"))
        head.set("type", "triangle")
        head.set("w", "med")
        head.set("len", "med")

    if shape_spec.end_arrow:
        tail = SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
