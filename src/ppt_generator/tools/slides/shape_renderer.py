"""PptxShape -> HTML 변환 렌더러.

Line, Custom SVG, AutoShape 등 도형 유형별 HTML 렌더링을 담당한다.
"""

from __future__ import annotations

import os

from ppt_generator.interfaces.constants import (
    PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU,
    PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU,
    PX_TO_EMU,
)
from ppt_generator.interfaces.schemas import PptxShape
from ppt_generator.interfaces.text_measurement import should_apply_nowrap_to_paragraph
from ppt_generator.tools.slides.text_renderer import escape_html, paragraph_to_html

# CSS clip-path polygon 매핑: shape_type → polygon points
_CLIP_PATH_MAP: dict[str, str] = {
    # Arrows
    "up_arrow": "polygon(50% 0%, 100% 40%, 70% 40%, 70% 100%, 30% 100%, 30% 40%, 0% 40%)",
    "down_arrow": "polygon(30% 0%, 70% 0%, 70% 60%, 100% 60%, 50% 100%, 0% 60%, 30% 60%)",
    "left_arrow": "polygon(40% 0%, 40% 30%, 100% 30%, 100% 70%, 40% 70%, 40% 100%, 0% 50%)",
    "right_arrow": "polygon(0% 30%, 60% 30%, 60% 0%, 100% 50%, 60% 100%, 60% 70%, 0% 70%)",
    "chevron": "polygon(0% 0%, 75% 0%, 100% 50%, 75% 100%, 0% 100%, 25% 50%)",
    # Polygons
    "triangle": "polygon(50% 0%, 100% 100%, 0% 100%)",
    "diamond": "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)",
    "pentagon": "polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%)",
    "hexagon": "polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)",
    "trapezoid": "polygon(20% 0%, 80% 0%, 100% 100%, 0% 100%)",
    "parallelogram": "polygon(20% 0%, 100% 0%, 80% 100%, 0% 100%)",
    "cross": "polygon(35% 0%, 65% 0%, 65% 35%, 100% 35%, 100% 65%, 65% 65%, 65% 100%, 35% 100%, 35% 65%, 0% 65%, 0% 35%, 35% 35%)",
    # Stars
    "star_4": "polygon(50% 0%, 62% 38%, 100% 50%, 62% 62%, 50% 100%, 38% 62%, 0% 50%, 38% 38%)",
    "star_5": "polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)",
    "heart": "polygon(50% 18%, 62% 0%, 82% 0%, 100% 18%, 100% 40%, 50% 100%, 0% 40%, 0% 18%, 18% 0%, 38% 0%)",
    # Flowchart
    "flowchart_process": None,  # rectangle (no clip needed)
    "flowchart_decision": "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)",
    "flowchart_terminator": None,  # rounded_rectangle variant (handled via border-radius)
}

_ARROW_SIZE = 14  # 화살표 머리 길이 (px)
_ARROW_HALF = 10  # 화살표 머리 높이 (px)


def _line_shape_to_html(shape: PptxShape) -> str:
    """Line shape -> position:absolute <svg> 변환 (화살표/대시 지원)."""
    stroke_color = shape.border_color or "#ffffff"
    stroke_width = shape.border_width_pt or 1

    w = shape.width_px
    h = shape.height_px

    _SNAP_THRESHOLD = 12
    abs_h_snap = abs(h)
    if w > 0 and 0 < abs_h_snap <= _SNAP_THRESHOLD:
        h = 0
    elif abs_h_snap > 0 and 0 < w <= _SNAP_THRESHOLD:
        w = 0

    pad = max(stroke_width * 2, 8)
    abs_h = abs(h) if h != 0 else 1
    svg_w = w + pad * 2
    svg_h = abs_h + pad * 2

    if h >= 0:
        x1, y1 = pad, pad
        x2 = w + pad
        y2 = h + pad
    else:
        # Negative height: line goes from bottom-left to top-right (↗)
        x1, y1 = pad, abs_h + pad
        x2 = w + pad
        y2 = pad

    dash_attr = ""
    if shape.dash_style == "dash":
        dash_attr = f' stroke-dasharray="{stroke_width * 4},{stroke_width * 3}"'
    elif shape.dash_style == "dot":
        dash_attr = f' stroke-dasharray="{stroke_width},{stroke_width * 2}"'

    defs_parts: list[str] = []
    line_attrs = ""

    line_length = max(w, abs(h), 1)
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
        defs_html = f"<defs>{''.join(defs_parts)}</defs>"

    # 음수 height(flipV) 의미: 박스는 (left, top)~(left+w, top+|h|) 그대로 두되
    # 라인이 좌하→우상으로 그려진다. container_top은 항상 top_px - pad.
    container_top = shape.top_px - pad
    container_style = (
        f"position:absolute;"
        f"left:{shape.left_px - pad}px;top:{container_top}px;"
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


def _custom_svg_shape_to_html(shape: PptxShape) -> str:
    """Custom SVG path shape -> position:absolute <svg> 변환."""
    svg_path = shape.svg_path or ""
    parts = svg_path.split(" ", 2)
    if len(parts) < 3:
        return f'<div style="position:absolute;left:{shape.left_px}px;top:{shape.top_px}px;width:{shape.width_px}px;height:{shape.height_px}px;"></div>'
    vb_w, vb_h, path_d = parts[0], parts[1], parts[2]

    fill = shape.fill_color or "none"
    stroke = shape.border_color or "none"
    stroke_width = shape.border_width_pt or 0

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {vb_w} {vb_h}" '
        f'preserveAspectRatio="none" '
        f'style="position:absolute;left:{shape.left_px}px;top:{shape.top_px}px;'
        f'width:{shape.width_px}px;height:{shape.height_px}px;overflow:visible;">'
        f'<path d="{path_d}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{stroke_width}" />'
        f"</svg>"
    )
    return svg


