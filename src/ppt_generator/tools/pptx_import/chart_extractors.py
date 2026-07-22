"""차트(Chart) → 도형(Shape) 벡터 변환 모듈.

graphicFrame 안의 차트를 이미지로 래스터화하는 대신, 차트 데이터를 파싱해 SVG 기반
도형(막대는 rectangle, 파이/도넛 슬라이스는 custom svg_path)으로 재현한다 (import/0003).

주요 차트 유형을 포괄한다:
- 세로/가로 막대(bar/column) → rectangle 도형
- 꺾은선(line) → custom svg_path polyline
- 파이/도넛(pie/doughnut) → custom svg_path arc (도넛은 가운데 구멍)

지원하지 않는 유형은 경고 후 스킵한다. 색상은 데이터포인트/계열 spPr(단색·gradient 첫
stop·scheme)에서 해석하고, 없으면 테마 accent 색을 순환한다.
"""

from __future__ import annotations

import logging
import math

from pptx.oxml.ns import qn

from ppt_generator.interfaces.schemas import (
    PptxShape,
    PptxTextBox,
)
from ppt_generator.tools.pptx_import.theme_resolver import resolve_scheme_color

logger = logging.getLogger(__name__)

# 차트 데이터포인트 색을 해석 못 했을 때 순환 사용하는 테마 accent 순서
_ACCENT_CYCLE = ("accent1", "accent2", "accent3", "accent4", "accent5", "accent6")

# 플롯 영역 상하좌우 여백 (프레임 대비 비율)
_PLOT_MARGIN_RATIO = 0.12


