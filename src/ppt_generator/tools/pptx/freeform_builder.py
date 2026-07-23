"""Freeform SVG 도형 생성 모듈.

SVG path data를 OOXML custGeom XML로 변환하여 python-pptx 슬라이드에 추가한다.
"""

from __future__ import annotations

import re

from lxml.etree import SubElement
from pptx.oxml.ns import qn

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
)
from ppt_generator.interfaces.schemas import PptxShape
from ppt_generator.tools.pptx.text_formatter import parse_color


def add_freeform_from_svg(slide, shape_spec: PptxShape) -> None:
    """SVG path data → python-pptx freeform 도형 생성."""
    svg_path = shape_spec.svg_path or ""
    parts = svg_path.split(" ", 2)
    if len(parts) < 3:
        return
    vb_w, vb_h, path_d = int(parts[0]), int(parts[1]), parts[2]
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

    # SVG path data 파싱: M, L, C, Z 명령
    tokens = re.findall(r"[MLCZ]|[-]?\d+", path_d)
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        if cmd == "M" and i + 2 < len(tokens):
            move = SubElement(path_el, qn("a:moveTo"))
            pt = SubElement(move, qn("a:pt"))
            pt.set("x", tokens[i + 1])
            pt.set("y", tokens[i + 2])
            i += 3
        elif cmd == "L" and i + 2 < len(tokens):
            ln = SubElement(path_el, qn("a:lnTo"))
            pt = SubElement(ln, qn("a:pt"))
            pt.set("x", tokens[i + 1])
            pt.set("y", tokens[i + 2])
            i += 3
        elif cmd == "C" and i + 6 < len(tokens):
            bez = SubElement(path_el, qn("a:cubicBezTo"))
            for j in range(3):
                pt = SubElement(bez, qn("a:pt"))
                pt.set("x", tokens[i + 1 + j * 2])
                pt.set("y", tokens[i + 2 + j * 2])
            i += 7
        elif cmd == "Z":
            SubElement(path_el, qn("a:close"))
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
    else:
        ln = SubElement(spPr, qn("a:ln"))
        SubElement(ln, qn("a:noFill"))
