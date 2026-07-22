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
from ppt_generator.interfaces.text_measurement import (
    calculate_shrink_font_scale,
    estimate_text_width_px,
    scaled_line_spacing_pt,
    should_apply_nowrap_to_paragraph,
)
from ppt_generator.tools.slides.html_safety import (
    css_number,
    css_url,
    escape_attr,
    safe_base64_data,
    safe_color,
    safe_image_src,
    safe_number,
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
    left = safe_number(tb.left_px)
    top = safe_number(tb.top_px)
    width = safe_number(tb.width_px)
    height = safe_number(tb.height_px)
    pl = safe_number(tb.padding_left_px)
    pr = safe_number(tb.padding_right_px)
    pt_ = safe_number(tb.padding_top_px)
    pb = safe_number(tb.padding_bottom_px)
    style = (
        f"position:absolute;"
        f"left:{css_number(left)}px;top:{css_number(top)}px;"
        f"width:{css_number(width)}px;height:{css_number(height)}px;"
        f"padding:{css_number(pt_)}px {css_number(pr)}px "
        f"{css_number(pb)}px {css_number(pl)}px;box-sizing:border-box;"
        f"overflow:visible;"
    )
    line_spacing = safe_number(tb.line_spacing_pt)

    # 불릿 그룹핑
    has_bullets = any(p.bullet_level >= 0 for p in tb.paragraphs)
    usable_w = width - pl - pr

    # shrink_text autofit: 텍스트가 박스 높이를 넘으면 폰트를 비례 축소해
    # 헤더/푸터가 넘쳐 이웃과 겹치거나 잘리는 것을 막는다. 박스에 들어가면 scale=1.0.
    # PPTX 빌더(slide_builder)와 동일한 공유 헬퍼를 사용한다.
    # autofit_font_scale(normAutofit 의 저장된 스케일)이 있으면 그대로 적용한다.
    # autofit="none"(noAutofit) / "resize"(spAutoFit) 는 축소 없이 원본 크기 유지.
    explicit_scale = getattr(tb, "autofit_font_scale", None)
    if explicit_scale is not None:
        font_scale = explicit_scale
    elif getattr(tb, "autofit", "shrink") != "shrink":
        font_scale = 1.0
    else:
        try:
            font_scale = calculate_shrink_font_scale(
                tb.paragraphs,
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

    # 폰트를 축소했으면 line-height 도 같은 비율로 축소해야 소비 높이가 실제로 줄어
    # 오버플로가 해소된다 (shape_renderer 와 동일한 공유 헬퍼).
    # line-height 는 컨테이너 div 뿐 아니라 각 <p>/<li> 에도 직접 적용해야 한다.
    # 전역 CSS 의 `p{line-height:1.5}` 가 컨테이너 상속을 덮어써서, div 에만 걸면
    # 실제 문단은 1.5 로 렌더돼 줄이 벌어지고 박스를 넘친다 (import/0003).
    para_line_height_pt: float | None = None
    if line_spacing > 0:
        effective_ls = scaled_line_spacing_pt(line_spacing, font_scale) or line_spacing
        style += f"line-height:{css_number(effective_ls)}pt;"
        para_line_height_pt = effective_ls
    if tb.vertical_alignment == "middle":
        style += "display:flex;flex-direction:column;justify-content:center;"
    elif tb.vertical_alignment == "bottom":
        style += "display:flex;flex-direction:column;justify-content:flex-end;"

    inner_parts: list[str] = []
    if has_bullets:
        bullet_items: list[str] = []
        for para in tb.paragraphs:
            html = paragraph_to_html(
                para, font_scale=font_scale, line_height_pt=para_line_height_pt
            )
            if para.bullet_level >= 0:
                bullet_items.append(html)
            else:
                if bullet_items:
                    inner_parts.append(
                        f'<ul style="list-style:disc;padding-left:20px;margin:0">{"".join(bullet_items)}</ul>'
                    )
                    bullet_items = []
                inner_parts.append(html)
        if bullet_items:
            inner_parts.append(
                f'<ul style="list-style:disc;padding-left:20px;margin:0">{"".join(bullet_items)}</ul>'
            )
    else:
        # autofit="none"(PPTX noAutofit) 단일 문단이 박스 폭을 "근소하게"(≤1.25배)
        # 초과하는 경우만 nowrap 을 강제한다. 원본이 한 줄로 넘치도록 의도한 케이스
        # (예: 타이틀 "AWS HealthImaging")를 PPT 처럼 한 줄로 렌더하기 위함이다.
        # 폭을 크게 초과하는 텍스트(원본도 여러 줄로 wrap)는 nowrap 하지 않는다.
        force_nowrap = False
        if (
            getattr(tb, "autofit", "shrink") == "none"
            and len(tb.paragraphs) == 1
            and not any("\n" in r.text for r in tb.paragraphs[0].runs)
        ):
            try:
                est_w = sum(
                    estimate_text_width_px(
                        r.text,
                        (r.font_size_pt or 16) * font_scale,
                        r.font_family == "monospace",
                    )
                    for r in tb.paragraphs[0].runs
                    if r.text
                )
                force_nowrap = est_w <= usable_w * 1.25
            except (TypeError, ValueError, OverflowError):
                force_nowrap = False
        for para in tb.paragraphs:
            try:
                apply_nowrap = force_nowrap or should_apply_nowrap_to_paragraph(
                    para, usable_w
                )
            except (TypeError, ValueError, OverflowError):
                apply_nowrap = force_nowrap
            inner_parts.append(
                paragraph_to_html(
                    para,
                    nowrap=apply_nowrap,
                    font_scale=font_scale,
                    line_height_pt=para_line_height_pt,
                )
            )

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
    left = safe_number(image.left_px)
    top = safe_number(image.top_px)
    width = safe_number(image.width_px)
    height = safe_number(image.height_px)
    radius = safe_number(image.corner_radius_px)
    radius_css = ""
    if radius > 0:
        radius_css = f"border-radius:{css_number(radius)}px;"
    pos_style = (
        f"position:absolute;"
        f"left:{css_number(left)}px;top:{css_number(top)}px;"
        f"width:{css_number(width)}px;height:{css_number(height)}px;"
        f"{radius_css}"
    )
    safe_src = safe_image_src(image_src) if image_src else None
    if safe_src:
        style = pos_style + "overflow:hidden;"
        img_radius = f"border-radius:{css_number(radius)}px;" if radius > 0 else ""
        # 원형/둥근 클리핑(radius>0)은 프레임을 채워야 크롭이 자연스럽다(PPT 그림 채우기).
        # 일반 이미지는 왜곡 방지를 위해 contain 유지.
        object_fit = "cover" if radius > 0 else "contain"
        return (
            f'<div style="{style}">'
            f'<img src="{escape_attr(safe_src)}" '
            f'style="width:100%;height:100%;object-fit:{object_fit};{img_radius}" alt="image" />'
            "</div>"
        )
    style = (
        pos_style + "background:rgba(128,128,128,0.15);"
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
    bg = safe_color(spec.background_color, "#1a1a2e")
    notes_attr = ""
    if spec.speaker_notes:
        escaped_notes = escape_attr(spec.speaker_notes)
        notes_attr = f' data-speaker-notes="{escaped_notes}"'

    bg_image_css = ""
    if spec.background_image_src:
        safe_bg_src = safe_image_src(spec.background_image_src)
        if safe_bg_src:
            bg_image_css = (
                f"background-image:{css_url(safe_bg_src)};"
                "background-size:cover;background-position:center;"
            )
    elif bg_image_base64 and (safe_bg_data := safe_base64_data(bg_image_base64)):
        bg_image_css = (
            f"background-image:url(data:image/png;base64,{safe_bg_data});"
            "background-size:cover;background-position:center;"
        )

    srcs = image_srcs or []

    parts: list[str] = []
    safe_slide_index = css_number(slide_index)
    parts.append(
        f'<section id="slide-{safe_slide_index}"{notes_attr}>'
        f'<div style="position:absolute;top:0;left:0;right:0;bottom:0;'
        f'background-color:{bg};{bg_image_css}overflow:hidden;">'
    )

    # z_index가 있는 요소와 없는 요소를 구분하여 렌더링
    has_z_index = any(
        getattr(e, "z_index", None) is not None
        for lst in (spec.shapes, spec.images, spec.textboxes)
        for e in lst
    )

    if has_z_index:
        # z_index 순으로 모든 요소를 통합 렌더링
        render_items: list[tuple[float, str]] = []
        for shape in spec.shapes:
            z = safe_number(shape.z_index)
            render_items.append((z, shape_to_html(shape)))
        for i, image in enumerate(spec.images):
            src = srcs[i] if i < len(srcs) else None
            z = safe_number(image.z_index)
            render_items.append((z, image_to_html(image, image_src=src)))
        for tb in spec.textboxes:
            z = safe_number(tb.z_index)
            render_items.append((z, textbox_to_html(tb)))
        render_items.sort(key=lambda x: x[0])
        for _, html in render_items:
            parts.append(html)
    else:
        # z_index 미설정: 기존 순서 (shapes → images → textboxes)
        for shape in spec.shapes:
            parts.append(shape_to_html(shape))
        for i, image in enumerate(spec.images):
            src = srcs[i] if i < len(srcs) else None
            parts.append(image_to_html(image, image_src=src))
        for tb in spec.textboxes:
            parts.append(textbox_to_html(tb))

    parts.append("</div></section>")
    return "\n".join(parts)
