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

from ppt_generator.interfaces.constants import IMPORT_EMU_TO_PX

if TYPE_CHECKING:
    from pptx.presentation import Presentation

logger = logging.getLogger(__name__)


@dataclass
class DefaultRunProps:
    """OOXML 상속 체인에서 추출한 기본 run 서식.

    line_spacing_pct / line_spacing_pt 는 해당 레벨의 a:pPr > a:lnSpc 에서 온다.
    lnSpc 는 run 이 아니라 문단(pPr) 속성이지만, 폰트 크기와 같은 상속 체인
    (layout lstStyle → master txStyle)을 타므로 함께 캐시한다.
    - spcPct(백분율 배수, 예 90% → 0.9) → line_spacing_pct
    - spcPts(절대 pt) → line_spacing_pt
    둘 중 하나만 설정된다. pct 는 렌더 시 폰트 크기와 곱해 pt 로 환산한다.
    """

    font_size_pt: int | None = None
    color: str | None = None
    bold: bool | None = None
    font_name: str | None = None
    line_spacing_pct: float | None = None
    line_spacing_pt: float | None = None
    default_tab_size_px: float | None = None


def extract_line_spacing_from_ppr(
    pPr_el: Element | None,
) -> tuple[float | None, float | None]:
    """a:pPr > a:lnSpc 에서 (배수 pct, 절대 pt) 를 추출한다.

    Returns:
        (line_spacing_pct, line_spacing_pt). lnSpc 가 없으면 (None, None).
        spcPct 는 100000 단위(90000 → 0.9), spcPts 는 100 단위(1200 → 12pt).
    """
    if pPr_el is None:
        return None, None
    ln_spc = pPr_el.find(qn("a:lnSpc"))
    if ln_spc is None:
        return None, None
    spc_pct = ln_spc.find(qn("a:spcPct"))
    if spc_pct is not None:
        val = spc_pct.get("val")
        if val is not None:
            return int(val) / 100000, None
    spc_pts = ln_spc.find(qn("a:spcPts"))
    if spc_pts is not None:
        val = spc_pts.get("val")
        if val is not None:
            return None, int(val) / 100
    return None, None


def extract_default_tab_size_from_ppr(pPr_el: Element | None) -> float | None:
    """문단 스타일의 defTabSz(EMU)를 px로 변환한다."""
    if pPr_el is None:
        return None
    raw = pPr_el.get("defTabSz")
    if raw is None:
        return None
    try:
        return round(int(raw) * IMPORT_EMU_TO_PX, 1)
    except (TypeError, ValueError):
        return None


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
    # 명시적 latin 폰트명 (예: "Amazon Ember Display"). "+mj-lt"/"+mn-lt" 는
    # 테마 참조이므로 폰트명으로 저장하지 않고, 상속 소비 측의 테마 폴백에 맡긴다.
    font_name: str | None = None
    latin = rpr_el.find(qn("a:latin"))
    if latin is not None:
        tf = latin.get("typeface")
        if tf and not tf.startswith("+"):
            font_name = tf
    return DefaultRunProps(
        font_size_pt=font_size_pt, color=color, bold=bold, font_name=font_name
    )


def extract_theme_fonts_for_master(master) -> dict[str, str]:
    """마스터 테마의 fontScheme 에서 major(+mj-lt)/minor(+mn-lt) latin 폰트를 추출.

    Returns:
        {"major": "<폰트명>", "minor": "<폰트명>"} (없으면 빈 dict).
        placeholder 나 run 에 명시적 폰트가 없을 때의 상속 폴백으로 사용한다.
    """
    fonts: dict[str, str] = {}
    try:
        theme_part = None
        for rel in master.part.rels.values():
            if "theme" in rel.reltype:
                theme_part = rel.target_part
                break
        if theme_part is None:
            return fonts

        from xml.etree.ElementTree import fromstring

        theme_xml = fromstring(theme_part.blob)
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        font_scheme = theme_xml.find(".//a:fontScheme", ns)
        if font_scheme is None:
            return fonts
        major = font_scheme.find("a:majorFont/a:latin", ns)
        minor = font_scheme.find("a:minorFont/a:latin", ns)
        major_tf = major.get("typeface") if major is not None else None
        minor_tf = minor.get("typeface") if minor is not None else None
        if major_tf:
            fonts["major"] = major_tf
        if minor_tf:
            fonts["minor"] = minor_tf
    except Exception:
        logger.debug("테마 폰트 추출 실패", exc_info=True)
    return fonts


def extract_theme_color_map_for_master(master) -> dict[str, str]:
    """특정 슬라이드 마스터의 테마에서 실제 색상 맵을 추출.

    프레젠테이션에 마스터가 여러 개인 경우(다크/라이트 테마 혼재 등) 각 슬라이드가
    소속된 마스터의 clrScheme + clrMap 을 사용해야 배경/텍스트 색이 올바르게 해석된다.
    """
    color_map: dict[str, str] = {}
    try:
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


def extract_theme_color_map(presentation: Presentation) -> dict[str, str]:
    """프레젠테이션 첫 마스터의 테마 색상 맵을 추출 (하위 호환용).

    슬라이드별 정확한 색상 해석에는 extract_theme_color_map_for_master() 를 사용한다.
    """
    try:
        return extract_theme_color_map_for_master(presentation.slide_masters[0])
    except Exception:
        logger.debug("테마 색상 맵 추출 실패, 폴백 사용", exc_info=True)
        return {}


def extract_master_tx_styles(
    presentation: Presentation,
    master=None,
) -> dict[str, dict[int, DefaultRunProps]]:
    """마스터의 p:txStyles에서 titleStyle/bodyStyle/otherStyle의 레벨별 기본 서식을 추출.

    master 를 넘기면 해당 마스터를, 없으면 첫 마스터를 사용한다. 멀티 마스터
    프레젠테이션에서는 슬라이드가 소속된 마스터를 넘겨야 서식이 올바르게 상속된다.

    Returns:
        {"titleStyle": {0: props, 1: props, ...}, "bodyStyle": {...}, "otherStyle": {...}}
    """
    result: dict[str, dict[int, DefaultRunProps]] = {}
    try:
        if master is None:
            master = presentation.slide_masters[0]
        txStyles = master.element.find(qn("p:txStyles"))
        if txStyles is None:
            return result

        theme_map = extract_theme_color_map_for_master(master)

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
                props = extract_props_from_rpr(def_rPr, theme_map)
                pct, pts = extract_line_spacing_from_ppr(lvl_pPr)
                props.line_spacing_pct = pct
                props.line_spacing_pt = pts
                props.default_tab_size_px = extract_default_tab_size_from_ppr(lvl_pPr)
                if any(
                    value is not None
                    for value in (
                        props.font_size_pt,
                        props.color,
                        props.bold,
                        props.font_name,
                        props.line_spacing_pct,
                        props.line_spacing_pt,
                        props.default_tab_size_px,
                    )
                ):
                    level_map[lvl_idx] = props
            result[style_name] = level_map
    except Exception:
        logger.debug("마스터 txStyles 추출 실패", exc_info=True)
    return result
