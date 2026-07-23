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
from ppt_generator.interfaces.line_geometry import line_endpoints
from ppt_generator.interfaces.schemas import PptxShape
from ppt_generator.interfaces.text_measurement import (
    calculate_shrink_font_scale,
    scaled_line_spacing_pt,
)
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

# rounded_rectangle 기본 라운딩 (corner_radius_px가 null일 때, HTML 렌더러와 동일)
_ROUNDED_RECT_DEFAULT_RADIUS_PX = 8.0

# 컴팩트 라벨 도형(번호 뱃지 등) 판별 임계.
# 작은 도형 + 짧은 단일 텍스트는 한 줄 라벨이 의도다 — PPTX 의 자동 줄바꿈이
# "01" 같은 번호를 세로로 쪼개지 않도록 word_wrap 을 끈다.
_COMPACT_BADGE_MAX_PX = 64.0
_COMPACT_BADGE_MAX_CHARS = 4


# shrink_text 측정 시 padding 기본값 (HTML 렌더러 shape_to_html 과 동일).
_DEFAULT_SHAPE_PADDING_LR_PX = PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU / PX_TO_EMU
_DEFAULT_SHAPE_PADDING_TB_PX = PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU / PX_TO_EMU


def _resolved_padding_lr(value: float | None) -> float:
    """좌우 padding 을 해석한다 (None 이면 HTML 렌더러와 동일한 기본값)."""
    return value if value is not None else _DEFAULT_SHAPE_PADDING_LR_PX


def _resolved_padding_tb(value: float | None) -> float:
    """상하 padding 을 해석한다 (None 이면 HTML 렌더러와 동일한 기본값)."""
    return value if value is not None else _DEFAULT_SHAPE_PADDING_TB_PX


def _is_compact_label(shape_spec: PptxShape, text: str) -> bool:
    """작은 도형 안의 짧은 단일 라벨인지 — 줄바꿈을 끄는 게 맞는 케이스인지."""
    if "\n" in text:
        return False
    if len(text.strip()) > _COMPACT_BADGE_MAX_CHARS:
        return False
    return (
        abs(shape_spec.width_px) <= _COMPACT_BADGE_MAX_PX
        and abs(shape_spec.height_px) <= _COMPACT_BADGE_MAX_PX
    )


def _apply_shape_margins(tf, shape_spec: PptxShape) -> None:
    """도형 텍스트 프레임 내부 여백을 spec padding(없으면 기본값)으로 설정."""
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


def _apply_compact_margins(tf) -> None:
    """컴팩트 라벨 도형 — 내부 여백을 0으로 두어 짧은 텍스트가 한 줄에 들어가게."""
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)


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

    if shape_spec.rotation:
        shape.rotation = shape_spec.rotation

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
        para_text = "".join(
            run.text for para in shape_spec.paragraphs for run in para.runs
        )
        # 컴팩트 라벨(번호 뱃지 등)은 줄바꿈을 끄고 내부 여백도 없애 한 줄 유지.
        compact = _is_compact_label(shape_spec, para_text)
        tf.word_wrap = not compact
        tf.auto_size = MSO_AUTO_SIZE.NONE

        if compact:
            _apply_compact_margins(tf)
        else:
            _apply_shape_margins(tf, shape_spec)

        # shrink_text autofit: 텍스트가 박스 높이를 넘으면 폰트를 비례 축소한다
        # (HTML 렌더러 shape_to_html 과 동일). expand_height 는 박스가 늘어나므로 제외.
        # 컴팩트 라벨은 여백 0·한 줄이므로 축소 불필요.
        font_scale = 1.0
        if not compact and shape_spec.autofit_mode != "expand_height":
            font_scale = calculate_shrink_font_scale(
                shape_spec.paragraphs,
                shape_spec.width_px,
                shape_spec.height_px,
                line_spacing_pt=shape_spec.line_spacing_pt,
                padding_left_px=_resolved_padding_lr(shape_spec.padding_left_px),
                padding_right_px=_resolved_padding_lr(shape_spec.padding_right_px),
                padding_top_px=_resolved_padding_tb(shape_spec.padding_top_px),
                padding_bottom_px=_resolved_padding_tb(shape_spec.padding_bottom_px),
            )

        format_paragraphs(tf, shape_spec.paragraphs, font_scale=font_scale)

        # shrink_text 로 폰트를 축소했으면 line_spacing 도 같은 비율로 축소해야
        # 소비 높이가 실제로 줄어 오버플로가 해소된다 (HTML 렌더러와 공유 헬퍼).
        effective_line_spacing = scaled_line_spacing_pt(
            shape_spec.line_spacing_pt, font_scale
        )
        if effective_line_spacing:
            apply_line_spacing(
                tf,
                effective_line_spacing,
                shape_spec.paragraphs,
                font_scale=font_scale,
            )

        apply_vertical_alignment(tf, shape_spec.vertical_alignment or "top")

    elif shape_spec.text:
        tf = shape.text_frame
        # 컴팩트 라벨(번호 뱃지 등)은 줄바꿈을 끄고 내부 여백도 없애 한 줄 유지.
        compact = _is_compact_label(shape_spec, shape_spec.text)
        tf.word_wrap = not compact
        tf.auto_size = MSO_AUTO_SIZE.NONE

        if compact:
            _apply_compact_margins(tf)
        else:
            _apply_shape_margins(tf, shape_spec)

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
    """Line shape 를 python-pptx Connector(직선)로 생성하고 화살표 머리를 설정.

    spec convention: (left, top) 은 라인 bounding box 의 최소 좌표 모서리이고
    박스는 (left, top)~(left+|w|, top+|h|) 를 차지한다. w/h 의 부호는 두 끝점의
    대각 방향만 정한다 — 양수면 시작=최소 모서리, 끝=최대 모서리이고 음수면 그
    축의 시작/끝이 뒤바뀐다. HTML 렌더러도 이 convention 을 따른다
    (shape_renderer._line_shape_to_html).

    python-pptx 의 add_connector 가 begin/end 좌표 비교로 flipH/flipV 를 자동
    설정하므로 호출자는 begin/end 좌표만 정확히 넘기면 된다.
    """
    begin_px, end_px = line_endpoints(
        shape_spec.left_px,
        shape_spec.top_px,
        shape_spec.width_px,
        shape_spec.height_px,
    )

    begin_x = Inches(begin_px[0] * EXPORT_PX_TO_INCHES_X)
    begin_y = Inches(begin_px[1] * EXPORT_PX_TO_INCHES_Y)
    end_x = Inches(end_px[0] * EXPORT_PX_TO_INCHES_X)
    end_y = Inches(end_px[1] * EXPORT_PX_TO_INCHES_Y)

    connector = slide.shapes.add_connector(
        MSO_CONNECTOR_TYPE.STRAIGHT,
        begin_x,
        begin_y,
        end_x,
        end_y,
    )

    # 회전: import 는 회전 前 bbox 기준 좌표 + rotation 을 저장하므로 export 도
    # 동일하게 begin/end(회전 前) 에 rotation 을 얹어야 왕복이 맞는다.
    if shape_spec.rotation:
        connector.rotation = shape_spec.rotation

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