class ChartExtractorMixin:
    """차트를 도형으로 변환하는 mixin. SlideReader/ShapeExtractor 에서 상속.

    _emu_to_px_x/_emu_to_px_y, _theme_color_map 이 필요하다.
    """

    _theme_color_map: dict[str, str]

    def _extract_chart(
        self,
        shape,
        textboxes: list[PptxTextBox],
        shapes: list[PptxShape],
        warnings: list[str],
    ) -> bool:
        """차트 shape 를 도형 배열로 변환해 shapes/textboxes 에 추가.

        Returns:
            변환에 성공하면 True, 미지원/실패면 False (호출부가 경고 후 스킵).
        """
        try:
            chart = shape.chart
        except Exception:
            logger.debug("차트 객체 접근 실패 (name=%s)", getattr(shape, "name", "?"))
            return False

        left = self._emu_to_px_x(shape.left)
        top = self._emu_to_px_y(shape.top)
        width = self._emu_to_px_x(shape.width)
        height = self._emu_to_px_y(shape.height)
        if width <= 0 or height <= 0:
            return False

        chart_type = str(getattr(chart, "chart_type", ""))

        # 원본이 차트 series 를 noFill(투명)로 둔 경우, 실제 시각 막대는 별도 도형(굵은
        # line 등)으로 그려져 있고 차트는 데이터 컨테이너일 뿐이다. 이를 색칠해 그리면
        # 진짜 막대와 중복되므로 렌더하지 않는다 (import/0003).
        if self._chart_all_series_nofill(chart):
            logger.debug(
                "차트 series 가 모두 noFill — 렌더 생략 (name=%s)",
                getattr(shape, "name", "?"),
            )
            return True

        colors = self._chart_series_colors(chart)

        try:
            if "DOUGHNUT" in chart_type or "PIE" in chart_type:
                is_doughnut = "DOUGHNUT" in chart_type
                self._render_pie(
                    chart, left, top, width, height, colors, is_doughnut, shapes
                )
                return True
            if "LINE" in chart_type:
                self._render_line(chart, left, top, width, height, colors, shapes)
                return True
            if "BAR" in chart_type or "COLUMN" in chart_type:
                horizontal = "BAR" in chart_type and "COLUMN" not in chart_type
                self._render_bars(
                    chart, left, top, width, height, colors, horizontal, shapes
                )
                return True
        except Exception:
            logger.warning(
                "차트 변환 실패 (name=%s, type=%s)",
                getattr(shape, "name", "?"),
                chart_type,
                exc_info=True,
            )
            return False

        warnings.append(
            f"지원하지 않는 차트 유형입니다 (name={shape.name}, type={chart_type})"
        )
        return False

    def _chart_all_series_nofill(self, chart) -> bool:
        """모든 series(및 dPt) 의 spPr 이 명시적 noFill 인지 판정.

        하나라도 채움/그라데이션이 있거나 spPr 자체가 없으면(=기본 채움) False.
        """
        try:
            sers = list(chart.series)
        except Exception:
            return False
        if not sers:
            return False
        for ser in sers:
            ser_el = ser._element
            dpts = ser_el.findall(qn("c:dPt"))
            spprs = [d.find(qn("c:spPr")) for d in dpts]
            ser_sppr = ser_el.find(qn("c:spPr"))
            if not any(sp is not None for sp in spprs) and ser_sppr is None:
                return False  # spPr 없음 → 기본 채움(보임)
            for sp in [*spprs, ser_sppr]:
                if sp is None:
                    continue
                # noFill 이 아니면(solidFill/gradFill 존재) 보이는 것으로 간주
                if sp.find(qn("a:noFill")) is None and (
                    sp.find(qn("a:solidFill")) is not None
                    or sp.find(qn("a:gradFill")) is not None
                ):
                    return False
        return True

    # ── 색상 해석 ──

    def _chart_series_colors(self, chart) -> list[str]:
        """계열/데이터포인트 spPr 에서 색을 해석해 리스트로 반환.

        해석 실패 시 테마 accent 색을 순환한다. 인덱스 초과 시 accent 순환으로 폴백.
        """
        colors: list[str] = []
        try:
            for ser in chart.series:
                ser_el = ser._element
                # 데이터포인트별 dPt 색 우선 (파이/도넛은 슬라이스마다 색이 다름)
                dpt_colors: dict[int, str] = {}
                for dPt in ser_el.findall(qn("c:dPt")):
                    idx_el = dPt.find(qn("c:idx"))
                    spPr = dPt.find(qn("c:spPr"))
                    if idx_el is None or spPr is None:
                        continue
                    color = self._color_from_sppr(spPr)
                    if color:
                        dpt_colors[int(idx_el.get("val", "0"))] = color
                if dpt_colors:
                    for i in range(max(dpt_colors) + 1):
                        colors.append(dpt_colors.get(i, self._accent(i)))
                else:
                    spPr = ser_el.find(qn("c:spPr"))
                    color = self._color_from_sppr(spPr) if spPr is not None else None
                    colors.append(color or self._accent(len(colors)))
        except Exception:
            logger.debug("차트 색상 해석 실패", exc_info=True)
        return colors

    def _color_from_sppr(self, spPr) -> str | None:
        """c:spPr(또는 a:spPr)에서 단색을 해석. solidFill → gradFill 첫 stop 순."""
        solid = spPr.find(qn("a:solidFill"))
        if solid is not None:
            srgb = solid.find(qn("a:srgbClr"))
            if srgb is not None and srgb.get("val"):
                return f"#{srgb.get('val')}"
            scheme = solid.find(qn("a:schemeClr"))
            if scheme is not None:
                return resolve_scheme_color(scheme, self._theme_color_map)
        grad = spPr.find(qn("a:gradFill"))
        if grad is not None:
            gs_lst = grad.find(qn("a:gsLst"))
            if gs_lst is not None:
                first_gs = gs_lst.find(qn("a:gs"))
                if first_gs is not None:
                    srgb = first_gs.find(qn("a:srgbClr"))
                    if srgb is not None and srgb.get("val"):
                        return f"#{srgb.get('val')}"
                    scheme = first_gs.find(qn("a:schemeClr"))
                    if scheme is not None:
                        return resolve_scheme_color(scheme, self._theme_color_map)
        return None

    def _accent(self, idx: int) -> str:
        name = _ACCENT_CYCLE[idx % len(_ACCENT_CYCLE)]
        return self._theme_color_map.get(name) or "#5B9BD5"

    # ── 유형별 렌더 ──

    def _series_points(self, chart) -> tuple[list, list[list[float]]]:
        """(categories, [series_values, ...]) 를 반환. 값 None 은 0 으로 대체."""
        try:
            categories = list(chart.plots[0].categories)
        except Exception:
            categories = []
        series_values: list[list[float]] = []
        for ser in chart.series:
            series_values.append(
                [float(v) if v is not None else 0.0 for v in ser.values]
            )
        return categories, series_values

    def _render_bars(
        self, chart, left, top, width, height, colors, horizontal, shapes
    ) -> None:
        _, series_values = self._series_points(chart)
        if not series_values or not series_values[0]:
            return
        values = series_values[0]  # 첫 계열 기준 (단일 계열 차트 위주)
        n = len(values)
        vmax = max(values) or 1.0

        pm_x = width * _PLOT_MARGIN_RATIO
        pm_y = height * _PLOT_MARGIN_RATIO
        plot_l = left + pm_x
        plot_t = top + pm_y
        plot_w = width - pm_x * 2
        plot_h = height - pm_y * 2

        # 데이터포인트별 색이 있으면 그것을, 없으면 첫 계열색을 공통 적용
        bar_color = colors[0] if colors else self._accent(0)

        if horizontal:
            slot = plot_h / n
            bar_th = slot * 0.6
            for i, v in enumerate(values):
                bar_len = plot_w * (v / vmax)
                y = plot_t + slot * i + (slot - bar_th) / 2
                shapes.append(
                    self._bar_rect(
                        plot_l, y, bar_len, bar_th, self._color_at(colors, i, bar_color)
                    )
                )
        else:
            slot = plot_w / n
            bar_th = slot * 0.6
            for i, v in enumerate(values):
                bar_len = plot_h * (v / vmax)
                x = plot_l + slot * i + (slot - bar_th) / 2
                y = plot_t + (plot_h - bar_len)
                shapes.append(
                    self._bar_rect(
                        x, y, bar_th, bar_len, self._color_at(colors, i, bar_color)
                    )
                )

    def _color_at(self, colors: list[str], i: int, fallback: str) -> str:
        if i < len(colors):
            return colors[i]
        return fallback

    def _bar_rect(self, x, y, w, h, color) -> PptxShape:
        return PptxShape(
            left_px=round(x, 1),
            top_px=round(y, 1),
            width_px=round(max(w, 0), 1),
            height_px=round(max(h, 0), 1),
            shape_type="rectangle",
            fill_color=color,
        )

    def _render_line(self, chart, left, top, width, height, colors, shapes) -> None:
        _, series_values = self._series_points(chart)
        if not series_values or not series_values[0]:
            return
        pm_x = width * _PLOT_MARGIN_RATIO
        pm_y = height * _PLOT_MARGIN_RATIO
        plot_w = width - pm_x * 2
        plot_h = height - pm_y * 2

        # 전체 계열의 공통 최대값으로 스케일
        vmax = max((max(vs) for vs in series_values if vs), default=1.0) or 1.0

        for s_idx, values in enumerate(series_values):
            n = len(values)
            if n < 2:
                continue
            step = plot_w / (n - 1)
            # svg_path 는 플롯 영역 크기를 viewBox 로, 점을 그 안 좌표로 그린다.
            parts: list[str] = []
            for i, v in enumerate(values):
                px = step * i
                py = plot_h * (1 - v / vmax)
                parts.append(f"{'M' if i == 0 else 'L'} {round(px, 1)} {round(py, 1)}")
            color = self._color_at(colors, s_idx, self._accent(s_idx))
            shapes.append(
                PptxShape(
                    left_px=round(left + pm_x, 1),
                    top_px=round(top + pm_y, 1),
                    width_px=round(plot_w, 1),
                    height_px=round(plot_h, 1),
                    shape_type="custom",
                    fill_color=None,
                    border_color=color,
                    border_width_pt=2.0,
                    svg_path=f"{round(plot_w, 1)} {round(plot_h, 1)} {' '.join(parts)}",
                )
            )

    def _render_pie(
        self, chart, left, top, width, height, colors, is_doughnut, shapes
    ) -> None:
        _, series_values = self._series_points(chart)
        if not series_values or not series_values[0]:
            return
        values = series_values[0]
        total = sum(values) or 1.0

        # 정사각형 플롯 영역에 원을 배치 (프레임 중앙)
        size = min(width, height)
        cx_off = (width - size) / 2
        cy_off = (height - size) / 2
        r = size / 2
        cx = r
        cy = r
        hole_r = r * self._doughnut_hole_ratio(chart) if is_doughnut else 0.0

        angle = -math.pi / 2  # 12시 방향에서 시작 (OOXML firstSliceAng=0 기준)
        for i, v in enumerate(values):
            frac = v / total
            sweep = frac * 2 * math.pi
            path_d = _arc_path(cx, cy, r, hole_r, angle, angle + sweep)
            angle += sweep
            color = self._color_at(colors, i, self._accent(i))
            shapes.append(
                PptxShape(
                    left_px=round(left + cx_off, 1),
                    top_px=round(top + cy_off, 1),
                    width_px=round(size, 1),
                    height_px=round(size, 1),
                    shape_type="custom",
                    fill_color=color,
                    border_color=None,
                    svg_path=f"{round(size, 1)} {round(size, 1)} {path_d}",
                )
            )

    def _doughnut_hole_ratio(self, chart) -> float:
        """doughnutChart 의 holeSize(%) 를 0~1 비율로. 기본 0.5."""
        try:
            hole = chart._chartSpace.find(".//" + qn("c:holeSize"))
            if hole is not None and hole.get("val"):
                return min(0.9, max(0.0, int(hole.get("val")) / 100))
        except Exception:
            logger.debug("holeSize 추출 실패", exc_info=True)
        return 0.5


