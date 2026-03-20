"""python-pptx 슬라이드 객체에서 PptxSlideSpec을 추출하는 리더 모듈.

SlideBuilder의 역변환: python-pptx 오브젝트 → PptxSlideSpec 데이터클래스.

상세 로직은 하위 모듈로 분리:
- theme_resolver: 테마/색상 해석
- ooxml_utils: OOXML 상수 매핑, custGeom → SVG 변환
- text_extractor: 텍스트/런/불릿 추출
- style_extractor: fill/line/dash 스타일 추출
- shape_extractors: 개별 도형 유형별 추출
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from pptx.oxml.ns import qn

from ppt_generator.interfaces.constants import (
    IMPORT_EMU_TO_PX,
    PX_TO_EMU,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
)
from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.tools.pptx_import.ooxml_utils import CLOSING_KEYWORDS
from ppt_generator.tools.pptx_import.shape_extractors import ShapeExtractorMixin
from ppt_generator.tools.pptx_import.style_extractor import StyleExtractorMixin
from ppt_generator.tools.pptx_import.text_extractor import TextExtractorMixin
from ppt_generator.tools.pptx_import.theme_resolver import (
    DefaultRunProps,
    extract_master_tx_styles,
    extract_props_from_rpr,
    extract_theme_color_map,
    resolve_scheme_color,
)

# 하위 호환: 외부에서 기존 private 이름으로 import하는 코드 지원
_DefaultRunProps = DefaultRunProps
_extract_theme_color_map = extract_theme_color_map

if TYPE_CHECKING:
    from pptx.presentation import Presentation
    from pptx.slide import Slide

logger = logging.getLogger(__name__)


class SlideReader(ShapeExtractorMixin, TextExtractorMixin, StyleExtractorMixin):
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
        self._master_tx_styles: dict[str, dict[int, DefaultRunProps]] = {}
        if presentation is not None:
            self._theme_color_map = extract_theme_color_map(presentation)
            self._master_tx_styles = extract_master_tx_styles(presentation)
        self._layout_def_rpr: dict[int, dict[int, DefaultRunProps]] = {}
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

    # ── 좌표 변환 ──

    def _emu_to_px_x(self, emu: int) -> float:
        return round(emu * IMPORT_EMU_TO_PX * self._scale_x, 1)

    def _emu_to_px_y(self, emu: int) -> float:
        return round(emu * IMPORT_EMU_TO_PX * self._scale_y, 1)

    def _emu_to_px_padding(self, emu: int | None) -> float | None:
        if emu is None:
            return None
        return round(emu / PX_TO_EMU, 1)

    # ── 슬라이드 읽기 ──

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

        z_counter = 0
        for shape in slide.shapes:
            prev_counts = (len(textboxes), len(shapes), len(images))
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
            # 새로 추가된 요소에 z_index 할당
            for lst, prev_len in (
                (textboxes, prev_counts[0]),
                (shapes, prev_counts[1]),
                (images, prev_counts[2]),
            ):
                for idx in range(prev_len, len(lst)):
                    lst[idx] = replace(lst[idx], z_index=z_counter)
                    z_counter += 1

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

    # ── 레이아웃 캐시 ──

    def _cache_layout_def_rpr(self, slide: Slide) -> None:
        """현재 슬라이드의 layout placeholder별 lstStyle > defRPr을 캐시."""
        self._layout_def_rpr = {}
        try:
            layout = slide.slide_layout
            for ph in layout.placeholders:
                ph_idx = ph.placeholder_format.idx
                ph_el = ph._element
                txBody = ph_el.find(qn("p:txBody"))
                if txBody is None:
                    continue
                lstStyle = txBody.find(qn("a:lstStyle"))
                if lstStyle is None:
                    continue
                level_map: dict[int, DefaultRunProps] = {}
                for lvl_idx in range(9):
                    lvl_pPr = lstStyle.find(qn(f"a:lvl{lvl_idx + 1}pPr"))
                    if lvl_pPr is None:
                        continue
                    def_rPr = lvl_pPr.find(qn("a:defRPr"))
                    if def_rPr is not None:
                        level_map[lvl_idx] = extract_props_from_rpr(def_rPr, self._theme_color_map)
                if level_map:
                    self._layout_def_rpr[ph_idx] = level_map
        except Exception:
            logger.debug("레이아웃 defRPr 캐시 실패", exc_info=True)

    # ── 배경 추출 ──

    def _extract_background_color(self, slide: Slide) -> str | None:
        color = self._try_extract_bg_fill(slide.background)
        if color:
            return color

        try:
            color = self._try_extract_bg_fill(slide.slide_layout.background)
            if color:
                return color
        except Exception:
            pass

        try:
            color = self._try_extract_bg_fill(slide.slide_layout.slide_master.background)
            if color:
                return color
        except Exception:
            pass

        return self._default_bg_color or self._theme_color_map.get("bg1")

    def _try_extract_bg_fill(self, bg) -> str | None:
        """background 객체에서 solid fill 색상을 XML 직접 파싱으로 추출."""
        try:
            bg_el = bg._element if hasattr(bg, "_element") else bg
            p_bg = bg_el.find(qn("p:bg")) if bg_el.tag != qn("p:bg") else bg_el
            if p_bg is None:
                return None
            if p_bg.find(f".//{qn('a:noFill')}") is not None:
                return None
            for srgb in p_bg.iter(qn("a:srgbClr")):
                val = srgb.get("val")
                if val:
                    return f"#{val}"
            for scheme_el in p_bg.iter(qn("a:schemeClr")):
                return resolve_scheme_color(scheme_el, self._theme_color_map)
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

        if slide_index == total_slides - 1 and CLOSING_KEYWORDS.search(all_text):
            return "closing"

        if slide_index == 0 and element_count <= 4 and max_font >= 28:
            return "title"

        return "content"