_IMAGE_EXTENSIONS = frozenset(
    (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tiff")
)


def _is_image_path(path: str) -> bool:
    """svg_path 값이 이미지 파일 경로인지 판별한다."""
    _, ext = os.path.splitext(path.lower().split("?")[0])
    return ext in _IMAGE_EXTENSIONS


def _image_shape_to_html(shape: PptxShape) -> str:
    """이미지 경로를 가진 shape -> position:absolute <div><img></div> 변환."""
    radius_css = ""
    if shape.corner_radius_px:
        radius_css = f"border-radius:{shape.corner_radius_px}px;"
    bg_css = ""
    if shape.fill_color:
        bg_css = f"background-color:{shape.fill_color};"
    border_css = ""
    if shape.border_color:
        bw = shape.border_width_pt or 1
        border_css = f"border:{bw}pt solid {shape.border_color};"
    style = (
        f"position:absolute;"
        f"left:{shape.left_px}px;top:{shape.top_px}px;"
        f"width:{shape.width_px}px;height:{shape.height_px}px;"
        f"{bg_css}{border_css}{radius_css}"
        f"overflow:hidden;padding:0;box-sizing:border-box;"
    )
    img_radius = radius_css
    return (
        f'<div style="{style}">'
        f'<img src="{shape.svg_path}" '
        f'style="width:100%;height:100%;object-fit:cover;{img_radius}" alt="image" />'
        f"</div>"
    )


def shape_to_html(shape: PptxShape) -> str:
    """PptxShape -> position:absolute <div> 변환."""
    if shape.shape_type == "line":
        return _line_shape_to_html(shape)
    if shape.svg_path and _is_image_path(shape.svg_path):
        return _image_shape_to_html(shape)
    if shape.shape_type == "custom" and shape.svg_path:
        return _custom_svg_shape_to_html(shape)

    expand = getattr(shape, "autofit_mode", None) == "expand_height"
    height_prop = "min-height" if expand else "height"
    style = (
        f"position:absolute;"
        f"left:{shape.left_px}px;top:{shape.top_px}px;"
        f"width:{shape.width_px}px;{height_prop}:{shape.height_px}px;"
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
    if shape.shape_type == "flowchart_terminator":
        style += f"border-radius:{min(shape.width_px, shape.height_px) / 2}px;"

    clip_path = _CLIP_PATH_MAP.get(shape.shape_type)
    if clip_path:
        style += f"clip-path:{clip_path};"

    style += "overflow:visible;" if expand else "overflow:hidden;"

    default_lr = PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU / PX_TO_EMU
    default_tb = PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU / PX_TO_EMU
    pl = shape.padding_left_px if shape.padding_left_px is not None else default_lr
    pr = shape.padding_right_px if shape.padding_right_px is not None else default_lr
    pt_ = shape.padding_top_px if shape.padding_top_px is not None else default_tb
    pb = shape.padding_bottom_px if shape.padding_bottom_px is not None else default_tb
    style += f"padding:{pt_}px {pr}px {pb}px {pl}px;box-sizing:border-box;"

    if shape.line_spacing_pt:
        style += f"line-height:{shape.line_spacing_pt}pt;"

    if shape.text and not shape.paragraphs:
        style += "display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;"
    elif shape.vertical_alignment == "middle":
        style += "display:flex;flex-direction:column;justify-content:center;"
    elif shape.vertical_alignment == "bottom":
        style += "display:flex;flex-direction:column;justify-content:flex-end;"

    inner = ""
    if shape.paragraphs:
        usable_w = shape.width_px - pl - pr
        # 단일 paragraph인 경우에만 nowrap 판정 (multi-paragraph는 의도된 줄바꿈)
        single_para = len(shape.paragraphs) == 1
        para_parts: list[str] = []
        for para in shape.paragraphs:
            apply_nowrap = single_para and should_apply_nowrap_to_paragraph(
                para, usable_w
            )
            para_parts.append(paragraph_to_html(para, nowrap=apply_nowrap))
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
