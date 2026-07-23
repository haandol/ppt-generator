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
from ppt_generator.interfaces.line_geometry import line_endpoints
from ppt_generator.interfaces.schemas import PptxShape
from ppt_generator.interfaces.text_measurement import (
    calculate_shrink_font_scale,
    scaled_line_spacing_pt,
    should_apply_nowrap_to_paragraph,
)
from ppt_generator.tools.slides.html_safety import (
    css_number,
    escape_attr,
    safe_color,
    safe_image_src,
    safe_number,
    safe_svg_path,
)
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


def _rotation_css(shape: PptxShape) -> str:
    """도형 회전(rotation degree)을 CSS transform 으로 변환한다.

    CSS transform:rotate 의 기본 origin 은 요소 중심(50% 50%)이고, PPTX rot 도
    bbox 중심 기준이라 그대로 대응된다. line/custom 컨테이너는 pad 가 상하좌우
    대칭이라 컨테이너 중심 == bbox 중심이므로 별도 origin 보정이 필요 없다.
    """
    rot = safe_number(getattr(shape, "rotation", 0.0))
    if not rot or rot % 360 == 0:
        return ""
    return f"transform:rotate({css_number(rot % 360)}deg);"


def _elbow_connector_to_html(
    shape: PptxShape, stroke_color: str, stroke_width: float
) -> str:
    """꺾인 커넥터를 직각 <polyline> 로 렌더 (화살표/대시 지원).

    elbow_points 는 bbox 대비 정규화 좌표([[fx,fy],...])다. bbox(left/top/width/height)
    로 실제 픽셀 좌표를 만들고, 화살표 마커·대시는 직선 커넥터와 동일 규칙으로 적용한다.
    """
    left = safe_number(shape.left_px)
    top = safe_number(shape.top_px)
    w = abs(safe_number(shape.width_px))
    h = abs(safe_number(shape.height_px))

    pad = max(stroke_width * 2, 8)
    svg_w = (w or 1) + pad * 2
    svg_h = (h or 1) + pad * 2

    pts = []
    for p in shape.elbow_points or []:
        try:
            fx = safe_number(p[0])
            fy = safe_number(p[1])
        except (IndexError, TypeError):
            continue
        pts.append((pad + fx * w, pad + fy * h))
    if len(pts) < 2:
        return ""
    points_attr = " ".join(f"{css_number(x)},{css_number(y)}" for x, y in pts)

    dash_attr = ""
    if shape.dash_style == "dash":
        dash_attr = (
            f' stroke-dasharray="{css_number(stroke_width * 4)},'
            f'{css_number(stroke_width * 3)}"'
        )
    elif shape.dash_style == "dot":
        dash_attr = (
            f' stroke-dasharray="{css_number(stroke_width)},'
            f'{css_number(stroke_width * 2)}"'
        )

    line_length = max(w, h, 1)
    aw = min(_ARROW_SIZE, line_length * 0.6)
    ah = min(_ARROW_HALF, aw * _ARROW_HALF / _ARROW_SIZE)
    ah2 = ah / 2
    defs_parts: list[str] = []
    line_attrs = ""
    if shape.end_arrow:
        defs_parts.append(
            f'<marker id="ah-end" markerWidth="{css_number(aw)}" '
            f'markerHeight="{css_number(ah)}" '
            f'refX="{css_number(aw)}" refY="{css_number(ah2)}" '
            f'orient="auto" markerUnits="userSpaceOnUse">'
            f'<polygon points="0 0, {css_number(aw)} {css_number(ah2)}, '
            f'0 {css_number(ah)}" fill="{stroke_color}" /></marker>'
        )
        line_attrs += ' marker-end="url(#ah-end)"'
    if shape.start_arrow:
        defs_parts.append(
            f'<marker id="ah-start" markerWidth="{css_number(aw)}" '
            f'markerHeight="{css_number(ah)}" '
            f'refX="0" refY="{css_number(ah2)}" '
            f'orient="auto" markerUnits="userSpaceOnUse">'
            f'<polygon points="{css_number(aw)} 0, 0 {css_number(ah2)}, '
            f'{css_number(aw)} {css_number(ah)}" fill="{stroke_color}" /></marker>'
        )
        line_attrs += ' marker-start="url(#ah-start)"'
    defs_html = f"<defs>{''.join(defs_parts)}</defs>" if defs_parts else ""

    container_style = (
        f"position:absolute;"
        f"left:{css_number(left - pad)}px;top:{css_number(top - pad)}px;"
        f"width:{css_number(svg_w)}px;height:{css_number(svg_h)}px;"
        f"overflow:visible;pointer-events:none;{_rotation_css(shape)}"
    )
    return (
        f'<svg style="{container_style}" '
        f'width="{css_number(svg_w)}" height="{css_number(svg_h)}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"{defs_html}"
        f'<polyline points="{points_attr}" fill="none" '
        f'stroke="{stroke_color}" stroke-width="{css_number(stroke_width)}"'
        f"{dash_attr}{line_attrs} />"
        f"</svg>"
    )


