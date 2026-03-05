"""PptxSlideSpec -> HTML 변환 렌더러.

PptxSlideSpec 요소를 position:absolute HTML div로 결정론적 변환한다.
텍스트 렌더링은 text_renderer, 도형 렌더링은 shape_renderer 모듈에서 처리한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.tools.slides.shape_renderer import shape_to_html
from ppt_generator.tools.slides.text_renderer import (
    escape_html,
    paragraph_to_html,
    run_to_html,
)

__all__ = [
    "escape_html",
    "run_to_html",
    "paragraph_to_html",
    "textbox_to_html",
    "image_to_html",
    "shape_to_html",
    "spec_to_html_section",
]


def textbox_to_html(tb: PptxTextBox) -> str:
    """PptxTextBox -> position:absolute <div> 변환."""
    pl = tb.padding_left_px or 0
    pr = tb.padding_right_px or 0
    pt_ = tb.padding_top_px or 0
    pb = tb.padding_bottom_px or 0
    style = (
        f"position:absolute;"
        f"left:{tb.left_px}px;top:{tb.top_px}px;"
        f"width:{tb.width_px}px;height:{tb.height_px}px;"
        f"padding:{pt_}px {pr}px {pb}px {pl}px;box-sizing:border-box;"
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


# SVG 이미지 아이콘 (산/태양 형태)
_IMAGE_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" '
    'fill="none" stroke="rgba(128,128,128,0.6)" stroke-width="1.5" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>'
    '<circle cx="8.5" cy="8.5" r="1.5"/>'
    '<polyline points="21 15 16 10 5 21"/>'
    "</svg>"
)


def image_to_html(image: PptxImage, *, image_src: str | None = None) -> str:
    """PptxImage -> position:absolute <div> 변환."""
    pos_style = (
        f"position:absolute;"
        f"left:{image.left_px}px;top:{image.top_px}px;"
        f"width:{image.width_px}px;height:{image.height_px}px;"
    )
    if image_src:
        style = pos_style + "overflow:hidden;"
        return (
            f'<div style="{style}">'
            f'<img src="{image_src}" '
            f'style="width:100%;height:100%;object-fit:contain" alt="image" />'
            "</div>"
        )
    style = (
        pos_style
        + "background:rgba(128,128,128,0.15);"
        "border:1px dashed rgba(128,128,128,0.4);"
        "display:flex;flex-direction:column;align-items:center;justify-content:center;"
        "box-sizing:border-box;overflow:hidden;"
    )
    return (
        f'<div style="{style}">'
        f"{_IMAGE_ICON_SVG}"
        '<span style="font-size:9pt;color:rgba(128,128,128,0.6);margin-top:4px">IMAGE</span>'
        "</div>"
    )


def spec_to_html_section(
    slide_index: int,
    spec: PptxSlideSpec,
    *,
    bg_image_base64: str | None = None,
    image_srcs: list[str] | None = None,
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

    srcs = image_srcs or []

    parts: list[str] = []
    parts.append(
        f'<section id="slide-{slide_index}"{notes_attr}>'
        f'<div style="position:absolute;top:0;left:0;right:0;bottom:0;'
        f'background-color:{bg};{bg_image_css}overflow:hidden;">'
    )

    for shape in spec.shapes:
        parts.append(shape_to_html(shape))

    for i, image in enumerate(spec.images):
        src = srcs[i] if i < len(srcs) else None
        parts.append(image_to_html(image, image_src=src))

    for tb in spec.textboxes:
        parts.append(textbox_to_html(tb))

    parts.append("</div></section>")
    return "\n".join(parts)
