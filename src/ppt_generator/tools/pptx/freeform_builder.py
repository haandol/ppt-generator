"""Freeform SVG 도형 생성 모듈.

SVG path data를 OOXML custGeom XML로 변환하여 python-pptx 슬라이드에 추가한다.
"""

from __future__ import annotations

import math
import re

from lxml.etree import SubElement
from pptx.oxml.ns import qn

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
)
from ppt_generator.interfaces.schemas import PptxShape
from ppt_generator.tools.pptx.text_formatter import parse_color

_DASH_STYLE_MAP = {
    "dash": "dash",
    "dot": "sysDot",
}


def _svg_arc_to_cubic(
    start_x: float,
    start_y: float,
    rx: float,
    ry: float,
    rotation_deg: float,
    large_arc: bool,
    sweep: bool,
    end_x: float,
    end_y: float,
) -> list[tuple[float, float, float, float, float, float]]:
    """SVG endpoint arc를 90도 이하 cubic Bézier 구간으로 변환."""
    rx = abs(rx)
    ry = abs(ry)
    if rx == 0 or ry == 0 or (start_x == end_x and start_y == end_y):
        return []

    phi = math.radians(rotation_deg % 360)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)
    dx = (start_x - end_x) / 2
    dy = (start_y - end_y) / 2
    x1_prime = cos_phi * dx + sin_phi * dy
    y1_prime = -sin_phi * dx + cos_phi * dy

    radius_scale = (x1_prime**2) / (rx**2) + (y1_prime**2) / (ry**2)
    if radius_scale > 1:
        scale = math.sqrt(radius_scale)
        rx *= scale
        ry *= scale

    numerator = max(
        0.0,
        rx**2 * ry**2 - rx**2 * y1_prime**2 - ry**2 * x1_prime**2,
    )
    denominator = rx**2 * y1_prime**2 + ry**2 * x1_prime**2
    coefficient = 0.0 if denominator == 0 else math.sqrt(numerator / denominator)
    if large_arc == sweep:
        coefficient = -coefficient

    cx_prime = coefficient * (rx * y1_prime / ry)
    cy_prime = coefficient * (-ry * x1_prime / rx)
    center_x = cos_phi * cx_prime - sin_phi * cy_prime + (start_x + end_x) / 2
    center_y = sin_phi * cx_prime + cos_phi * cy_prime + (start_y + end_y) / 2

    start_angle = math.atan2(
        (y1_prime - cy_prime) / ry,
        (x1_prime - cx_prime) / rx,
    )
    end_vector_x = (-x1_prime - cx_prime) / rx
    end_vector_y = (-y1_prime - cy_prime) / ry
    delta_angle = math.atan2(
        ((x1_prime - cx_prime) / rx) * end_vector_y
        - ((y1_prime - cy_prime) / ry) * end_vector_x,
        ((x1_prime - cx_prime) / rx) * end_vector_x
        + ((y1_prime - cy_prime) / ry) * end_vector_y,
    )
    if not sweep and delta_angle > 0:
        delta_angle -= 2 * math.pi
    elif sweep and delta_angle < 0:
        delta_angle += 2 * math.pi

    segment_count = max(1, math.ceil(abs(delta_angle) / (math.pi / 2)))
    segment_angle = delta_angle / segment_count

    def point(angle: float) -> tuple[float, float]:
        return (
            center_x + cos_phi * rx * math.cos(angle) - sin_phi * ry * math.sin(angle),
            center_y + sin_phi * rx * math.cos(angle) + cos_phi * ry * math.sin(angle),
        )

    def derivative(angle: float) -> tuple[float, float]:
        return (
            -cos_phi * rx * math.sin(angle) - sin_phi * ry * math.cos(angle),
            -sin_phi * rx * math.sin(angle) + cos_phi * ry * math.cos(angle),
        )

    curves = []
    for index in range(segment_count):
        angle_1 = start_angle + index * segment_angle
        angle_2 = angle_1 + segment_angle
        alpha = 4 / 3 * math.tan((angle_2 - angle_1) / 4)
        p1 = point(angle_1)
        p2 = point(angle_2)
        d1 = derivative(angle_1)
        d2 = derivative(angle_2)
        curves.append(
            (
                p1[0] + alpha * d1[0],
                p1[1] + alpha * d1[1],
                p2[0] - alpha * d2[0],
                p2[1] - alpha * d2[1],
                p2[0],
                p2[1],
            )
        )
    return curves


