"""HTML 슬라이드 파싱 모듈.

python-pptx 객체에 의존하지 않는 순수 HTML 파싱 함수들을 모아둔 모듈.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ppt_generator.tools.pptx.style_utils import (
    RichTextFragment,
    extract_font_size,
    merge_styles,
    parse_inline_style,
    resolve_int,
)


def parse_slides(html: str) -> list[Tag]:
    """HTML에서 슬라이드 section 태그들을 파싱."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("body")
    if body:
        return body.find_all("section", recursive=False)
    return soup.find_all("section")


def extract_background(div: Tag) -> str | None:
    """section 태그에서 배경색을 추출."""
    # data-wrapper div에서 먼저 배경색 추출 시도
    wrapper = div.find("div", attrs={"data-wrapper": "true"})
    if wrapper:
        wrapper_style = parse_inline_style(wrapper.get("style", ""))
        bg = wrapper_style.get("background-color") or wrapper_style.get("background")
        if bg:
            color_match = re.search(r"#[0-9a-fA-F]{3,8}", bg)
            if color_match:
                return color_match.group(0)
            rgb_match = re.search(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", bg)
            if rgb_match:
                return bg
            return bg

    # 폴백: section 자체의 style에서 추출
    style = parse_inline_style(div.get("style", ""))
    bg = style.get("background-color") or style.get("background")
    if not bg:
        return None
    # gradient 등 복합 배경에서 첫 번째 색상 추출 시도
    color_match = re.search(r"#[0-9a-fA-F]{3,8}", bg)
    if color_match:
        return color_match.group(0)
    rgb_match = re.search(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", bg)
    if rgb_match:
        return bg
    return bg


def extract_head_html(html: str) -> str:
    """HTML에서 <head> 블록을 추출한다. CSS 스타일 보존용."""
    soup = BeautifulSoup(html, "html.parser")
    head = soup.find("head")
    return str(head) if head else "<head></head>"


def build_single_slide_html(head_html: str, section: Tag) -> str:
    """<head>와 단일 <section>으로 최소 HTML 문서를 구성한다."""
    return (
        f"<!DOCTYPE html><html lang=\"ko\">{head_html}"
        f"<body>{section}</body></html>"
    )


def walk_region_content(
    element: Tag,
    parent_style: dict[str, str | None],
    bullet_level: int = -1,
    is_title_region: bool = False,
) -> list[RichTextFragment]:
    """Region div 내부의 자식 요소를 재귀적으로 순회하며 RichTextFragment 리스트를 생성."""
    fragments: list[RichTextFragment] = []

    for child in element.children:
        if isinstance(child, str):
            # NavigableString (텍스트 노드)
            text = child.strip()
            if text:
                fragments.append(RichTextFragment(
                    text=text,
                    font_size=resolve_int(parent_style.get("font_size")),
                    color=parent_style.get("color"),
                    bold=parent_style.get("bold") is True or is_title_region,
                    italic=parent_style.get("italic") is True,
                    bullet_level=bullet_level,
                ))
            continue

        if not isinstance(child, Tag):
            continue

        tag = child.name
        inline_style = parse_inline_style(child.get("style", ""))

        # 현재 요소의 스타일 결정 (자식 명시 > 부모 상속)
        current_style = merge_styles(parent_style, inline_style, tag)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            heading_text = child.get_text(strip=True)
            if heading_text:
                fs = extract_font_size(inline_style)
                fragments.append(RichTextFragment(
                    text=heading_text,
                    font_size=fs or resolve_int(current_style.get("font_size")),
                    color=current_style.get("color"),
                    bold=True,
                    italic=current_style.get("italic") is True,
                    bullet_level=bullet_level,
                    paragraph_break=True,
                ))
        elif tag == "p":
            sub = walk_region_content(child, current_style, bullet_level, is_title_region)
            if sub:
                sub[0] = RichTextFragment(
                    text=sub[0].text,
                    font_size=sub[0].font_size,
                    color=sub[0].color,
                    bold=sub[0].bold,
                    italic=sub[0].italic,
                    bullet_level=sub[0].bullet_level,
                    paragraph_break=True,
                )
                fragments.extend(sub)
        elif tag in ("ul", "ol"):
            next_level = max(bullet_level + 1, 0)
            for li in child.find_all("li", recursive=False):
                li_style = parse_inline_style(li.get("style", ""))
                li_merged = merge_styles(current_style, li_style, "li")
                li_sub = walk_region_content(li, li_merged, next_level, is_title_region)
                if li_sub:
                    li_sub[0] = RichTextFragment(
                        text=li_sub[0].text,
                        font_size=li_sub[0].font_size,
                        color=li_sub[0].color,
                        bold=li_sub[0].bold,
                        italic=li_sub[0].italic,
                        bullet_level=next_level,
                        paragraph_break=True,
                    )
                    fragments.extend(li_sub)
                else:
                    li_text = li.get_text(strip=True)
                    if li_text:
                        fragments.append(RichTextFragment(
                            text=li_text,
                            font_size=resolve_int(li_merged.get("font_size")),
                            color=li_merged.get("color"),
                            bold=li_merged.get("bold") is True,
                            italic=li_merged.get("italic") is True,
                            bullet_level=next_level,
                            paragraph_break=True,
                        ))
        elif tag in ("strong", "b"):
            sub = walk_region_content(child, {**current_style, "bold": True}, bullet_level, is_title_region)
            fragments.extend(sub)
            if not sub:
                text = child.get_text(strip=True)
                if text:
                    fragments.append(RichTextFragment(
                        text=text,
                        font_size=resolve_int(current_style.get("font_size")),
                        color=current_style.get("color"),
                        bold=True,
                        italic=current_style.get("italic") is True,
                        bullet_level=bullet_level,
                    ))
        elif tag in ("em", "i"):
            sub = walk_region_content(child, {**current_style, "italic": True}, bullet_level, is_title_region)
            fragments.extend(sub)
            if not sub:
                text = child.get_text(strip=True)
                if text:
                    fragments.append(RichTextFragment(
                        text=text,
                        font_size=resolve_int(current_style.get("font_size")),
                        color=current_style.get("color"),
                        bold=current_style.get("bold") is True,
                        italic=True,
                        bullet_level=bullet_level,
                    ))
        elif tag in ("div", "span", "li"):
            sub = walk_region_content(child, current_style, bullet_level, is_title_region)
            fragments.extend(sub)
        else:
            # 기타 요소: 텍스트만 추출
            text = child.get_text(strip=True)
            if text:
                fragments.append(RichTextFragment(
                    text=text,
                    font_size=resolve_int(current_style.get("font_size")),
                    color=current_style.get("color"),
                    bold=current_style.get("bold") is True or is_title_region,
                    italic=current_style.get("italic") is True,
                    bullet_level=bullet_level,
                ))

    return fragments
