"""OOXML 테마 색상 해석 모듈.

프레젠테이션 테마에서 색상 맵을 추출하고, scheme color를 RGB로 resolve한다.
마스터 슬라이드의 txStyles(titleStyle/bodyStyle/otherStyle) 기본 서식도 추출한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from pptx.oxml.ns import qn

if TYPE_CHECKING:
    from pptx.presentation import Presentation

logger = logging.getLogger(__name__)


@dataclass
class DefaultRunProps:
    """OOXML 상속 체인에서 추출한 기본 run 서식."""

    font_size_pt: int | None = None
    color: str | None = None
    bold: bool | None = None


# Office 기본 테마 색상 폴백 매핑
SCHEME_FALLBACK: dict[str, str] = {
    "bg1": "#FFFFFF",
    "bg2": "#E7E6E6",
    "tx1": "#000000",
    "tx2": "#44546A",
    "lt1": "#FFFFFF",
    "lt2": "#E7E6E6",
    "dk1": "#000000",
    "dk2": "#44546A",
    "accent1": "#4472C4",
    "accent2": "#ED7D31",
    "accent3": "#A5A5A5",
    "accent4": "#FFC000",
    "accent5": "#5B9BD5",
    "accent6": "#70AD47",
    "hlink": "#0563C1",
    "folHlink": "#954F72",
}

# placeholder type → master txStyle 매핑
PH_TYPE_TO_TXSTYLE: dict[int, str] = {
    1: "titleStyle",  # TITLE
    3: "titleStyle",  # CENTER_TITLE
    15: "titleStyle",  # TITLE (some variants)
    2: "bodyStyle",  # BODY
    7: "bodyStyle",  # OBJECT
    4: "bodyStyle",  # SUBTITLE
}


def resolve_scheme_color(
    scheme_el: Element,
    theme_color_map: dict[str, str] | None = None,
) -> str | None:
    """schemeClr XML 요소에서 RGB 색상을 근사 추출.

    lumMod/lumOff 변환을 지원하며, 테마 색상 맵을 우선 사용하고 Office 기본 팔레트를 폴백으로 사용한다.
    """
    val = scheme_el.get("val", "")

    base_hex: str | None = None
    if theme_color_map:
        base_hex = theme_color_map.get(val)
    if base_hex is None:
        base_hex = SCHEME_FALLBACK.get(val)
    if base_hex is None:
        return None

    lum_mod = scheme_el.find(qn("a:lumMod"))
    lum_off = scheme_el.find(qn("a:lumOff"))
    if lum_mod is not None or lum_off is not None:
        mod = int(lum_mod.get("val", "100000")) / 100000 if lum_mod is not None else 1.0
        off = int(lum_off.get("val", "0")) / 100000 if lum_off is not None else 0.0
        r = int(base_hex[1:3], 16)
        g = int(base_hex[3:5], 16)
        b = int(base_hex[5:7], 16)
        r = min(255, max(0, int(r * mod + 255 * off)))
        g = min(255, max(0, int(g * mod + 255 * off)))
        b = min(255, max(0, int(b * mod + 255 * off)))
        return f"#{r:02X}{g:02X}{b:02X}"

    return base_hex


def extract_color_from_rpr(
    rpr_el: Element | None, theme_color_map: dict[str, str] | None = None
) -> str | None:
    """a:rPr 또는 a:defRPr XML 요소에서 색상을 추출."""
    if rpr_el is None:
        return None
    solid = rpr_el.find(qn("a:solidFill"))
    if solid is None:
        return None
    srgb = solid.find(qn("a:srgbClr"))
    if srgb is not None:
        val = srgb.get("val")
        if val:
            return f"#{val}"
    scheme = solid.find(qn("a:schemeClr"))
    if scheme is not None:
        return resolve_scheme_color(scheme, theme_color_map)
    return None


def extract_props_from_rpr(
    rpr_el: Element | None, theme_color_map: dict[str, str] | None = None
) -> DefaultRunProps:
    """a:rPr 또는 a:defRPr XML 요소에서 font_size, color, bold를 추출."""
    if rpr_el is None:
        return DefaultRunProps()
    font_size_pt: int | None = None
    sz = rpr_el.get("sz")
    if sz is not None:
        font_size_pt = round(int(sz) / 100)
    bold: bool | None = None
    b = rpr_el.get("b")
    if b is not None:
        bold = b == "1" or b.lower() == "true"
    color = extract_color_from_rpr(rpr_el, theme_color_map)
    return DefaultRunProps(font_size_pt=font_size_pt, color=color, bold=bold)


def extract_theme_color_map(presentation: Presentation) -> dict[str, str]:
    """프레젠테이션 테마에서 실제 색상 맵을 추출."""
    color_map: dict[str, str] = {}
    try:
        master = presentation.slide_masters[0]
        theme_part = None
        for rel in master.part.rels.values():
            if "theme" in rel.reltype:
                theme_part = rel.target_part
                break
        if theme_part is None:
            return color_map

        from xml.etree.ElementTree import fromstring

        theme_xml = fromstring(theme_part.blob)

        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        clr_scheme = theme_xml.find(".//a:clrScheme", ns)
        if clr_scheme is None:
            return color_map

        for child in clr_scheme:
            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            srgb = child.find(qn("a:srgbClr"))
            if srgb is not None:
                val = srgb.get("val")
                if val:
                    color_map[tag_name] = f"#{val}"
                    continue
            sys_clr = child.find(qn("a:sysClr"))
            if sys_clr is not None:
                last_clr = sys_clr.get("lastClr")
                if last_clr:
                    color_map[tag_name] = f"#{last_clr}"

        clr_map_el = master.element.find(qn("p:clrMap"))
        if clr_map_el is not None:
            for attr_name, target_name in clr_map_el.attrib.items():
                local_attr = attr_name.split("}")[-1] if "}" in attr_name else attr_name
                if local_attr not in color_map and target_name in color_map:
                    color_map[local_attr] = color_map[target_name]
        else:
            _ALIASES = {"tx1": "dk1", "tx2": "dk2", "bg1": "lt1", "bg2": "lt2"}
            for alias, target in _ALIASES.items():
                if alias not in color_map and target in color_map:
                    color_map[alias] = color_map[target]
    except Exception:
        logger.debug("테마 색상 맵 추출 실패, 폴백 사용", exc_info=True)
    return color_map


def extract_master_tx_styles(
    presentation: Presentation,
) -> dict[str, dict[int, DefaultRunProps]]:
    """마스터의 p:txStyles에서 titleStyle/bodyStyle/otherStyle의 레벨별 기본 서식을 추출.

    Returns:
        {"titleStyle": {0: props, 1: props, ...}, "bodyStyle": {...}, "otherStyle": {...}}
    """
    result: dict[str, dict[int, DefaultRunProps]] = {}
    try:
        master = presentation.slide_masters[0]
        txStyles = master.element.find(qn("p:txStyles"))
        if txStyles is None:
            return result

        theme_map = extract_theme_color_map(presentation)

        for style_name in ("titleStyle", "bodyStyle", "otherStyle"):
            style_el = txStyles.find(qn(f"p:{style_name}"))
            if style_el is None:
                continue
            level_map: dict[int, DefaultRunProps] = {}
            for lvl_idx in range(9):
                lvl_pPr = style_el.find(qn(f"a:lvl{lvl_idx + 1}pPr"))
                if lvl_pPr is None:
                    continue
                def_rPr = lvl_pPr.find(qn("a:defRPr"))
                if def_rPr is not None:
                    level_map[lvl_idx] = extract_props_from_rpr(def_rPr, theme_map)
            result[style_name] = level_map
    except Exception:
        logger.debug("마스터 txStyles 추출 실패", exc_info=True)
    return result