def add_freeform_from_svg(slide, shape_spec: PptxShape) -> None:
    """SVG path data → python-pptx freeform 도형 생성."""
    svg_path = shape_spec.svg_path or ""
    parts = svg_path.split(" ", 2)
    if len(parts) < 3:
        return
    # viewBox 는 정수(px)인 경우가 대부분이나, 차트 원호(도넛/파이) 등은 소수
    # viewBox(예: "403.6 403.6")를 쓴다. float 로 파싱 후 OOXML path w/h(정수 EMU
    # 좌표계)에 맞게 반올림한다.
    try:
        vb_w = round(float(parts[0]))
        vb_h = round(float(parts[1]))
    except ValueError:
        return
    path_d = parts[2]
    if vb_w <= 0 or vb_h <= 0:
        return

    left_emu = int(shape_spec.left_px * EXPORT_PX_TO_INCHES_X * 914400)
    top_emu = int(shape_spec.top_px * EXPORT_PX_TO_INCHES_Y * 914400)
    width_emu = int(shape_spec.width_px * EXPORT_PX_TO_INCHES_X * 914400)
    height_emu = int(shape_spec.height_px * EXPORT_PX_TO_INCHES_Y * 914400)

    # SVG path를 OOXML custGeom으로 직접 구축
    sp_tree = slide.shapes._spTree
    sp = SubElement(sp_tree, qn("p:sp"))
    nvSpPr = SubElement(sp, qn("p:nvSpPr"))
    cNvPr = SubElement(nvSpPr, qn("p:cNvPr"))
    cNvPr.set("id", str(len(slide.shapes) + 100))
    cNvPr.set("name", "Freeform")
    SubElement(nvSpPr, qn("p:cNvSpPr"))
    SubElement(nvSpPr, qn("p:nvPr"))

    spPr = SubElement(sp, qn("p:spPr"))
    xfrm = SubElement(spPr, qn("a:xfrm"))
    # 회전: OOXML rot 은 60000분의 1도 단위 (import _read_rotation 의 역변환).
    if shape_spec.rotation:
        xfrm.set("rot", str(int(round(shape_spec.rotation * 60000)) % 21600000))
    off = SubElement(xfrm, qn("a:off"))
    off.set("x", str(left_emu))
    off.set("y", str(top_emu))
    ext = SubElement(xfrm, qn("a:ext"))
    ext.set("cx", str(width_emu))
    ext.set("cy", str(height_emu))

    custGeom = SubElement(spPr, qn("a:custGeom"))
    SubElement(custGeom, qn("a:avLst"))
    SubElement(custGeom, qn("a:gdLst"))
    SubElement(custGeom, qn("a:ahLst"))
    SubElement(custGeom, qn("a:cxnLst"))
    rect = SubElement(custGeom, qn("a:rect"))
    rect.set("l", "l")
    rect.set("t", "t")
    rect.set("r", "r")
    rect.set("b", "b")
    pathLst = SubElement(custGeom, qn("a:pathLst"))
    path_el = SubElement(pathLst, qn("a:path"))
    path_el.set("w", str(vb_w))
    path_el.set("h", str(vb_h))

    # SVG path data 파싱: M, L, C, A, Z 명령. 좌표는 소수 가능(정수로 반올림).
    # OOXML custGeom path 좌표는 정수만 허용하므로 각 좌표를 round 한다.
    def _icoord(tok: str) -> str:
        try:
            return str(round(float(tok)))
        except ValueError:
            return "0"

    tokens = re.findall(
        r"[MLCAZ]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?",
        path_d,
    )
    i = 0
    current_x = 0.0
    current_y = 0.0
    subpath_start_x = 0.0
    subpath_start_y = 0.0
    while i < len(tokens):
        cmd = tokens[i]
        if cmd == "M" and i + 2 < len(tokens):
            current_x = float(tokens[i + 1])
            current_y = float(tokens[i + 2])
            subpath_start_x = current_x
            subpath_start_y = current_y
            move = SubElement(path_el, qn("a:moveTo"))
            pt = SubElement(move, qn("a:pt"))
            pt.set("x", _icoord(tokens[i + 1]))
            pt.set("y", _icoord(tokens[i + 2]))
            i += 3
        elif cmd == "L" and i + 2 < len(tokens):
            current_x = float(tokens[i + 1])
            current_y = float(tokens[i + 2])
            ln = SubElement(path_el, qn("a:lnTo"))
            pt = SubElement(ln, qn("a:pt"))
            pt.set("x", _icoord(tokens[i + 1]))
            pt.set("y", _icoord(tokens[i + 2]))
            i += 3
        elif cmd == "C" and i + 6 < len(tokens):
            current_x = float(tokens[i + 5])
            current_y = float(tokens[i + 6])
            bez = SubElement(path_el, qn("a:cubicBezTo"))
            for j in range(3):
                pt = SubElement(bez, qn("a:pt"))
                pt.set("x", _icoord(tokens[i + 1 + j * 2]))
                pt.set("y", _icoord(tokens[i + 2 + j * 2]))
            i += 7
        elif cmd == "A" and i + 7 < len(tokens):
            end_x = float(tokens[i + 6])
            end_y = float(tokens[i + 7])
            curves = _svg_arc_to_cubic(
                current_x,
                current_y,
                float(tokens[i + 1]),
                float(tokens[i + 2]),
                float(tokens[i + 3]),
                bool(int(float(tokens[i + 4]))),
                bool(int(float(tokens[i + 5]))),
                end_x,
                end_y,
            )
            if curves:
                for curve in curves:
                    bez = SubElement(path_el, qn("a:cubicBezTo"))
                    for x, y in zip(curve[::2], curve[1::2], strict=True):
                        pt = SubElement(bez, qn("a:pt"))
                        pt.set("x", str(round(x)))
                        pt.set("y", str(round(y)))
            else:
                ln = SubElement(path_el, qn("a:lnTo"))
                pt = SubElement(ln, qn("a:pt"))
                pt.set("x", str(round(end_x)))
                pt.set("y", str(round(end_y)))
            current_x = end_x
            current_y = end_y
            i += 8
        elif cmd == "Z":
            SubElement(path_el, qn("a:close"))
            current_x = subpath_start_x
            current_y = subpath_start_y
            i += 1
        else:
            i += 1

    # fill
    if shape_spec.fill_color:
        rgb = parse_color(shape_spec.fill_color)
        if rgb:
            solid = SubElement(spPr, qn("a:solidFill"))
            srgb = SubElement(solid, qn("a:srgbClr"))
            srgb.set("val", str(rgb))
    else:
        SubElement(spPr, qn("a:noFill"))

    # border
    if shape_spec.border_color:
        rgb = parse_color(shape_spec.border_color)
        if rgb:
            ln = SubElement(spPr, qn("a:ln"))
            if shape_spec.border_width_pt:
                ln.set("w", str(int(shape_spec.border_width_pt * 12700)))
            solid = SubElement(ln, qn("a:solidFill"))
            srgb = SubElement(solid, qn("a:srgbClr"))
            srgb.set("val", str(rgb))
            dash = _DASH_STYLE_MAP.get((shape_spec.dash_style or "").lower())
            if dash:
                dash_el = SubElement(ln, qn("a:prstDash"))
                dash_el.set("val", dash)
            if shape_spec.start_arrow:
                head = SubElement(ln, qn("a:headEnd"))
                head.set("type", "triangle")
                head.set("w", "med")
                head.set("len", "med")
            if shape_spec.end_arrow:
                tail = SubElement(ln, qn("a:tailEnd"))
                tail.set("type", "triangle")
                tail.set("w", "med")
                tail.set("len", "med")
    else:
        ln = SubElement(spPr, qn("a:ln"))
        SubElement(ln, qn("a:noFill"))
