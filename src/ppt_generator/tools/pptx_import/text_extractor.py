"""텍스트/런/불릿 추출 모듈.

SlideReader에서 사용하는 텍스트 관련 추출 로직을 담당한다.
paragraph, run, 불릿 레벨, 정렬, 줄간격, 수직 정렬 등의 추출 기능을 제공한다.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pptx.oxml.ns import qn

from ppt_generator.interfaces.constants import (
    PPTX_BULLET_MARGIN_EMU_L1,
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxTextRun,
)
from ppt_generator.tools.pptx_import.ooxml_utils import (
    ALIGN_REVERSE_MAP,
    MONOSPACE_FONTS,
)
from ppt_generator.tools.pptx_import.theme_resolver import (
    DefaultRunProps,
    PH_TYPE_TO_TXSTYLE,
    extract_color_from_rpr,
    extract_props_from_rpr,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TextExtractorMixin:
    """텍스트 추출 기능을 제공하는 mixin 클래스.

    SlideReader에서 상속하여 사용한다.
    _theme_color_map, _master_tx_styles, _layout_def_rpr 속성이 필요하다.
    """

    _theme_color_map: dict[str, str]
    _master_tx_styles: dict[str, dict[int, DefaultRunProps]]
    _layout_def_rpr: dict[int, dict[int, DefaultRunProps]]

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
    ) -> DefaultRunProps:
        """OOXML 상속 체인에서 paragraph → layout → master 순으로 기본 서식을 resolve."""
        font_size: int | None = None
        color: str | None = None
        bold: bool | None = None

        # 1) paragraph a:pPr > a:defRPr
        pPr = paragraph._p.find(qn("a:pPr"))
        if pPr is not None:
            def_rPr = pPr.find(qn("a:defRPr"))
            para_props = extract_props_from_rpr(def_rPr, self._theme_color_map)
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
        style_name = PH_TYPE_TO_TXSTYLE.get(placeholder_type, "otherStyle") if placeholder_type is not None else "otherStyle"
        master_levels = self._master_tx_styles.get(style_name, {})
        master_props = master_levels.get(bullet_level)
        if master_props is not None:
            if font_size is None and master_props.font_size_pt is not None:
                font_size = master_props.font_size_pt
            if color is None and master_props.color is not None:
                color = master_props.color
            if bold is None and master_props.bold is not None:
                bold = master_props.bold

        return DefaultRunProps(font_size_pt=font_size, color=color, bold=bold)

    def _extract_runs(
        self,
        paragraph,
        placeholder_type: int | None = None,
        placeholder_idx: int | None = None,
        bullet_level: int = 0,
    ) -> list[PptxTextRun]:
        inherited = self._resolve_inherited_props(
            paragraph, placeholder_type, placeholder_idx, bullet_level,
        )

        runs: list[PptxTextRun] = []
        for run in paragraph.runs:
            if not run.text:
                continue
            font = run.font

            font_size: int | None = None
            if font.size is not None:
                font_size = round(font.size.pt)
            if font_size is None:
                font_size = inherited.font_size_pt

            color: str | None = None
            try:
                if font.color and font.color.rgb:
                    color = f"#{font.color.rgb}"
            except (AttributeError, TypeError):
                pass
            if color is None:
                try:
                    rPr = run._r.find(qn("a:rPr"))
                    if rPr is not None:
                        color = extract_color_from_rpr(rPr, self._theme_color_map)
                except Exception:
                    pass
            if color is None:
                color = inherited.color

            run_bold = font.bold
            if run_bold is None:
                run_bold = inherited.bold if inherited.bold is not None else False
            else:
                run_bold = bool(run_bold)

            font_family: str | None = None
            if font.name and font.name.lower() in MONOSPACE_FONTS:
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

        has_bullet = (
            pPr.find(qn("a:buChar")) is not None
            or pPr.find(qn("a:buAutoNum")) is not None
        )
        if pPr.find(qn("a:buNone")) is not None:
            has_bullet = False

        if not has_bullet:
            lvl = pPr.get("lvl")
            if lvl is not None:
                lvl_int = int(lvl)
                if lvl_int > 0:
                    return lvl_int
            return -1

        lvl = pPr.get("lvl")
        if lvl is not None:
            return int(lvl)

        marL_str = pPr.get("marL")
        if marL_str is not None:
            marL = int(marL_str)
            if marL >= PPTX_BULLET_MARGIN_EMU_L1:
                return 1
        return 0

    @staticmethod
    def _extract_alignment(paragraph) -> str | None:
        if paragraph.alignment is None:
            return None
        return ALIGN_REVERSE_MAP.get(paragraph.alignment)

    @staticmethod
    def _extract_line_spacing(text_frame) -> float | None:
        """텍스트 프레임의 줄간격(pt)을 추출. 첫 번째 paragraph 기준."""
        for para in text_frame.paragraphs:
            spacing = para.line_spacing
            if spacing is not None:
                try:
                    return float(spacing.pt)
                except (AttributeError, TypeError):
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