def _line_shape_to_html(shape: PptxShape) -> str:
    """Line shape -> position:absolute <svg> 변환 (화살표/대시 지원)."""
    stroke_color = safe_color(shape.border_color, "#ffffff")
    stroke_width = safe_number(shape.border_width_pt, 1.0)
    if stroke_width <= 0:
        stroke_width = 1.0

    # 꺾인 커넥터(elbow): 정규화 폴리라인 꼭짓점을 직각 polyline 으로 렌더
    if getattr(shape, "elbow_points", None):
        return _elbow_connector_to_html(shape, stroke_color, stroke_width)

    left = safe_number(shape.left_px)
    top = safe_number(shape.top_px)
    w = safe_number(shape.width_px)
    h = safe_number(shape.height_px)

    pad = max(stroke_width * 2, 8)
    # bbox 계약: (left, top) 은 항상 최소 좌표 모서리이고 박스는
    # (left, top)~(left+|w|, top+|h|) 를 차지한다. width/height 의 부호는
    # 선의 기울기 방향만 정한다 (음수 → 반대 방향 끝점). 어떤 부호 조합이든
    # 두 끝점이 박스의 올바른 대각 꼭짓점에 오도록 대칭으로 정규화한다.
    abs_w = abs(w)
    abs_h = abs(h)
    # svg 캔버스는 0px 이 되지 않도록 최소 1px 확보 (끝점 좌표엔 실제 |w|/|h| 사용).
    svg_w = (abs_w or 1) + pad * 2
    svg_h = (abs_h or 1) + pad * 2

    (x1, y1), (x2, y2) = line_endpoints(pad, pad, w, h)

    dash_attr = ""
    if shape.dash_style == "dash":
        dash_attr = (
            f' stroke-dasharray="{css_number(stroke_width * 4)},'
            f'{css_number(stroke_width * 3)}"'
        )
    elif shape.dash_style == "dot":
        dash_attr = (
            f' stroke-dasharray="{css_number(stroke_width)},'
            f'{css_number(stroke_width * 2)}"'
        )

    defs_parts: list[str] = []
    line_attrs = ""

    line_length = max(abs_w, abs_h, 1)
    aw = min(_ARROW_SIZE, line_length * 0.6)
    ah = min(_ARROW_HALF, aw * _ARROW_HALF / _ARROW_SIZE)
    ah2 = ah / 2

    if shape.end_arrow:
        defs_parts.append(
            f'<marker id="ah-end" markerWidth="{css_number(aw)}" '
            f'markerHeight="{css_number(ah)}" '
            f'refX="{css_number(aw)}" refY="{css_number(ah2)}" '
            f'orient="auto" markerUnits="userSpaceOnUse">'
            f'<polygon points="0 0, {css_number(aw)} {css_number(ah2)}, '
            f'0 {css_number(ah)}" fill="{stroke_color}" />'
            f"</marker>"
        )
        line_attrs += ' marker-end="url(#ah-end)"'

    if shape.start_arrow:
        defs_parts.append(
            f'<marker id="ah-start" markerWidth="{css_number(aw)}" '
            f'markerHeight="{css_number(ah)}" '
            f'refX="0" refY="{css_number(ah2)}" '
            f'orient="auto" markerUnits="userSpaceOnUse">'
            f'<polygon points="{css_number(aw)} 0, 0 {css_number(ah2)}, '
            f'{css_number(aw)} {css_number(ah)}" fill="{stroke_color}" />'
            f"</marker>"
        )
        line_attrs += ' marker-start="url(#ah-start)"'

    defs_html = ""
    if defs_parts:
        defs_html = f"<defs>{''.join(defs_parts)}</defs>"

    # (left, top) 은 최소 좌표 모서리이므로 컨테이너 원점은 부호와 무관하게
    # 항상 (left - pad, top - pad) 다. 부호는 위에서 끝점 방향으로만 반영했다.
    container_top = top - pad
    container_style = (
        f"position:absolute;"
        f"left:{css_number(left - pad)}px;top:{css_number(container_top)}px;"
        f"width:{css_number(svg_w)}px;height:{css_number(svg_h)}px;"
        f"overflow:visible;pointer-events:none;{_rotation_css(shape)}"
    )

    return (
        f'<svg style="{container_style}" '
        f'width="{css_number(svg_w)}" height="{css_number(svg_h)}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f"{defs_html}"
        f'<line x1="{css_number(x1)}" y1="{css_number(y1)}" '
        f'x2="{css_number(x2)}" y2="{css_number(y2)}" '
        f'stroke="{stroke_color}" stroke-width="{css_number(stroke_width)}"'
        f"{dash_attr}{line_attrs} />"
        f"</svg>"
    )


