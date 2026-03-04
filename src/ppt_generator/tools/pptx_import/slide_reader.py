"""python-pptx 슬라이드 객체에서 PptxSlideSpec을 추출하는 리더 모듈.

SlideBuilder의 역변환: python-pptx 오브젝트 → PptxSlideSpec 데이터클래스.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

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


def _resolve_scheme_color(scheme_el) -> str | None:
    """schemeClr XML 요소에서 RGB 색상을 근사 추출.

    lumMod/lumOff 변환을 지원하며, 알려진 테마 색상 이름을 폴백 매핑한다.
    """
    val = scheme_el.get("val", "")

    # 기본 테마 색상 폴백 매핑 (Office 기본 테마 기준)
    _SCHEME_FALLBACK = {
        "bg1": "#FFFFFF", "bg2": "#E7E6E6",
        "tx1": "#000000", "tx2": "#44546A",
        "lt1": "#FFFFFF", "lt2": "#E7E6E6",
        "dk1": "#000000", "dk2": "#44546A",
        "accent1": "#4472C4", "accent2": "#ED7D31",
        "accent3": "#A5A5A5", "accent4": "#FFC000",
        "accent5": "#5B9BD5", "accent6": "#70AD47",
        "hlink": "#0563C1", "folHlink": "#954F72",
    }

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


class SlideReader:
    """python-pptx 슬라이드에서 PptxSlideSpec을 추출하는 리더."""

    def __init__(self, scale_x: float = 1.0, scale_y: float = 1.0) -> None:
        self._scale_x = scale_x
        self._scale_y = scale_y

    @staticmethod
    def compute_scale(presentation: Presentation) -> tuple[float, float]:
        """프레젠테이션 슬라이드 크기 → 1280×720 캔버스 스케일 팩터 계산."""
        src_width_px = presentation.slide_width * IMPORT_EMU_TO_PX
        src_height_px = presentation.slide_height * IMPORT_EMU_TO_PX
        scale_x = SLIDES_WIDTH_PX / src_width_px if src_width_px else 1.0
        scale_y = SLIDES_HEIGHT_PX / src_height_px if src_height_px else 1.0
        return scale_x, scale_y

    def read_slide(
        self,
        slide: Slide,
        slide_index: int,
        total_slides: int,
    ) -> PptxSlideSpec:
        """단일 슬라이드 → PptxSlideSpec 변환."""
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

    @staticmethod
    def _extract_background_color(slide: Slide) -> str | None:
        try:
            bg = slide.background
            fill = bg.fill
            if fill.type is not None:
                from pptx.enum.dml import MSO_THEME_COLOR  # noqa: F401

                try:
                    rgb = fill.fore_color.rgb
                    if rgb:
                        return f"#{rgb}"
                except (AttributeError, TypeError):
                    pass
        except Exception:
            pass
        return None

    # ── Shape 분기 ──

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

        # 기타: 텍스트가 있으면 텍스트박스로 추출 시도
        if hasattr(shape, "text_frame"):
            paragraphs = self._extract_paragraphs(shape.text_frame)
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

    def _extract_paragraphs(self, text_frame) -> list[PptxParagraph]:
        paragraphs: list[PptxParagraph] = []
        for para in text_frame.paragraphs:
            runs = self._extract_runs(para)
            # 빈 paragraph (run 없음 + 텍스트 없음) 스킵
            if not runs:
                continue
            bullet_level = self._extract_bullet_level(para)
            alignment = self._extract_alignment(para)
            paragraphs.append(PptxParagraph(
                runs=runs,
                bullet_level=bullet_level,
                alignment=alignment,
            ))
        return paragraphs

    @staticmethod
    def _extract_runs(paragraph) -> list[PptxTextRun]:
        runs: list[PptxTextRun] = []
        for run in paragraph.runs:
            if not run.text:
                continue
            font = run.font
            font_size: int | None = None
            if font.size is not None:
                font_size = round(font.size.pt)

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
                        solid = rPr.find(qn("a:solidFill"))
                        if solid is not None:
                            srgb = solid.find(qn("a:srgbClr"))
                            if srgb is not None:
                                val = srgb.get("val")
                                if val:
                                    color = f"#{val}"
                            else:
                                scheme = solid.find(qn("a:schemeClr"))
                                if scheme is not None:
                                    color = _resolve_scheme_color(scheme)
                except Exception:
                    pass

            font_family: str | None = None
            if font.name and font.name.lower() in _MONOSPACE_FONTS:
                font_family = "monospace"

            runs.append(PptxTextRun(
                text=run.text,
                font_size_pt=font_size,
                color=color,
                bold=bool(font.bold),
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

    @staticmethod
    def _resolve_color_from_xml(fill_element) -> str | None:
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
            # schemeClr에서 직접 srgbClr 속성을 찾기 어려우므로
            # 대표적인 테마 색상을 폴백으로 매핑
            return _resolve_scheme_color(scheme)
        return None

    @staticmethod
    def _extract_fill_color(shape) -> str | None:
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
                        return _resolve_scheme_color(scheme)
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
                        return _resolve_scheme_color(scheme)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_line_style(shape) -> tuple[str | None, float | None]:
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
                                    border_color = _resolve_scheme_color(scheme)
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
                            border_color = _resolve_scheme_color(scheme)
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
