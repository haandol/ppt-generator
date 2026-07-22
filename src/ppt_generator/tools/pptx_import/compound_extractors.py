"""복합 도형(Group, Table) 추출 모듈.

Group 도형의 자식 평탄화 및 Table → Shape 격자 변환 로직을 담당한다.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from pptx.oxml.ns import qn

from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxShape,
    PptxTextBox,
)

logger = logging.getLogger(__name__)


class CompoundExtractorMixin:
    """Group/Table 추출 기능을 제공하는 mixin 클래스.

    ShapeExtractorMixin에서 상속하여 사용한다.
    """

    # 타입 힌트 (실제 구현은 SlideReader/다른 mixin에서 제공)
    _emu_to_px_x: any
    _emu_to_px_y: any
    _extract_paragraphs: any
    _extract_shape: any

    # ── 그룹 도형 평탄화 ──

    def _extract_group(
        self,
        group_shape,
        textboxes: list[PptxTextBox],
        shapes: list[PptxShape],
        images: list[PptxImage],
        warnings: list[str],
    ) -> None:
        grp_xfrm = group_shape._element.find(qn("p:grpSpPr") + "/" + qn("a:xfrm"))
        scale_x = scale_y = 1.0
        offset_x_emu = offset_y_emu = 0
        ch_offset_x_emu = ch_offset_y_emu = 0
        if grp_xfrm is not None:
            off = grp_xfrm.find(qn("a:off"))
            ext = grp_xfrm.find(qn("a:ext"))
            ch_off = grp_xfrm.find(qn("a:chOff"))
            ch_ext = grp_xfrm.find(qn("a:chExt"))
            if (
                off is not None
                and ext is not None
                and ch_off is not None
                and ch_ext is not None
            ):
                offset_x_emu = int(off.get("x", "0"))
                offset_y_emu = int(off.get("y", "0"))
                ext_cx = int(ext.get("cx", "1"))
                ext_cy = int(ext.get("cy", "1"))
                ch_offset_x_emu = int(ch_off.get("x", "0"))
                ch_offset_y_emu = int(ch_off.get("y", "0"))
                ch_ext_cx = int(ch_ext.get("cx", "1"))
                ch_ext_cy = int(ch_ext.get("cy", "1"))
                if ch_ext_cx > 0:
                    scale_x = ext_cx / ch_ext_cx
                if ch_ext_cy > 0:
                    scale_y = ext_cy / ch_ext_cy

        tmp_tb: list[PptxTextBox] = []
        tmp_sh: list[PptxShape] = []
        tmp_img: list[PptxImage] = []
        # 자식을 문서(그리기) 순서대로 추출하며, 각 자식이 만든 요소에 그룹 내 상대 순서
        # (draw_order)를 부여한다. slide_reader 가 z_index 를 리스트 종류별로 일괄 부여하면
        # (textbox 먼저 → shape 나중) 그룹 내 "박스(도형) 뒤 + 텍스트 앞" 그리기 순서가
        # 뒤집혀 흰 채움 박스가 텍스트를 덮는다 (import/0003). draw_order 를 남겨 두면
        # slide_reader 가 이를 존중해 올바른 z 를 매긴다.
        order = 0
        for child in group_shape.shapes:
            before = (len(tmp_tb), len(tmp_sh), len(tmp_img))
            try:
                self._extract_shape(child, tmp_tb, tmp_sh, tmp_img, warnings)
            except Exception:
                logger.warning(
                    "그룹 내 shape 추출 실패 (name=%s)",
                    getattr(child, "name", "?"),
                    exc_info=True,
                )
            for lst, prev in (
                (tmp_tb, before[0]),
                (tmp_sh, before[1]),
                (tmp_img, before[2]),
            ):
                for idx in range(prev, len(lst)):
                    lst[idx] = replace(lst[idx], z_index=order)
                    order += 1

        if grp_xfrm is not None:
            ch_off_x_px = self._emu_to_px_x(ch_offset_x_emu)
            ch_off_y_px = self._emu_to_px_y(ch_offset_y_emu)
            off_x_px = self._emu_to_px_x(offset_x_emu)
            off_y_px = self._emu_to_px_y(offset_y_emu)

            def _tx(
                left: float, top: float, w: float, h: float
            ) -> tuple[float, float, float, float]:
                return (
                    round((left - ch_off_x_px) * scale_x + off_x_px, 1),
                    round((top - ch_off_y_px) * scale_y + off_y_px, 1),
                    round(w * scale_x, 1),
                    round(h * scale_y, 1),
                )

            tmp_tb = [
                replace(tb, left_px=c[0], top_px=c[1], width_px=c[2], height_px=c[3])
                for tb in tmp_tb
                for c in [_tx(tb.left_px, tb.top_px, tb.width_px, tb.height_px)]
            ]
            tmp_sh = [
                replace(sh, left_px=c[0], top_px=c[1], width_px=c[2], height_px=c[3])
                for sh in tmp_sh
                for c in [_tx(sh.left_px, sh.top_px, sh.width_px, sh.height_px)]
            ]
            tmp_img = [
                replace(img, left_px=c[0], top_px=c[1], width_px=c[2], height_px=c[3])
                for img in tmp_img
                for c in [_tx(img.left_px, img.top_px, img.width_px, img.height_px)]
            ]

        textboxes.extend(tmp_tb)
        shapes.extend(tmp_sh)
        images.extend(tmp_img)

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
                    logger.debug(
                        "테이블 셀 fill 색상 추출 실패 (r=%d, c=%d)",
                        r_idx,
                        c_idx,
                        exc_info=True,
                    )

                shapes.append(
                    PptxShape(
                        left_px=self._emu_to_px_x(table_left + x_offset),
                        top_px=self._emu_to_px_y(table_top + y_offset),
                        width_px=self._emu_to_px_x(cell_w),
                        height_px=self._emu_to_px_y(cell_h),
                        shape_type="rectangle",
                        fill_color=fill_color,
                        border_color="#CCCCCC",
                        border_width_pt=0.5,
                        paragraphs=paragraphs,
                    )
                )
                x_offset += cell_w
            y_offset += cell_h
