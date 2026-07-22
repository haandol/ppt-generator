"""도형 스타일(fill/line/dash) 추출 모듈.

SlideReader에서 사용하는 fill color, line style, dash style 추출 로직을 담당한다.
python-pptx API 우선 시도 후 실패 시 XML 직접 파싱으로 폴백한다.
"""

from __future__ import annotations

import logging

from pptx.oxml.ns import qn

from ppt_generator.tools.pptx_import.theme_resolver import resolve_scheme_color

logger = logging.getLogger(__name__)


class StyleExtractorMixin:
    """스타일 추출 기능을 제공하는 mixin 클래스.

    SlideReader에서 상속하여 사용한다.
    _theme_color_map 속성이 필요하다.
    """

    _theme_color_map: dict[str, str]

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
            return resolve_scheme_color(scheme, self._theme_color_map)
        return None

    def _color_from_grad_first_stop(self, container) -> str | None:
        """container(a:ln 또는 spPr) 안의 a:gradFill 첫 gradient stop 색을 근사.

        그라데이션을 CSS 로 완전 재현하지 않고 첫 stop 을 단색으로 근사한다
        (import/0003). custom SVG stroke 근사와 동일한 전략. srgbClr → schemeClr 순.
        """
        if container is None:
            return None
        grad = container.find(qn("a:gradFill"))
        if grad is None:
            return None
        gs_lst = grad.find(qn("a:gsLst"))
        if gs_lst is None:
            return None
        first_gs = gs_lst.find(qn("a:gs"))
        if first_gs is None:
            return None
        srgb = first_gs.find(qn("a:srgbClr"))
        if srgb is not None and srgb.get("val"):
            return f"#{srgb.get('val')}"
        scheme = first_gs.find(qn("a:schemeClr"))
        if scheme is not None:
            return resolve_scheme_color(scheme, self._theme_color_map)
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
            logger.debug("fill color API 추출 실패", exc_info=True)
        # API 실패 시 XML 직접 파싱 (테마 색상 등)
        try:
            spPr = shape._element.find(qn("p:spPr"))
            if spPr is not None:
                # noFill이 명시적으로 있으면 fill 없음 (p:style 폴백 안 함)
                if spPr.find(qn("a:noFill")) is not None:
                    return None
                solid = spPr.find(qn("a:solidFill"))
                if solid is not None:
                    srgb = solid.find(qn("a:srgbClr"))
                    if srgb is not None:
                        val = srgb.get("val")
                        if val:
                            return f"#{val}"
                    scheme = solid.find(qn("a:schemeClr"))
                    if scheme is not None:
                        return resolve_scheme_color(scheme, self._theme_color_map)
                # gradFill 채움 → 첫 stop 색으로 근사
                grad_color = self._color_from_grad_first_stop(spPr)
                if grad_color:
                    return grad_color
        except Exception:
            logger.debug("fill color XML 파싱 실패", exc_info=True)
        # p:style/a:fillRef 폴백 (테마 스타일 참조 도형)
        try:
            style_el = shape._element.find(qn("p:style"))
            if style_el is not None:
                fill_ref = style_el.find(qn("a:fillRef"))
                if fill_ref is not None and fill_ref.get("idx", "0") != "0":
                    scheme = fill_ref.find(qn("a:schemeClr"))
                    if scheme is not None:
                        return resolve_scheme_color(scheme, self._theme_color_map)
        except Exception:
            logger.debug("fillRef 폴백 추출 실패", exc_info=True)
        return None

    def _extract_line_style(self, shape) -> tuple[str | None, float | None]:
        border_color: str | None = None
        border_width: float | None = None
        # XML에서 a:ln/a:noFill을 먼저 확인 (python-pptx API가 XML을 변형하기 전에)
        # python-pptx의 shape.line.color 접근 시 <a:noFill/>·<a:gradFill/>이
        # <a:solidFill/>로 변형되므로, API 접근 전에 noFill·gradFill 을 확인해야 한다.
        try:
            spPr = shape._element.find(qn("p:spPr"))
            if spPr is not None:
                ln = spPr.find(qn("a:ln"))
                if ln is not None:
                    if ln.find(qn("a:noFill")) is not None:
                        return None, None
                    # 그라데이션 테두리 → 첫 stop 색 근사 (API 접근 전에 추출).
                    # API 가 gradFill 을 solidFill 로 덮어쓰기 전에 잡아야 한다 (import/0003).
                    grad_color = self._color_from_grad_first_stop(ln)
                    if grad_color:
                        border_color = grad_color
                        w_attr = ln.get("w")
                        if w_attr is not None:
                            border_width = round(int(w_attr) / 12700, 1)
        except Exception:
            logger.debug("line noFill/gradFill 확인 실패", exc_info=True)
        # python-pptx API로 시도 (그라데이션에서 이미 색을 잡았으면 건너뜀 —
        # API 접근이 gradFill 을 solidFill 로 변형하므로 재접근하지 않는다)
        if border_color is None:
            try:
                line = shape.line
                if line.color and line.color.rgb:
                    border_color = f"#{line.color.rgb}"
                if line.width is not None:
                    border_width = round(line.width.pt, 1)
            except (AttributeError, TypeError):
                logger.debug("line style API 추출 실패", exc_info=True)
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
                                    border_color = resolve_scheme_color(
                                        scheme, self._theme_color_map
                                    )
                        # 그라데이션 테두리 → 첫 stop 색으로 근사 (import/0003)
                        if border_color is None:
                            border_color = self._color_from_grad_first_stop(ln)
                        if border_width is None:
                            w_attr = ln.get("w")
                            if w_attr is not None:
                                border_width = round(int(w_attr) / 12700, 1)  # EMU → pt
            except Exception:
                logger.debug("line style XML 파싱 실패", exc_info=True)
        # p:style/a:lnRef 폴백 (테마 스타일 참조 도형)
        if border_color is None:
            try:
                style_el = shape._element.find(qn("p:style"))
                if style_el is not None:
                    ln_ref = style_el.find(qn("a:lnRef"))
                    if ln_ref is not None and ln_ref.get("idx", "0") != "0":
                        scheme = ln_ref.find(qn("a:schemeClr"))
                        if scheme is not None:
                            border_color = resolve_scheme_color(
                                scheme, self._theme_color_map
                            )
                            if border_width is None:
                                border_width = 0.5  # 테마 기본 선 굵기
            except Exception:
                logger.debug("lnRef 폴백 추출 실패", exc_info=True)
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
                        if "dash" in val.lower() or "Dash" in val:
                            return "dash"
                        if "dot" in val.lower():
                            return "dot"
        except Exception:
            logger.debug("dash style 추출 실패", exc_info=True)
        return None