def _arc_path(
    cx: float,
    cy: float,
    r: float,
    hole_r: float,
    a0: float,
    a1: float,
) -> str:
    """파이/도넛 슬라이스의 SVG path data 생성.

    hole_r=0 이면 파이(중심에서 부채꼴), >0 이면 도넛(바깥호→안쪽호).
    각도는 라디안, 화면 좌표(y 아래로 증가) 기준.
    """
    large = 1 if (a1 - a0) > math.pi else 0

    ox0, oy0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    ox1, oy1 = cx + r * math.cos(a1), cy + r * math.sin(a1)

    def n(v: float) -> float:
        return round(v, 2)

    if hole_r <= 0:
        return (
            f"M {n(cx)} {n(cy)} "
            f"L {n(ox0)} {n(oy0)} "
            f"A {n(r)} {n(r)} 0 {large} 1 {n(ox1)} {n(oy1)} Z"
        )
    ix0, iy0 = cx + hole_r * math.cos(a0), cy + hole_r * math.sin(a0)
    ix1, iy1 = cx + hole_r * math.cos(a1), cy + hole_r * math.sin(a1)
    return (
        f"M {n(ox0)} {n(oy0)} "
        f"A {n(r)} {n(r)} 0 {large} 1 {n(ox1)} {n(oy1)} "
        f"L {n(ix1)} {n(iy1)} "
        f"A {n(hole_r)} {n(hole_r)} 0 {large} 0 {n(ix0)} {n(iy0)} Z"
    )