def _custom_svg_shape_to_html(shape: PptxShape) -> str:
    """Custom SVG path shape -> position:absolute <svg> 변환."""
    parsed_path = safe_svg_path(shape.svg_path or "")
    if parsed_path is None:
        return (
            f'<div style="position:absolute;left:{css_number(shape.left_px)}px;'
            f"top:{css_number(shape.top_px)}px;"
            f"width:{css_number(shape.width_px)}px;"
            f'height:{css_number(shape.height_px)}px;"></div>'
        )
    vb_w, vb_h, path_d = parsed_path

    fill = safe_color(shape.fill_color, "none")
    stroke = safe_color(shape.border_color, "none")
    stroke_width = max(safe_number(shape.border_width_pt), 0)

    # viewBox 는 도형의 원본 좌표계(EMU 단위, 예: 315407×331499)이고 실제 렌더 박스는
    # width_px×height_px(예: 108×113)다. preserveAspectRatio="none" 로 매핑되면
    # stroke-width 도 viewBox 스케일만큼 축소돼 라인아트 선이 사실상 소멸한다.
    # vector-effect="non-scaling-stroke" 는 stroke-width 를 viewBox 스케일과
    # 무관하게 화면 픽셀 단위로 해석하므로, line shape 와 동일하게 pt 값을 px 선폭으로
    # 그대로 쓸 수 있다 (Chromium 등 최신 브라우저 지원).
    stroke_attr = ""
    if stroke != "none":
        stroke_attr = (
            f' stroke="{stroke}" stroke-width="{css_number(stroke_width)}" '
            f'vector-effect="non-scaling-stroke"'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {css_number(vb_w)} {css_number(vb_h)}" '
        f'preserveAspectRatio="none" '
        f'style="position:absolute;left:{css_number(shape.left_px)}px;'
        f"top:{css_number(shape.top_px)}px;"
        f"width:{css_number(shape.width_px)}px;"
        f"height:{css_number(shape.height_px)}px;overflow:visible;"
        f'{_rotation_css(shape)}">'
        f'<path d="{escape_attr(path_d)}" fill="{fill}"{stroke_attr} />'
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
    image_src = safe_image_src(shape.svg_path or "")
    if image_src is None:
        return ""
    left = safe_number(shape.left_px)
    top = safe_number(shape.top_px)
    width = safe_number(shape.width_px)
    height = safe_number(shape.height_px)
    radius = max(safe_number(shape.corner_radius_px), 0)
    radius_css = ""
    if radius:
        radius_css = f"border-radius:{css_number(radius)}px;"
    bg_css = ""
    if shape.fill_color:
        fill_color = safe_color(shape.fill_color)
        if fill_color:
            bg_css = f"background-color:{fill_color};"
    border_css = ""
    if shape.border_color:
        bw = safe_number(shape.border_width_pt, 1.0)
        if bw <= 0:
            bw = 1.0
        border_color = safe_color(shape.border_color)
        if border_color:
            border_css = f"border:{css_number(bw)}pt solid {border_color};"
    style = (
        f"position:absolute;"
        f"left:{css_number(left)}px;top:{css_number(top)}px;"
        f"width:{css_number(width)}px;height:{css_number(height)}px;"
        f"{bg_css}{border_css}{radius_css}"
        f"overflow:hidden;padding:0;box-sizing:border-box;"
    )
    img_radius = radius_css
    return (
        f'<div style="{style}">'
        f'<img src="{escape_attr(image_src)}" '
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

    left = safe_number(shape.left_px)
    top = safe_number(shape.top_px)
    width = safe_number(shape.width_px)
    height = safe_number(shape.height_px)
    expand = getattr(shape, "autofit_mode", None) == "expand_height"
    height_prop = "min-height" if expand else "height"
    style = (
        f"position:absolute;"
        f"left:{css_number(left)}px;top:{css_number(top)}px;"
        f"width:{css_number(width)}px;{height_prop}:{css_number(height)}px;"
        f"{_rotation_css(shape)}"
    )
    if shape.fill_color:
        fill_color = safe_color(shape.fill_color)
        if fill_color:
            style += f"background-color:{fill_color};"
    if shape.border_color:
        bw = safe_number(shape.border_width_pt, 1.0)
        if bw <= 0:
            bw = 1.0
        border_color = safe_color(shape.border_color)
        if border_color:
            style += f"border:{css_number(bw)}pt solid {border_color};"
    radius = max(safe_number(shape.corner_radius_px), 0)
    if radius:
        style += f"border-radius:{css_number(radius)}px;"
    if shape.shape_type == "rounded_rectangle" and not shape.corner_radius_px:
        style += "border-radius:8px;"
    if shape.shape_type == "ellipse":
        style += "border-radius:50%;"
    if shape.shape_type == "flowchart_terminator":
        style += f"border-radius:{css_number(min(width, height) / 2)}px;"

    clip_path = _CLIP_PATH_MAP.get(shape.shape_type)
    if clip_path:
        style += f"clip-path:{clip_path};"

    style += "overflow:visible;" if expand else "overflow:hidden;"

    default_lr = PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU / PX_TO_EMU
    default_tb = PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU / PX_TO_EMU
    has_text = bool(shape.text) or any(
        run.text for para in shape.paragraphs for run in para.runs
    )
    if has_text:
        pl = safe_number(shape.padding_left_px, default_lr)
        pr = safe_number(shape.padding_right_px, default_lr)
        pt_ = safe_number(shape.padding_top_px, default_tb)
        pb = safe_number(shape.padding_bottom_px, default_tb)
    else:
        # Empty PowerPoint shapes can retain large, irrelevant text margins.
        # CSS otherwise expands the border box beyond its declared width.
        pl = pr = pt_ = pb = 0.0
    style += (
        f"padding:{css_number(pt_)}px {css_number(pr)}px "
        f"{css_number(pb)}px {css_number(pl)}px;box-sizing:border-box;"
    )

    line_spacing = safe_number(shape.line_spacing_pt)

    # shrink_text autofit: 필요 높이가 박스 높이를 초과하면 폰트를 비례 축소한다.
    # expand_height 는 박스가 늘어나므로 축소 불필요. paragraphs 경로에서만 산출하며
    # line-height 도 같은 비율로 축소해야 소비 높이가 실제로 줄어 오버플로가 해소된다.
    font_scale = 1.0
    if shape.paragraphs and not expand:
        # text-overflow lint 와 동일한 15% 여유를 두어, 경계 케이스에서
        # 불필요하게 축소하지 않는다. 축소 하한은 절대 10pt(가독성 floor).
        # PPTX 빌더(shape_builders)와 동일한 공유 헬퍼를 사용해 두 출력의
        # 폰트 크기가 일치하도록 한다.
        try:
            font_scale = calculate_shrink_font_scale(
                shape.paragraphs,
                width,
                height,
                line_spacing_pt=line_spacing or None,
                padding_left_px=pl,
                padding_right_px=pr,
                padding_top_px=pt_,
                padding_bottom_px=pb,
            )
        except (TypeError, ValueError, OverflowError):
            font_scale = 1.0

    para_line_height_pt: float | None = None
    if line_spacing > 0:
        effective_ls = scaled_line_spacing_pt(line_spacing, font_scale) or line_spacing
        style += f"line-height:{css_number(effective_ls)}pt;"
        para_line_height_pt = effective_ls

    if shape.text and not shape.paragraphs:
        style += "display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;"
    elif shape.vertical_alignment == "middle":
        style += "display:flex;flex-direction:column;justify-content:center;"
    elif shape.vertical_alignment == "bottom":
        style += "display:flex;flex-direction:column;justify-content:flex-end;"

    inner = ""
    if shape.paragraphs:
        usable_w = width - pl - pr
        para_parts: list[str] = []
        for para in shape.paragraphs:
            try:
                apply_nowrap = should_apply_nowrap_to_paragraph(para, usable_w)
            except (TypeError, ValueError, OverflowError):
                apply_nowrap = False
            para_parts.append(
                paragraph_to_html(
                    para,
                    nowrap=apply_nowrap,
                    font_scale=font_scale,
                    line_height_pt=para_line_height_pt,
                )
            )
        inner = "".join(para_parts)
    elif shape.text:
        text_style = ""
        if shape.text_color:
            text_color = safe_color(shape.text_color)
            if text_color:
                text_style += f"color:{text_color};"
        text_size = safe_number(shape.text_size_pt)
        if text_size > 0:
            text_style += f"font-size:{css_number(text_size)}pt;"
        if shape.text_bold:
            text_style += "font-weight:bold;"
        escaped = escape_html(shape.text).replace("\n", "<br>")
        inner = f'<span style="{text_style}">{escaped}</span>'

    return f'<div style="{style}">{inner}</div>'
