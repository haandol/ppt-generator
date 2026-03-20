"""개별 도형 유형별 추출 모듈.

SlideReader에서 사용하는 각 shape 유형(AutoShape, Freeform, Connector,
Image, TextBox)의 추출 로직을 담당한다.
Group/Table은 compound_extractors 모듈에서 처리한다.
"""

from __future__ import annotations

import logging

from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxParagraph,
    PptxShape,
    PptxTextBox,
)
from ppt_generator.tools.pptx_import.compound_extractors import CompoundExtractorMixin
from ppt_generator.tools.pptx_import.ooxml_utils import (
    SHAPE_TYPE_REVERSE_MAP,
    custgeom_to_svg_path,
)

logger = logging.getLogger(__name__)


class ShapeExtractorMixin(CompoundExtractorMixin):
    """도형별 추출 기능을 제공하는 mixin 클래스.

    SlideReader에서 상속하여 사용한다.
    TextExtractorMixin, StyleExtractorMixin, 좌표 변환 메서드가 필요하다.
    """

    # 타입 힌트 (실제 구현은 SlideReader/다른 mixin에서 제공)
    # _emu_to_px_x, _emu_to_px_y, _extract_paragraphs, _extract_shape는
    # 부모 CompoundExtractorMixin에서 선언
    _emu_to_px_padding: any
    _extract_line_spacing: any
    _extract_vertical_alignment: any
    _extract_fill_color: any
    _extract_line_style: any
    _extract_dash_style_from_shape: any

    # ── Shape 분기 ──

    @staticmethod
    def _get_placeholder_info(shape) -> tuple[int | None, int | None]:
        """shape에서 placeholder type과 idx를 추출."""
        try:
            ph_fmt = shape.placeholder_format
        except (ValueError, AttributeError):
            return None, None
        if ph_fmt is None:
            return None, None
        ph_type = getattr(ph_fmt, "type", None)
        ph_idx = getattr(ph_fmt, "idx", None)
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

        if shape_type == MSO_SHAPE_TYPE.GROUP:
            self._extract_group(shape, textboxes, shapes, images, warnings)
            return

        if shape_type == MSO_SHAPE_TYPE.PICTURE:
            images.append(self._extract_image(shape))
            return

        if shape_type == MSO_SHAPE_TYPE.PLACEHOLDER:
            if hasattr(shape, "image"):
                try:
                    _ = shape.image.blob
                    images.append(self._extract_image(shape))
                    return
                except Exception:
                    pass

        if shape_type == MSO_SHAPE_TYPE.TABLE:
            self._extract_table(shape, shapes, warnings)
            return

        el_tag = shape._element.tag if hasattr(shape, "_element") else ""
        if el_tag == qn("p:cxnSp"):
            shapes.append(self._extract_connector(shape))
            return

        if shape_type == MSO_SHAPE_TYPE.TEXT_BOX:
            tb = self._extract_textbox(shape)
            if tb.paragraphs:
                textboxes.append(tb)
            return

        if shape_type == MSO_SHAPE_TYPE.FREEFORM:
            spPr = shape._element.find(qn("p:spPr"))
            svg_path = custgeom_to_svg_path(spPr) if spPr is not None else None
            if svg_path is not None:
                shapes.append(self._extract_freeform_shape(shape, svg_path))
                return

        if shape_type in (
            MSO_SHAPE_TYPE.AUTO_SHAPE,
            MSO_SHAPE_TYPE.FREEFORM,
        ):
            shapes.append(self._extract_auto_shape(shape))
            return

        if shape_type == MSO_SHAPE_TYPE.CHART:
            warnings.append(f"차트 요소는 미지원입니다 (name={shape.name})")
            return

        if shape_type == MSO_SHAPE_TYPE.MEDIA:
            warnings.append(f"미디어 요소는 미지원입니다 (name={shape.name})")
            return

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

    # ── Shape 텍스트 공통 추출 헬퍼 ──

    def _extract_shape_text_props(self, shape) -> dict:
        """AutoShape/Freeform 공통: text_frame에서 텍스트 관련 속성을 추출."""
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

        return {
            "paragraphs": paragraphs,
            "line_spacing_pt": line_spacing,
            "vertical_alignment": vertical_alignment,
            "padding_left_px": padding_left,
            "padding_right_px": padding_right,
            "padding_top_px": padding_top,
            "padding_bottom_px": padding_bottom,
            "text": text,
            "text_color": text_color,
            "text_size_pt": text_size_pt,
            "text_bold": text_bold,
        }

    # ── Freeform (custGeom) 추출 ──

    def _extract_freeform_shape(self, shape, svg_path: str) -> PptxShape:
        """Freeform custGeom 도형 → PptxShape (shape_type="custom", svg_path 포함)."""
        fill_color = self._extract_fill_color(shape)
        border_color, border_width = self._extract_line_style(shape)
        text_props = self._extract_shape_text_props(shape)

        return PptxShape(
            left_px=self._emu_to_px_x(shape.left),
            top_px=self._emu_to_px_y(shape.top),
            width_px=self._emu_to_px_x(shape.width),
            height_px=self._emu_to_px_y(shape.height),
            shape_type="custom",
            fill_color=fill_color,
            border_color=border_color,
            border_width_pt=border_width,
            svg_path=svg_path,
            **text_props,
        )

    # ── AutoShape 추출 ──

    def _extract_auto_shape(self, shape) -> PptxShape:
        auto_shape_type = getattr(shape, "auto_shape_type", None)
        type_str = SHAPE_TYPE_REVERSE_MAP.get(auto_shape_type)
        if type_str is None:
            type_str = "rectangle"

        fill_color = self._extract_fill_color(shape)
        border_color, border_width = self._extract_line_style(shape)
        dash_style = self._extract_dash_style_from_shape(shape)
        text_props = self._extract_shape_text_props(shape)

        return PptxShape(
            left_px=self._emu_to_px_x(shape.left),
            top_px=self._emu_to_px_y(shape.top),
            width_px=self._emu_to_px_x(shape.width),
            height_px=self._emu_to_px_y(shape.height),
            shape_type=type_str,
            fill_color=fill_color,
            border_color=border_color,
            border_width_pt=border_width,
            dash_style=dash_style,
            **text_props,
        )

    # ── 커넥터 (선/화살표) 추출 ──

    def _extract_connector(self, shape) -> PptxShape:
        el = shape._element

        left_emu = shape.left
        top_emu = shape.top
        width_emu = shape.width
        height_emu = shape.height

        border_color, border_width = self._extract_line_style(shape)

        spPr = el.find(qn("p:spPr"))

        xfrm = spPr.find(qn("a:xfrm")) if spPr is not None else None
        flip_h = xfrm is not None and xfrm.get("flipH") == "1"
        flip_v = xfrm is not None and xfrm.get("flipV") == "1"

        ln = spPr.find(qn("a:ln")) if spPr is not None else None
        tail_arrow = False
        head_arrow = False
        dash_style: str | None = None

        if ln is not None:
            tail_end = ln.find(qn("a:tailEnd"))
            if tail_end is not None and tail_end.get("type", "none") != "none":
                tail_arrow = True
            head_end = ln.find(qn("a:headEnd"))
            if head_end is not None and head_end.get("type", "none") != "none":
                head_arrow = True
            prst_dash = ln.find(qn("a:prstDash"))
            if prst_dash is not None:
                dash_val = prst_dash.get("val", "")
                if dash_val in ("dash", "dot"):
                    dash_style = dash_val

        width_px = self._emu_to_px_x(width_emu)
        height_px = self._emu_to_px_y(height_emu)

        # PPTX 커넥터의 실제 시작/끝 좌표 계산:
        # 기본: start=(left,top), end=(left+w,top+h)
        # flipH=1 → x좌표 반전: start.x=left+w, end.x=left
        # flipV=1 → y좌표 반전: start.y=top+h, end.y=top
        # headEnd 마커는 start에, tailEnd 마커는 end에 위치
        #
        # 디자인 스펙 모델은 항상 (left,top)→(left+w,top±h) 방향으로 그리므로
        # flip이 start/end를 뒤바꾸면 화살표도 swap 해야 함
        _SNAP = 12  # 수직/수평 판별 임계값 (px)
        is_horizontal = height_px == 0 or (width_px > 0 and abs(height_px) <= _SNAP)
        is_vertical = width_px == 0 or (abs(height_px) > 0 and width_px <= _SNAP)

        if is_vertical and not is_horizontal:
            # 수직선: flipH는 시각적 효과 없음, flipV만 방향 반전
            if flip_v:
                tail_arrow, head_arrow = head_arrow, tail_arrow
        elif is_horizontal and not is_vertical:
            # 수평선: flipV는 시각적 효과 없음, flipH만 방향 반전
            if flip_h:
                tail_arrow, head_arrow = head_arrow, tail_arrow
        else:
            # 대각선: flipH XOR flipV → 선 방향 반전 (↘ ↔ ↗)
            if flip_v != flip_h:
                height_px = -height_px
            # flipH가 활성이면 화살표 swap (↘→↙ 또는 ↗→↖)
            if flip_h:
                tail_arrow, head_arrow = head_arrow, tail_arrow

        return PptxShape(
            left_px=self._emu_to_px_x(left_emu),
            top_px=self._emu_to_px_y(top_emu),
            width_px=width_px,
            height_px=height_px,
            shape_type="line",
            border_color=border_color,
            border_width_pt=border_width,
            end_arrow=tail_arrow,
            start_arrow=head_arrow,
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
