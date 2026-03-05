"""python-pptx 슬라이드 객체에서 PptxSlideSpec을 추출하는 리더 모듈.

SlideBuilder의 역변환: python-pptx 오브젝트 → PptxSlideSpec 데이터클래스.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

from ppt_generator.interfaces.constants import (
    IMPORT_EMU_TO_PX,
    PPTX_BULLET_MARGIN_EMU_L0,
    PPTX_BULLET_MARGIN_EMU_L1,
    PPTX_MONOSPACE_FONT_NAME,
    PPTX_SLIDE_HEIGHT_EMU,
    PPTX_SLIDE_WIDTH_EMU,
    PX_TO_EMU,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
)
from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)

if TYPE_CHECKING:
    from pptx.presentation import Presentation
    from pptx.slide import Slide


@dataclass
class _DefaultRunProps:
    """OOXML 상속 체인에서 추출한 기본 run 서식."""

    font_size_pt: int | None = None
    color: str | None = None
    bold: bool | None = None

logger = logging.getLogger(__name__)

# 모노스페이스 폰트 감지용 패턴
_MONOSPACE_FONTS = frozenset({
    "consolas", "courier", "courier new", "monaco", "menlo",
    "lucida console", "dejavu sans mono", "source code pro",
    "fira code", "fira mono", "jetbrains mono", "d2coding",
})

# PP_ALIGN → alignment 문자열 매핑
_ALIGN_REVERSE_MAP = {
    PP_ALIGN.LEFT: "left",
    PP_ALIGN.CENTER: "center",
    PP_ALIGN.RIGHT: "right",
}

# MSO_SHAPE → shape_type 문자열 매핑
_SHAPE_TYPE_REVERSE_MAP = {
    # Basic
    MSO_SHAPE.RECTANGLE: "rectangle",
    MSO_SHAPE.ROUNDED_RECTANGLE: "rounded_rectangle",
    MSO_SHAPE.OVAL: "ellipse",
    # Arrows
    MSO_SHAPE.UP_ARROW: "up_arrow",
    MSO_SHAPE.DOWN_ARROW: "down_arrow",
    MSO_SHAPE.LEFT_ARROW: "left_arrow",
    MSO_SHAPE.RIGHT_ARROW: "right_arrow",
    MSO_SHAPE.CHEVRON: "chevron",
    # Polygons
    MSO_SHAPE.ISOSCELES_TRIANGLE: "triangle",
    MSO_SHAPE.DIAMOND: "diamond",
    MSO_SHAPE.PENTAGON: "pentagon",
    MSO_SHAPE.HEXAGON: "hexagon",
    MSO_SHAPE.TRAPEZOID: "trapezoid",
    MSO_SHAPE.PARALLELOGRAM: "parallelogram",
    MSO_SHAPE.CROSS: "cross",
    # Stars
    MSO_SHAPE.STAR_4_POINT: "star_4",
    MSO_SHAPE.STAR_5_POINT: "star_5",
    MSO_SHAPE.HEART: "heart",
    # Flowchart
    MSO_SHAPE.FLOWCHART_PROCESS: "flowchart_process",
    MSO_SHAPE.FLOWCHART_DECISION: "flowchart_decision",
    MSO_SHAPE.FLOWCHART_TERMINATOR: "flowchart_terminator",
}

# 매핑되지 않은 화살표 계열 도형 (rectangle로 폴백)
_ARROW_SHAPE_TYPES = {
    MSO_SHAPE.LEFT_RIGHT_ARROW,
    MSO_SHAPE.UP_DOWN_ARROW,
    MSO_SHAPE.BENT_ARROW,
    MSO_SHAPE.NOTCHED_RIGHT_ARROW,
    MSO_SHAPE.STRIPED_RIGHT_ARROW,
    MSO_SHAPE.BLOCK_ARC,
}

# slide_type 추론용 closing 키워드
_CLOSING_KEYWORDS = re.compile(
    r"(감사|thank|q\s*&\s*a|질문|문의|contact|끝|the\s+end)", re.IGNORECASE,
)


# Office 기본 테마 색상 폴백 매핑
_SCHEME_FALLBACK: dict[str, str] = {
    "bg1": "#FFFFFF", "bg2": "#E7E6E6",
    "tx1": "#000000", "tx2": "#44546A",
    "lt1": "#FFFFFF", "lt2": "#E7E6E6",
    "dk1": "#000000", "dk2": "#44546A",
    "accent1": "#4472C4", "accent2": "#ED7D31",
    "accent3": "#A5A5A5", "accent4": "#FFC000",
    "accent5": "#5B9BD5", "accent6": "#70AD47",
    "hlink": "#0563C1", "folHlink": "#954F72",
}


def _custgeom_to_svg_path(spPr: Element) -> str | None:
    """spPr 내 a:custGeom을 SVG path 문자열로 변환.

    OOXML path 명령(moveTo, lnTo, cubicBezTo, close)을 SVG path data로 변환한다.
    viewBox 좌표계는 path 요소의 w/h를 그대로 사용한다.

    Returns:
        "w h d" 형식 문자열. w/h는 viewBox 크기, d는 SVG path data.
        custGeom이 없으면 None.
    """
    cust_geom = spPr.find(qn("a:custGeom"))
    if cust_geom is None:
        return None
    path_lst = cust_geom.find(qn("a:pathLst"))
    if path_lst is None:
        return None

    parts: list[str] = []
    vb_w = 0
    vb_h = 0

    for path_el in path_lst.findall(qn("a:path")):
        pw = int(path_el.get("w", "0"))
        ph = int(path_el.get("h", "0"))
        if pw > vb_w:
            vb_w = pw
        if ph > vb_h:
            vb_h = ph

        for cmd in path_el:
            tag = cmd.tag.split("}")[-1] if "}" in cmd.tag else cmd.tag
            if tag == "moveTo":
                pt = cmd.find(qn("a:pt"))
                if pt is not None:
                    parts.append(f"M {pt.get('x', '0')} {pt.get('y', '0')}")
            elif tag == "lnTo":
                pt = cmd.find(qn("a:pt"))
                if pt is not None:
                    parts.append(f"L {pt.get('x', '0')} {pt.get('y', '0')}")
            elif tag == "cubicBezTo":
                pts = cmd.findall(qn("a:pt"))
                if len(pts) == 3:
                    coords = " ".join(f"{p.get('x', '0')} {p.get('y', '0')}" for p in pts)
                    parts.append(f"C {coords}")
            elif tag == "close":
                parts.append("Z")

    if not parts:
        return None
    return f"{vb_w} {vb_h} {' '.join(parts)}"


def _resolve_scheme_color(
    scheme_el,
    theme_color_map: dict[str, str] | None = None,
) -> str | None:
    """schemeClr XML 요소에서 RGB 색상을 근사 추출.

    lumMod/lumOff 변환을 지원하며, 테마 색상 맵을 우선 사용하고 Office 기본 팔레트를 폴백으로 사용한다.
    """
    val = scheme_el.get("val", "")

    # 테마 색상 맵 우선 → 폴백 매핑
    base_hex: str | None = None
    if theme_color_map:
        base_hex = theme_color_map.get(val)
    if base_hex is None:
        base_hex = _SCHEME_FALLBACK.get(val)
    if base_hex is None:
        return None

    # lumMod/lumOff 변환
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


def _extract_color_from_rpr(rpr_el: Element | None, theme_color_map: dict[str, str] | None = None) -> str | None:
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
        return _resolve_scheme_color(scheme, theme_color_map)
    return None


def _extract_props_from_rpr(rpr_el: Element | None, theme_color_map: dict[str, str] | None = None) -> _DefaultRunProps:
    """a:rPr 또는 a:defRPr XML 요소에서 font_size, color, bold를 추출."""
    if rpr_el is None:
        return _DefaultRunProps()
    font_size_pt: int | None = None
    sz = rpr_el.get("sz")
    if sz is not None:
        font_size_pt = round(int(sz) / 100)
    bold: bool | None = None
    b = rpr_el.get("b")
    if b is not None:
        bold = b == "1" or b.lower() == "true"
    color = _extract_color_from_rpr(rpr_el, theme_color_map)
    return _DefaultRunProps(font_size_pt=font_size_pt, color=color, bold=bold)


def _extract_theme_color_map(presentation: Presentation) -> dict[str, str]:
    """프레젠테이션 테마에서 실제 색상 맵을 추출."""
    color_map: dict[str, str] = {}
    try:
        master = presentation.slide_masters[0]
        # theme part를 찾기 위해 rels를 순회
        theme_part = None
        for rel in master.part.rels.values():
            if "theme" in rel.reltype:
                theme_part = rel.target_part
                break
        if theme_part is None:
            return color_map

        from xml.etree.ElementTree import fromstring
        theme_xml = fromstring(theme_part.blob)

        # a:themeElements > a:clrScheme
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        clr_scheme = theme_xml.find(".//a:clrScheme", ns)
        if clr_scheme is None:
            return color_map

        for child in clr_scheme:
            # 태그에서 네임스페이스 제거하여 이름 추출
            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            # srgbClr 또는 sysClr에서 색상값 추출
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

        # clrMap 기반 별칭 매핑 (마스터의 p:clrMap이 실제 매핑을 정의)
        # 예: 다크 테마에서는 tx1→lt1, tx2→lt2 (일반: tx1→dk1, tx2→dk2)
        clr_map_el = master.element.find(qn("p:clrMap"))
        if clr_map_el is not None:
            # clrMap 속성: bg1, tx1, bg2, tx2 등이 실제 테마 색상 이름을 가리킴
            for attr_name, target_name in clr_map_el.attrib.items():
                local_attr = attr_name.split("}")[-1] if "}" in attr_name else attr_name
                if local_attr not in color_map and target_name in color_map:
                    color_map[local_attr] = color_map[target_name]
        else:
            # clrMap이 없으면 기본 별칭 매핑
            _ALIASES = {"tx1": "dk1", "tx2": "dk2", "bg1": "lt1", "bg2": "lt2"}
            for alias, target in _ALIASES.items():
                if alias not in color_map and target in color_map:
                    color_map[alias] = color_map[target]
    except Exception:
        logger.debug("테마 색상 맵 추출 실패, 폴백 사용", exc_info=True)
    return color_map


# placeholder type → master txStyle 매핑
_PH_TYPE_TO_TXSTYLE: dict[int, str] = {
    1: "titleStyle",   # TITLE
    3: "titleStyle",   # CENTER_TITLE
    15: "titleStyle",  # TITLE (some variants)
    2: "bodyStyle",    # BODY
    7: "bodyStyle",    # OBJECT
    4: "bodyStyle",    # SUBTITLE
}


def _extract_master_tx_styles(presentation: Presentation) -> dict[str, dict[int, _DefaultRunProps]]:
    """마스터의 p:txStyles에서 titleStyle/bodyStyle/otherStyle의 레벨별 기본 서식을 추출.

    Returns:
        {"titleStyle": {0: props, 1: props, ...}, "bodyStyle": {...}, "otherStyle": {...}}
    """
    result: dict[str, dict[int, _DefaultRunProps]] = {}
    try:
        master = presentation.slide_masters[0]
        txStyles = master.element.find(qn("p:txStyles"))
        if txStyles is None:
            return result

        # 테마 색상 맵은 별도로 넘기지 않고 호출 시점에 전달
        theme_map = _extract_theme_color_map(presentation)

        for style_name in ("titleStyle", "bodyStyle", "otherStyle"):
            style_el = txStyles.find(qn(f"p:{style_name}"))
            if style_el is None:
                continue
            level_map: dict[int, _DefaultRunProps] = {}
            # a:lvl1pPr ~ a:lvl9pPr
            for lvl_idx in range(9):
                lvl_pPr = style_el.find(qn(f"a:lvl{lvl_idx + 1}pPr"))
                if lvl_pPr is None:
                    continue
                def_rPr = lvl_pPr.find(qn("a:defRPr"))
                if def_rPr is not None:
                    level_map[lvl_idx] = _extract_props_from_rpr(def_rPr, theme_map)
            result[style_name] = level_map
    except Exception:
        logger.debug("마스터 txStyles 추출 실패", exc_info=True)
    return result


class SlideReader:
    """python-pptx 슬라이드에서 PptxSlideSpec을 추출하는 리더."""

    def __init__(
        self,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        presentation: Presentation | None = None,
    ) -> None:
        self._scale_x = scale_x
        self._scale_y = scale_y
        self._theme_color_map: dict[str, str] = {}
        self._master_tx_styles: dict[str, dict[int, _DefaultRunProps]] = {}
        if presentation is not None:
            self._theme_color_map = _extract_theme_color_map(presentation)
            self._master_tx_styles = _extract_master_tx_styles(presentation)
        # 현재 슬라이드의 레이아웃 placeholder defRPr 캐시 (read_slide마다 갱신)
        self._layout_def_rpr: dict[int, dict[int, _DefaultRunProps]] = {}
        # 기본 배경색 (2번째 슬라이드에서 추출, 최종 폴백으로 사용)
        self._default_bg_color: str | None = None

    def set_default_bg_color(self, color: str | None) -> None:
        """기본 배경색을 설정 (최종 폴백으로 사용)."""
        self._default_bg_color = color

    @staticmethod
    def compute_scale(presentation: Presentation) -> tuple[float, float]:
        """프레젠테이션 슬라이드 크기 → 1280×720 캔버스 스케일 팩터 계산."""
        src_width_px = presentation.slide_width * IMPORT_EMU_TO_PX
        src_height_px = presentation.slide_height * IMPORT_EMU_TO_PX
        scale_x = SLIDES_WIDTH_PX / src_width_px if src_width_px else 1.0
        scale_y = SLIDES_HEIGHT_PX / src_height_px if src_height_px else 1.0
        return scale_x, scale_y

    def _cache_layout_def_rpr(self, slide: Slide) -> None:
        """현재 슬라이드의 layout placeholder별 lstStyle > defRPr을 캐시."""
        self._layout_def_rpr = {}
        try:
            layout = slide.slide_layout
            for ph in layout.placeholders:
                ph_idx = ph.placeholder_format.idx
                ph_el = ph._element
                # sp > p:txBody > a:lstStyle > a:lvlNpPr > a:defRPr
                txBody = ph_el.find(qn("p:txBody"))
                if txBody is None:
                    continue
                lstStyle = txBody.find(qn("a:lstStyle"))
                if lstStyle is None:
                    continue
                level_map: dict[int, _DefaultRunProps] = {}
                for lvl_idx in range(9):
                    lvl_pPr = lstStyle.find(qn(f"a:lvl{lvl_idx + 1}pPr"))
                    if lvl_pPr is None:
                        continue
                    def_rPr = lvl_pPr.find(qn("a:defRPr"))
                    if def_rPr is not None:
                        level_map[lvl_idx] = _extract_props_from_rpr(def_rPr, self._theme_color_map)
                if level_map:
                    self._layout_def_rpr[ph_idx] = level_map
        except Exception:
            logger.debug("레이아웃 defRPr 캐시 실패", exc_info=True)

    def read_slide(
        self,
        slide: Slide,
        slide_index: int,
        total_slides: int,
    ) -> PptxSlideSpec:
        """단일 슬라이드 → PptxSlideSpec 변환."""
        self._cache_layout_def_rpr(slide)
        background_color = self._extract_background_color(slide)
        textboxes: list[PptxTextBox] = []
        shapes: list[PptxShape] = []
        images: list[PptxImage] = []
        warnings: list[str] = []

        for shape in slide.shapes:
            try:
                self._extract_shape(
                    shape, textboxes, shapes, images, warnings,
                )
            except Exception:
                logger.warning(
                    "슬라이드 %d: shape 추출 실패 (name=%s, type=%s)",
                    slide_index + 1,
                    getattr(shape, "name", "?"),
                    getattr(shape, "shape_type", "?"),
                    exc_info=True,
                )

        speaker_notes = self._extract_speaker_notes(slide)
        slide_type = self._infer_slide_type(
            slide_index, total_slides, textboxes, shapes,
        )

        for w in warnings:
            logger.warning("슬라이드 %d: %s", slide_index + 1, w)

        return PptxSlideSpec(
            background_color=background_color,
            textboxes=textboxes,
            shapes=shapes,
            images=images,
            speaker_notes=speaker_notes,
            slide_type=slide_type,
        )

    # ── 좌표 변환 ──

    def _emu_to_px_x(self, emu: int) -> float:
        return round(emu * IMPORT_EMU_TO_PX * self._scale_x, 1)

    def _emu_to_px_y(self, emu: int) -> float:
        return round(emu * IMPORT_EMU_TO_PX * self._scale_y, 1)

    def _emu_to_px_padding(self, emu: int | None) -> float | None:
        if emu is None:
            return None
        return round(emu / PX_TO_EMU, 1)

    # ── 배경 추출 ──

    def _extract_background_color(self, slide: Slide) -> str | None:
        # 1) 슬라이드 자체 배경
        color = self._try_extract_bg_fill(slide.background)
        if color:
            return color

        # 2) 레이아웃 배경
        try:
            color = self._try_extract_bg_fill(slide.slide_layout.background)
            if color:
                return color
        except Exception:
            pass

        # 3) 마스터 배경
        try:
            color = self._try_extract_bg_fill(slide.slide_layout.slide_master.background)
            if color:
                return color
        except Exception:
            pass

        # 4) 기본 배경색 (2번째 슬라이드에서 추출한 값) 또는 테마 bg1 폴백
        return self._default_bg_color or self._theme_color_map.get("bg1")

    def _try_extract_bg_fill(self, bg) -> str | None:
        """background 객체에서 solid fill 색상을 XML 직접 파싱으로 추출.

        python-pptx fill API는 사용하지 않음: bgRef가 있는 배경에서
        fill 속성 접근 시 bgRef XML이 bgPr/noFill로 변경되는 부작용이 있음.
        """
        try:
            bg_el = bg._element if hasattr(bg, "_element") else bg
            p_bg = bg_el.find(qn("p:bg")) if bg_el.tag != qn("p:bg") else bg_el
            if p_bg is None:
                return None
            # noFill 확인
            if p_bg.find(f".//{qn('a:noFill')}") is not None:
                return None
            # srgbClr 직접 지정 확인
            for srgb in p_bg.iter(qn("a:srgbClr")):
                val = srgb.get("val")
                if val:
                    return f"#{val}"
            # schemeClr 참조 확인
            for scheme_el in p_bg.iter(qn("a:schemeClr")):
                return _resolve_scheme_color(scheme_el, self._theme_color_map)
        except Exception:
            pass
        return None

    # ── Shape 분기 ──

    @staticmethod
    def _get_placeholder_info(shape) -> tuple[int | None, int | None]:
        """shape에서 placeholder type과 idx를 추출. placeholder가 아니면 (None, None)."""
        try:
            ph_fmt = shape.placeholder_format
        except (ValueError, AttributeError):
            return None, None
        if ph_fmt is None:
            return None, None
        ph_type = getattr(ph_fmt, "type", None)
        ph_idx = getattr(ph_fmt, "idx", None)
        # ph_type은 enum이므로 int로 변환
        return (int(ph_type) if ph_type is not None else None, ph_idx)

    def _extract_shape(
        self,
        shape,
        textboxes: list[PptxTextBox],
        shapes: list[PptxShape],
        images: list[PptxImage],
        warnings: list[str],
    ) -> None:
        shape_type = getattr(shape, "shape_type", None)

        # 그룹 도형 → 평탄화
        if shape_type == MSO_SHAPE_TYPE.GROUP:
            self._extract_group(shape, textboxes, shapes, images, warnings)
            return

        # 이미지
        if shape_type == MSO_SHAPE_TYPE.PICTURE:
            images.append(self._extract_image(shape))
            return

        # 플레이스홀더 이미지
        if shape_type == MSO_SHAPE_TYPE.PLACEHOLDER:
            if hasattr(shape, "image"):
                try:
                    _ = shape.image.blob
                    images.append(self._extract_image(shape))
                    return
                except Exception:
                    pass

        # 테이블
        if shape_type == MSO_SHAPE_TYPE.TABLE:
            self._extract_table(shape, shapes, warnings)
            return

        # 커넥터 (선/화살표) - XML 태그로 판별
        el_tag = shape._element.tag if hasattr(shape, "_element") else ""
        if el_tag == qn("p:cxnSp"):
            shapes.append(self._extract_connector(shape))
            return

        # 텍스트박스
        if shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
            tb = self._extract_textbox(shape)
            if tb.paragraphs:
                textboxes.append(tb)
            return

        # Freeform + custGeom → custom SVG shape
        if shape_type == MSO_SHAPE_TYPE.FREEFORM:
            spPr = shape._element.find(qn("p:spPr"))
            svg_path = _custgeom_to_svg_path(spPr) if spPr is not None else None
            if svg_path is not None:
                shapes.append(self._extract_freeform_shape(shape, svg_path))
                return
            # custGeom이 없으면 일반 AutoShape로 폴백

        # 일반 도형 (AutoShape 등)
        if shape_type in (
            MSO_SHAPE_TYPE.AUTO_SHAPE,
            MSO_SHAPE_TYPE.FREEFORM,
        ):
            shapes.append(self._extract_auto_shape(shape))
            return

        # 차트 → 미지원 경고
        if shape_type == MSO_SHAPE_TYPE.CHART:
            warnings.append(f"차트 요소는 미지원입니다 (name={shape.name})")
            return

        # 미디어 → 미지원 경고
        if shape_type == MSO_SHAPE_TYPE.MEDIA:
            warnings.append(f"미디어 요소는 미지원입니다 (name={shape.name})")
            return

        # 기타 (placeholder 텍스트 등): 텍스트가 있으면 텍스트박스로 추출 시도
        if hasattr(shape, "text_frame"):
            ph_type, ph_idx = self._get_placeholder_info(shape)
            paragraphs = self._extract_paragraphs(
                shape.text_frame,
                placeholder_type=ph_type,
                placeholder_idx=ph_idx,
            )
            if paragraphs:
                textboxes.append(PptxTextBox(
                    left_px=self._emu_to_px_x(shape.left),
                    top_px=self._emu_to_px_y(shape.top),
                    width_px=self._emu_to_px_x(shape.width),
                    height_px=self._emu_to_px_y(shape.height),
                    paragraphs=paragraphs,
                ))

    # ── 텍스트박스 추출 ──

    def _extract_textbox(self, shape) -> PptxTextBox:
        tf = shape.text_frame
        paragraphs = self._extract_paragraphs(tf)
        line_spacing = self._extract_line_spacing(tf)
        vertical_alignment = self._extract_vertical_alignment(tf)

        return PptxTextBox(
            left_px=self._emu_to_px_x(shape.left),
            top_px=self._emu_to_px_y(shape.top),
            width_px=self._emu_to_px_x(shape.width),
            height_px=self._emu_to_px_y(shape.height),
            paragraphs=paragraphs,
            line_spacing_pt=line_spacing,
            vertical_alignment=vertical_alignment,
            padding_left_px=self._emu_to_px_padding(tf.margin_left),
            padding_right_px=self._emu_to_px_padding(tf.margin_right),
            padding_top_px=self._emu_to_px_padding(tf.margin_top),
            padding_bottom_px=self._emu_to_px_padding(tf.margin_bottom),
        )

    # ── Freeform (custGeom) 추출 ──

    def _extract_freeform_shape(self, shape, svg_path: str) -> PptxShape:
        """Freeform custGeom 도형 → PptxShape (shape_type="custom", svg_path 포함)."""
        fill_color = self._extract_fill_color(shape)
        border_color, border_width = self._extract_line_style(shape)

        paragraphs: list[PptxParagraph] = []
        line_spacing: float | None = None
        vertical_alignment = "top"
        padding_left: float | None = None
        padding_right: float | None = None
        padding_top: float | None = None
        padding_bottom: float | None = None
        text: str | None = None
        text_color: str | None = None
        text_size_pt: int | None = None
        text_bold = False

        if shape.has_text_frame:
            tf = shape.text_frame
            paragraphs = self._extract_paragraphs(tf)
            line_spacing = self._extract_line_spacing(tf)
            vertical_alignment = self._extract_vertical_alignment(tf)
            padding_left = self._emu_to_px_padding(tf.margin_left)
            padding_right = self._emu_to_px_padding(tf.margin_right)
            padding_top = self._emu_to_px_padding(tf.margin_top)
            padding_bottom = self._emu_to_px_padding(tf.margin_bottom)

            if (
                len(paragraphs) == 1
                and len(paragraphs[0].runs) == 1
                and paragraphs[0].bullet_level < 0
            ):
                run = paragraphs[0].runs[0]
                text = run.text
                text_color = run.color
                text_size_pt = run.font_size_pt
                text_bold = run.bold

        return PptxShape(
            left_px=self._emu_to_px_x(shape.left),
            top_px=self._emu_to_px_y(shape.top),
            width_px=self._emu_to_px_x(shape.width),
            height_px=self._emu_to_px_y(shape.height),
            shape_type="custom",
            fill_color=fill_color,
            border_color=border_color,
            border_width_pt=border_width,
            paragraphs=paragraphs,
            line_spacing_pt=line_spacing,
            vertical_alignment=vertical_alignment,
            padding_left_px=padding_left,
            padding_right_px=padding_right,
            padding_top_px=padding_top,
            padding_bottom_px=padding_bottom,
            text=text,
            text_color=text_color,
            text_size_pt=text_size_pt,
            text_bold=text_bold,
            svg_path=svg_path,
        )

    # ── AutoShape 추출 ──

    def _extract_auto_shape(self, shape) -> PptxShape:
        # shape_type 문자열 결정
        auto_shape_type = getattr(shape, "auto_shape_type", None)

        # 역매핑 테이블에서 먼저 조회, 없으면 미지원 화살표 계열인지 확인 후 rectangle 폴백
        type_str = _SHAPE_TYPE_REVERSE_MAP.get(auto_shape_type)
        if type_str is None:
            type_str = "rectangle"

        fill_color = self._extract_fill_color(shape)
        border_color, border_width = self._extract_line_style(shape)
        dash_style = self._extract_dash_style_from_shape(shape)

        paragraphs: list[PptxParagraph] = []
        line_spacing: float | None = None
        vertical_alignment = "top"
        padding_left: float | None = None
        padding_right: float | None = None
        padding_top: float | None = None
        padding_bottom: float | None = None
        text: str | None = None
        text_color: str | None = None
        text_size_pt: int | None = None
        text_bold = False

        if shape.has_text_frame:
            tf = shape.text_frame
            paragraphs = self._extract_paragraphs(tf)
            line_spacing = self._extract_line_spacing(tf)
            vertical_alignment = self._extract_vertical_alignment(tf)
            padding_left = self._emu_to_px_padding(tf.margin_left)
            padding_right = self._emu_to_px_padding(tf.margin_right)
            padding_top = self._emu_to_px_padding(tf.margin_top)
            padding_bottom = self._emu_to_px_padding(tf.margin_bottom)

            # paragraphs가 단일 paragraph + 단일 run이면 간단한 text 필드로도 저장
            if (
                len(paragraphs) == 1
                and len(paragraphs[0].runs) == 1
                and paragraphs[0].bullet_level < 0
            ):
                run = paragraphs[0].runs[0]
                text = run.text
                text_color = run.color
                text_size_pt = run.font_size_pt
                text_bold = run.bold

        return PptxShape(
            left_px=self._emu_to_px_x(shape.left),
            top_px=self._emu_to_px_y(shape.top),
            width_px=self._emu_to_px_x(shape.width),
            height_px=self._emu_to_px_y(shape.height),
            shape_type=type_str,
            fill_color=fill_color,
            border_color=border_color,
            border_width_pt=border_width,
            paragraphs=paragraphs,
            line_spacing_pt=line_spacing,
            vertical_alignment=vertical_alignment,
            padding_left_px=padding_left,
            padding_right_px=padding_right,
            padding_top_px=padding_top,
            padding_bottom_px=padding_bottom,
            text=text,
            text_color=text_color,
            text_size_pt=text_size_pt,
            text_bold=text_bold,
            dash_style=dash_style,
        )

    # ── 커넥터 (선/화살표) 추출 ──

    def _extract_connector(self, shape) -> PptxShape:
        el = shape._element

        # 시작/끝 좌표 (cxnSp의 a:off, a:ext 또는 직접 좌표)
        left_emu = shape.left
        top_emu = shape.top
        width_emu = shape.width
        height_emu = shape.height

        border_color, border_width = self._extract_line_style(shape)

        # 화살표 감지: a:ln 아래 headEnd/tailEnd
        spPr = el.find(qn("p:spPr"))
        ln = spPr.find(qn("a:ln")) if spPr is not None else None
        end_arrow = False
        start_arrow = False
        dash_style: str | None = None

        if ln is not None:
            tail_end = ln.find(qn("a:tailEnd"))
            if tail_end is not None and tail_end.get("type", "none") != "none":
                end_arrow = True
            head_end = ln.find(qn("a:headEnd"))
            if head_end is not None and head_end.get("type", "none") != "none":
                start_arrow = True
            prst_dash = ln.find(qn("a:prstDash"))
            if prst_dash is not None:
                dash_val = prst_dash.get("val", "")
                if dash_val in ("dash", "dot"):
                    dash_style = dash_val

        return PptxShape(
            left_px=self._emu_to_px_x(left_emu),
            top_px=self._emu_to_px_y(top_emu),
            width_px=self._emu_to_px_x(width_emu),
            height_px=self._emu_to_px_y(height_emu),
            shape_type="line",
            border_color=border_color,
            border_width_pt=border_width,
            end_arrow=end_arrow,
            start_arrow=start_arrow,
            dash_style=dash_style,
        )

    # ── 이미지 추출 ──

    def _extract_image(self, shape) -> PptxImage:
        try:
            blob = shape.image.blob
        except Exception:
            blob = b""
        return PptxImage(
            left_px=self._emu_to_px_x(shape.left),
            top_px=self._emu_to_px_y(shape.top),
            width_px=self._emu_to_px_x(shape.width),
            height_px=self._emu_to_px_y(shape.height),
            image_bytes=blob,
        )

    # ── 그룹 도형 평탄화 ──

    def _extract_group(
        self,
        group_shape,
        textboxes: list[PptxTextBox],
        shapes: list[PptxShape],
        images: list[PptxImage],
        warnings: list[str],
    ) -> None:
        for child in group_shape.shapes:
            try:
                self._extract_shape(child, textboxes, shapes, images, warnings)
            except Exception:
                logger.warning(
                    "그룹 내 shape 추출 실패 (name=%s)",
                    getattr(child, "name", "?"),
                    exc_info=True,
                )

    # ── 테이블 → Shape 배열 변환 ──

    def _extract_table(
        self,
        shape,
        shapes: list[PptxShape],
        warnings: list[str],
    ) -> None:
        warnings.append(f"테이블을 도형 격자로 변환합니다 (name={shape.name})")
        table = shape.table
        table_left = shape.left
        table_top = shape.top

        # 행/열 크기 계산 (EMU)
        col_widths = [col.width for col in table.columns]
        row_heights = [row.height for row in table.rows]

        y_offset = 0
        for r_idx, row in enumerate(table.rows):
            x_offset = 0
            for c_idx, cell in enumerate(row.cells):
                cell_w = col_widths[c_idx]
                cell_h = row_heights[r_idx]

                paragraphs = self._extract_paragraphs(cell.text_frame)
                fill_color: str | None = None
                try:
                    fill = cell.fill
                    if fill.type is not None:
                        rgb = fill.fore_color.rgb
                        if rgb:
                            fill_color = f"#{rgb}"
                except Exception:
                    pass

                shapes.append(PptxShape(
                    left_px=self._emu_to_px_x(table_left + x_offset),
                    top_px=self._emu_to_px_y(table_top + y_offset),
                    width_px=self._emu_to_px_x(cell_w),
                    height_px=self._emu_to_px_y(cell_h),
                    shape_type="rectangle",
                    fill_color=fill_color,
                    border_color="#CCCCCC",
                    border_width_pt=0.5,
                    paragraphs=paragraphs,
                ))
                x_offset += cell_w
            y_offset += cell_h

    # ── 텍스트 추출 ──

    def _extract_paragraphs(
        self,
        text_frame,
        placeholder_type: int | None = None,
        placeholder_idx: int | None = None,
    ) -> list[PptxParagraph]:
        paragraphs: list[PptxParagraph] = []
        for para in text_frame.paragraphs:
            bullet_level = self._extract_bullet_level(para)
            runs = self._extract_runs(
                para,
                placeholder_type=placeholder_type,
                placeholder_idx=placeholder_idx,
                bullet_level=max(bullet_level, 0),
            )
            # 빈 paragraph (run 없음 + 텍스트 없음) 스킵
            if not runs:
                continue
            alignment = self._extract_alignment(para)
            paragraphs.append(PptxParagraph(
                runs=runs,
                bullet_level=bullet_level,
                alignment=alignment,
            ))
        return paragraphs

    def _resolve_inherited_props(
        self,
        paragraph,
        placeholder_type: int | None,
        placeholder_idx: int | None,
        bullet_level: int,
    ) -> _DefaultRunProps:
        """OOXML 상속 체인에서 paragraph → layout → master 순으로 기본 서식을 resolve."""
        font_size: int | None = None
        color: str | None = None
        bold: bool | None = None

        # 1) paragraph a:pPr > a:defRPr
        pPr = paragraph._p.find(qn("a:pPr"))
        if pPr is not None:
            def_rPr = pPr.find(qn("a:defRPr"))
            para_props = _extract_props_from_rpr(def_rPr, self._theme_color_map)
            if para_props.font_size_pt is not None:
                font_size = para_props.font_size_pt
            if para_props.color is not None:
                color = para_props.color
            if para_props.bold is not None:
                bold = para_props.bold

        # 2) layout placeholder lstStyle > lvlNpPr > defRPr
        if placeholder_idx is not None and placeholder_idx in self._layout_def_rpr:
            layout_levels = self._layout_def_rpr[placeholder_idx]
            layout_props = layout_levels.get(bullet_level)
            if layout_props is not None:
                if font_size is None and layout_props.font_size_pt is not None:
                    font_size = layout_props.font_size_pt
                if color is None and layout_props.color is not None:
                    color = layout_props.color
                if bold is None and layout_props.bold is not None:
                    bold = layout_props.bold

        # 3) master p:txStyles > titleStyle/bodyStyle/otherStyle > lvlNpPr > defRPr
        # placeholder가 아닌 일반 TextBox도 otherStyle 폴백 적용
        style_name = _PH_TYPE_TO_TXSTYLE.get(placeholder_type, "otherStyle") if placeholder_type is not None else "otherStyle"
        master_levels = self._master_tx_styles.get(style_name, {})
        master_props = master_levels.get(bullet_level)
        if master_props is not None:
            if font_size is None and master_props.font_size_pt is not None:
                font_size = master_props.font_size_pt
            if color is None and master_props.color is not None:
                color = master_props.color
            if bold is None and master_props.bold is not None:
                bold = master_props.bold

        return _DefaultRunProps(font_size_pt=font_size, color=color, bold=bold)

    def _extract_runs(
        self,
        paragraph,
        placeholder_type: int | None = None,
        placeholder_idx: int | None = None,
        bullet_level: int = 0,
    ) -> list[PptxTextRun]:
        # 상속 기본값을 미리 resolve
        inherited = self._resolve_inherited_props(
            paragraph, placeholder_type, placeholder_idx, bullet_level,
        )

        runs: list[PptxTextRun] = []
        for run in paragraph.runs:
            if not run.text:
                continue
            font = run.font

            # font_size: run 직접 지정 → 상속값
            font_size: int | None = None
            if font.size is not None:
                font_size = round(font.size.pt)
            if font_size is None:
                font_size = inherited.font_size_pt

            # color: run 직접 지정 → 상속값
            color: str | None = None
            try:
                if font.color and font.color.rgb:
                    color = f"#{font.color.rgb}"
            except (AttributeError, TypeError):
                pass
            # RGB 추출 실패 시 rPr XML에서 직접 색상 추출 (테마 색상 포함)
            if color is None:
                try:
                    rPr = run._r.find(qn("a:rPr"))
                    if rPr is not None:
                        color = _extract_color_from_rpr(rPr, self._theme_color_map)
                except Exception:
                    pass
            if color is None:
                color = inherited.color

            # bold: run 직접 지정 → 상속값
            run_bold = font.bold
            if run_bold is None:
                run_bold = inherited.bold if inherited.bold is not None else False
            else:
                run_bold = bool(run_bold)

            font_family: str | None = None
            if font.name and font.name.lower() in _MONOSPACE_FONTS:
                font_family = "monospace"

            runs.append(PptxTextRun(
                text=run.text,
                font_size_pt=font_size,
                color=color,
                bold=run_bold,
                italic=bool(font.italic),
                font_family=font_family,
            ))
        return runs

    @staticmethod
    def _extract_bullet_level(paragraph) -> int:
        pPr = paragraph._p.find(qn("a:pPr"))
        if pPr is None:
            return -1

        # buChar 또는 buAutoNum 존재 시 불릿
        has_bullet = (
            pPr.find(qn("a:buChar")) is not None
            or pPr.find(qn("a:buAutoNum")) is not None
        )
        # buNone이 있으면 불릿 아님
        if pPr.find(qn("a:buNone")) is not None:
            has_bullet = False

        if not has_bullet:
            # marL(indent)이 있지만 buChar 없으면 레벨 기반으로 판단
            lvl = pPr.get("lvl")
            if lvl is not None:
                lvl_int = int(lvl)
                if lvl_int > 0:
                    return lvl_int
            return -1

        # lvl 속성이 명시적으로 있으면 사용
        lvl = pPr.get("lvl")
        if lvl is not None:
            return int(lvl)

        # lvl 속성이 없으면 marL(왼쪽 마진) 값으로 레벨 추론
        # SlideBuilder.apply_bullet이 lvl을 설정하지 않고 marL만 설정하므로
        marL_str = pPr.get("marL")
        if marL_str is not None:
            marL = int(marL_str)
            # L1 마진(457200) 이상이면 레벨 1
            if marL >= PPTX_BULLET_MARGIN_EMU_L1:
                return 1
        return 0

    @staticmethod
    def _extract_alignment(paragraph) -> str | None:
        if paragraph.alignment is None:
            return None
        return _ALIGN_REVERSE_MAP.get(paragraph.alignment)

    @staticmethod
    def _extract_line_spacing(text_frame) -> float | None:
        """텍스트 프레임의 줄간격(pt)을 추출. 첫 번째 paragraph 기준."""
        for para in text_frame.paragraphs:
            spacing = para.line_spacing
            if spacing is not None:
                try:
                    return float(spacing.pt)
                except (AttributeError, TypeError):
                    # 비율 기반 줄간격은 무시
                    pass
        return None

    @staticmethod
    def _extract_vertical_alignment(text_frame) -> str:
        anchor_map = {"t": "top", "ctr": "middle", "b": "bottom"}
        try:
            bodyPr = text_frame._txBody.find(qn("a:bodyPr"))
            if bodyPr is not None:
                anchor = bodyPr.get("anchor")
                if anchor in anchor_map:
                    return anchor_map[anchor]
        except Exception:
            pass
        return "top"

    # ── 스타일 추출 헬퍼 ──

    def _resolve_color_from_xml(self, fill_element) -> str | None:
        """XML 요소에서 색상을 추출. srgbClr 우선, schemeClr 폴백."""
        if fill_element is None:
            return None
        solid = fill_element.find(qn("a:solidFill"))
        if solid is None:
            return None
        srgb = solid.find(qn("a:srgbClr"))
        if srgb is not None:
            val = srgb.get("val")
            if val:
                return f"#{val}"
        scheme = solid.find(qn("a:schemeClr"))
        if scheme is not None:
            return _resolve_scheme_color(scheme, self._theme_color_map)
        return None

    def _extract_fill_color(self, shape) -> str | None:
        # python-pptx API로 시도 (RGB 색상)
        try:
            fill = shape.fill
            if fill.type is not None:
                rgb = fill.fore_color.rgb
                if rgb:
                    return f"#{rgb}"
        except (AttributeError, TypeError):
            pass
        # API 실패 시 XML 직접 파싱 (테마 색상 등)
        try:
            spPr = shape._element.find(qn("p:spPr"))
            if spPr is not None:
                solid = spPr.find(qn("a:solidFill"))
                if solid is not None:
                    srgb = solid.find(qn("a:srgbClr"))
                    if srgb is not None:
                        val = srgb.get("val")
                        if val:
                            return f"#{val}"
                    scheme = solid.find(qn("a:schemeClr"))
                    if scheme is not None:
                        return _resolve_scheme_color(scheme, self._theme_color_map)
        except Exception:
            pass
        # p:style/a:fillRef 폴백 (테마 스타일 참조 도형)
        try:
            style_el = shape._element.find(qn("p:style"))
            if style_el is not None:
                fill_ref = style_el.find(qn("a:fillRef"))
                if fill_ref is not None and fill_ref.get("idx", "0") != "0":
                    scheme = fill_ref.find(qn("a:schemeClr"))
                    if scheme is not None:
                        return _resolve_scheme_color(scheme, self._theme_color_map)
        except Exception:
            pass
        return None

    def _extract_line_style(self, shape) -> tuple[str | None, float | None]:
        border_color: str | None = None
        border_width: float | None = None
        # python-pptx API로 시도
        try:
            line = shape.line
            if line.color and line.color.rgb:
                border_color = f"#{line.color.rgb}"
            if line.width is not None:
                border_width = round(line.width.pt, 1)
        except (AttributeError, TypeError):
            pass
        # API 실패 시 XML 직접 파싱 (테마 색상 등)
        if border_color is None:
            try:
                spPr = shape._element.find(qn("p:spPr"))
                if spPr is not None:
                    ln = spPr.find(qn("a:ln"))
                    if ln is not None:
                        solid = ln.find(qn("a:solidFill"))
                        if solid is not None:
                            srgb = solid.find(qn("a:srgbClr"))
                            if srgb is not None:
                                val = srgb.get("val")
                                if val:
                                    border_color = f"#{val}"
                            else:
                                scheme = solid.find(qn("a:schemeClr"))
                                if scheme is not None:
                                    border_color = _resolve_scheme_color(scheme, self._theme_color_map)
                        if border_width is None:
                            w_attr = ln.get("w")
                            if w_attr is not None:
                                border_width = round(int(w_attr) / 12700, 1)  # EMU → pt
            except Exception:
                pass
        # p:style/a:lnRef 폴백 (테마 스타일 참조 도형)
        if border_color is None:
            try:
                style_el = shape._element.find(qn("p:style"))
                if style_el is not None:
                    ln_ref = style_el.find(qn("a:lnRef"))
                    if ln_ref is not None and ln_ref.get("idx", "0") != "0":
                        scheme = ln_ref.find(qn("a:schemeClr"))
                        if scheme is not None:
                            border_color = _resolve_scheme_color(scheme, self._theme_color_map)
                            if border_width is None:
                                border_width = 0.5  # 테마 기본 선 굵기
            except Exception:
                pass
        return border_color, border_width

    @staticmethod
    def _extract_dash_style_from_shape(shape) -> str | None:
        """AutoShape의 border dash style을 추출."""
        try:
            spPr = shape._element.find(qn("p:spPr"))
            if spPr is not None:
                ln = spPr.find(qn("a:ln"))
                if ln is not None:
                    prst = ln.find(qn("a:prstDash"))
                    if prst is not None:
                        val = prst.get("val", "")
                        # lgDash, sysDash 등을 dash로 통합
                        if "dash" in val.lower() or "Dash" in val:
                            return "dash"
                        if "dot" in val.lower():
                            return "dot"
        except Exception:
            pass
        return None

    # ── 발표자 노트 ──

    @staticmethod
    def _extract_speaker_notes(slide: Slide) -> str:
        try:
            if slide.has_notes_slide:
                return slide.notes_slide.notes_text_frame.text or ""
        except Exception:
            pass
        return ""

    # ── slide_type 추론 ──

    @staticmethod
    def _infer_slide_type(
        slide_index: int,
        total_slides: int,
        textboxes: list[PptxTextBox],
        shapes: list[PptxShape],
    ) -> str:
        all_text = ""
        max_font = 0
        element_count = len(textboxes) + len(shapes)

        for tb in textboxes:
            for p in tb.paragraphs:
                for r in p.runs:
                    all_text += r.text
                    if r.font_size_pt and r.font_size_pt > max_font:
                        max_font = r.font_size_pt

        for s in shapes:
            if s.text:
                all_text += s.text
            for p in s.paragraphs:
                for r in p.runs:
                    all_text += r.text
                    if r.font_size_pt and r.font_size_pt > max_font:
                        max_font = r.font_size_pt

        # 마지막 슬라이드 + closing 키워드
        if slide_index == total_slides - 1 and _CLOSING_KEYWORDS.search(all_text):
            return "closing"

        # 첫 슬라이드 + 요소 적고 큰 폰트
        if slide_index == 0 and element_count <= 4 and max_font >= 28:
            return "title"

        return "content"
