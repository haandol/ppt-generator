"""PptxSlideSpec -> HTML 변환 렌더러.

PptxSlideSpec 요소를 position:absolute HTML div로 결정론적 변환한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import (
    PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU,
    PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU,
    PX_TO_EMU,
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)


def escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def run_to_html(run: PptxTextRun) -> str:
    """PptxTextRun -> <span> 변환."""
    styles: list[str] = []
    if run.font_size_pt:
        styles.append(f"font-size:{run.font_size_pt}pt")
    if run.color:
        styles.append(f"color:{run.color}")
    if run.bold:
        styles.append("font-weight:bold")
    if run.italic:
        styles.append("font-style:italic")
    if run.font_family == "monospace":
        styles.append("font-family:'Source Code Pro',Consolas,'Courier New',monospace")

    text = escape_html(run.text)
    if styles:
        return f'<span style="{";".join(styles)}">{text}</span>'
    return text


def paragraph_to_html(para: PptxParagraph) -> str:
    """PptxParagraph -> HTML 변환."""
    runs_html = "".join(run_to_html(r) for r in para.runs)
    align_style = ""
    if para.alignment:
        align_style = f' style="text-align:{para.alignment}"'

    if para.bullet_level >= 0:
        indent = 20 * (para.bullet_level + 1)
        return f'<li style="margin-left:{indent}px{(";text-align:" + para.alignment) if para.alignment else ""}">{runs_html}</li>'
    return f"<p{align_style}>{runs_html}</p>"


def textbox_to_html(tb: PptxTextBox) -> str:
    """PptxTextBox -> position:absolute <div> 변환."""
    style = (
        f"position:absolute;"
        f"left:{tb.left_px}px;top:{tb.top_px}px;"
        f"width:{tb.width_px}px;height:{tb.height_px}px;"
        f"padding:0;box-sizing:border-box;"
        f"overflow:visible;"
    )
    if tb.line_spacing_pt:
        style += f"line-height:{tb.line_spacing_pt}pt;"
    if tb.vertical_alignment == "middle":
        style += "display:flex;flex-direction:column;justify-content:center;"
    elif tb.vertical_alignment == "bottom":
        style += "display:flex;flex-direction:column;justify-content:flex-end;"

    # 불릿 그룹핑
    has_bullets = any(p.bullet_level >= 0 for p in tb.paragraphs)
    inner_parts: list[str] = []
    if has_bullets:
        bullet_items: list[str] = []
        for para in tb.paragraphs:
            html = paragraph_to_html(para)
            if para.bullet_level >= 0:
                bullet_items.append(html)
            else:
                if bullet_items:
                    inner_parts.append(f'<ul style="list-style:disc;padding-left:20px;margin:0">{"".join(bullet_items)}</ul>')
                    bullet_items = []
                inner_parts.append(html)
        if bullet_items:
            inner_parts.append(f'<ul style="list-style:disc;padding-left:20px;margin:0">{"".join(bullet_items)}</ul>')
    else:
        for para in tb.paragraphs:
            inner_parts.append(paragraph_to_html(para))

    return f'<div style="{style}">{"".join(inner_parts)}</div>'


_ARROW_SIZE = 14  # 화살표 머리 길이 (px)
_ARROW_HALF = 10  # 화살표 머리 높이 (px)


def _line_shape_to_html(shape: PptxShape) -> str:
    """Line shape -> position:absolute <svg> 변환 (화살표/대시 지원)."""
    stroke_color = shape.border_color or "#ffffff"
    stroke_width = shape.border_width_pt or 1

    w = shape.width_px
    h = shape.height_px

    # 수평/수직 스냅: 한쪽이 지배적이면 나머지를 0으로 보정
    # LLM이 height_px=10 등 작은 값을 넣는 패턴 대응
    _SNAP_THRESHOLD = 12  # px 이하면 의도하지 않은 오차로 판단
    if w > 0 and 0 < h <= _SNAP_THRESHOLD:
        h = 0  # 수평선
    elif h > 0 and 0 < w <= _SNAP_THRESHOLD:
        w = 0  # 수직선

    # SVG 영역: 화살표 머리가 잘리지 않도록 여유(pad) 확보
    pad = max(stroke_width * 2, 8)
    svg_w = w + pad * 2
    svg_h = max(h, 1) + pad * 2

    x1, y1 = pad, pad
    x2 = w + pad
    y2 = h + pad

    # 대시 스타일
    dash_attr = ""
    if shape.dash_style == "dash":
        dash_attr = f' stroke-dasharray="{stroke_width * 4},{stroke_width * 3}"'
    elif shape.dash_style == "dot":
        dash_attr = f' stroke-dasharray="{stroke_width},{stroke_width * 2}"'

    # 마커 정의 (화살표 머리)
    defs_parts: list[str] = []
    line_attrs = ""

    # 화살표 머리 크기: 선 길이가 짧으면 자동 축소
    line_length = max(w, h, 1)
    aw = min(_ARROW_SIZE, line_length * 0.6)
    ah = min(_ARROW_HALF, aw * _ARROW_HALF / _ARROW_SIZE)
    ah2 = ah / 2

    if shape.end_arrow:
        defs_parts.append(
            f'<marker id="ah-end" markerWidth="{aw}" markerHeight="{ah}" '
            f'refX="{aw}" refY="{ah2}" orient="auto" markerUnits="userSpaceOnUse">'
            f'<polygon points="0 0, {aw} {ah2}, 0 {ah}" fill="{stroke_color}" />'
            f"</marker>"
        )
        line_attrs += ' marker-end="url(#ah-end)"'

    if shape.start_arrow:
        defs_parts.append(
            f'<marker id="ah-start" markerWidth="{aw}" markerHeight="{ah}" '
            f'refX="0" refY="{ah2}" orient="auto" markerUnits="userSpaceOnUse">'
            f'<polygon points="{aw} 0, 0 {ah2}, {aw} {ah}" fill="{stroke_color}" />'
            f"</marker>"
        )
        line_attrs += ' marker-start="url(#ah-start)"'

    defs_html = ""
    if defs_parts:
        defs_html = f'<defs>{"".join(defs_parts)}</defs>'

    container_style = (
        f"position:absolute;"
        f"left:{shape.left_px - pad}px;top:{shape.top_px - pad}px;"
        f"width:{svg_w}px;height:{svg_h}px;"
        f"overflow:visible;pointer-events:none;"
    )

    return (
        f'<svg style="{container_style}" '
        f'width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">'
        f"{defs_html}"
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke_color}" stroke-width="{stroke_width}"{dash_attr}{line_attrs} />'
        f"</svg>"
    )


def shape_to_html(shape: PptxShape) -> str:
    """PptxShape -> position:absolute <div> 변환."""
    if shape.shape_type == "line":
        return _line_shape_to_html(shape)

    style = (
        f"position:absolute;"
        f"left:{shape.left_px}px;top:{shape.top_px}px;"
        f"width:{shape.width_px}px;height:{shape.height_px}px;"
    )
    if shape.fill_color:
        style += f"background-color:{shape.fill_color};"
    if shape.border_color:
        bw = shape.border_width_pt or 1
        style += f"border:{bw}pt solid {shape.border_color};"
    if shape.corner_radius_px:
        style += f"border-radius:{shape.corner_radius_px}px;"
    if shape.shape_type == "rounded_rectangle" and not shape.corner_radius_px:
        style += "border-radius:8px;"
    if shape.shape_type == "ellipse":
        style += "border-radius:50%;"

    style += "overflow:hidden;"

    # 패딩 (PPTX 기본값: 45720/22860 EMU -> px 변환)
    default_lr = PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU / PX_TO_EMU
    default_tb = PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU / PX_TO_EMU
    pl = shape.padding_left_px if shape.padding_left_px is not None else default_lr
    pr = shape.padding_right_px if shape.padding_right_px is not None else default_lr
    pt_ = shape.padding_top_px if shape.padding_top_px is not None else default_tb
    pb = shape.padding_bottom_px if shape.padding_bottom_px is not None else default_tb
    style += f"padding:{pt_}px {pr}px {pb}px {pl}px;box-sizing:border-box;"

    # line-height (shape.line_spacing_pt)
    if shape.line_spacing_pt:
        style += f"line-height:{shape.line_spacing_pt}pt;"

    # 수직 정렬 (shape.text만 있을 때는 PPTX가 무조건 anchor="ctr")
    if shape.text and not shape.paragraphs:
        style += "display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;"
    elif shape.vertical_alignment == "middle":
        style += "display:flex;flex-direction:column;justify-content:center;"
    elif shape.vertical_alignment == "bottom":
        style += "display:flex;flex-direction:column;justify-content:flex-end;"

    inner = ""
    if shape.paragraphs:
        para_parts: list[str] = []
        for para in shape.paragraphs:
            para_parts.append(paragraph_to_html(para))
        inner = "".join(para_parts)
    elif shape.text:
        text_style = ""
        if shape.text_color:
            text_style += f"color:{shape.text_color};"
        if shape.text_size_pt:
            text_style += f"font-size:{shape.text_size_pt}pt;"
        if shape.text_bold:
            text_style += "font-weight:bold;"
        escaped = escape_html(shape.text).replace("\n", "<br>")
        inner = f'<span style="{text_style}">{escaped}</span>'

    return f'<div style="{style}">{inner}</div>'


def spec_to_html_section(
    slide_index: int,
    spec: PptxSlideSpec,
    *,
    bg_image_base64: str | None = None,
    logo_image_base64: str | None = None,
) -> str:
    """PptxSlideSpec 하나를 <section> HTML로 결정론적 변환."""
    bg = spec.background_color or "#1a1a2e"
    notes_attr = ""
    if spec.speaker_notes:
        escaped_notes = spec.speaker_notes.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
        notes_attr = f' data-speaker-notes="{escaped_notes}"'

    bg_image_css = ""
    if bg_image_base64:
        bg_image_css = (
            f"background-image:url(data:image/png;base64,{bg_image_base64});"
            "background-size:cover;background-position:center;"
        )

    parts: list[str] = []
    parts.append(
        f'<section id="slide-{slide_index}"{notes_attr}>'
        f'<div style="position:absolute;top:0;left:0;right:0;bottom:0;'
        f'background-color:{bg};{bg_image_css}overflow:hidden;">'
    )

    # shapes를 먼저 렌더링 (z-order 하단)
    for shape in spec.shapes:
        parts.append(shape_to_html(shape))

    # textboxes를 나중에 렌더링 (z-order 상단)
    for tb in spec.textboxes:
        parts.append(textbox_to_html(tb))

    # 로고 이미지 (우측 하단)
    if logo_image_base64:
        parts.append(
            f'<img src="data:image/png;base64,{logo_image_base64}" '
            'style="position:absolute;bottom:45px;right:50px;width:100px;height:auto;" />'
        )

    parts.append("</div></section>")
    return "\n".join(parts)
