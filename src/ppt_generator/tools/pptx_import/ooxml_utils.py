"""OOXML 상수 매핑 및 유틸리티 모듈.

MSO_SHAPE 역매핑 테이블, 화살표 도형 집합, custGeom → SVG 변환 등
PPTX 임포트에 필요한 OOXML 관련 상수와 유틸리티를 제공한다.
"""

from __future__ import annotations

import re
from xml.etree.ElementTree import Element

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

# PP_ALIGN → alignment 문자열 매핑
ALIGN_REVERSE_MAP = {
    PP_ALIGN.LEFT: "left",
    PP_ALIGN.CENTER: "center",
    PP_ALIGN.RIGHT: "right",
}

# MSO_SHAPE → shape_type 문자열 매핑
SHAPE_TYPE_REVERSE_MAP = {
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
ARROW_SHAPE_TYPES = {
    MSO_SHAPE.LEFT_RIGHT_ARROW,
    MSO_SHAPE.UP_DOWN_ARROW,
    MSO_SHAPE.BENT_ARROW,
    MSO_SHAPE.NOTCHED_RIGHT_ARROW,
    MSO_SHAPE.STRIPED_RIGHT_ARROW,
    MSO_SHAPE.BLOCK_ARC,
}

# 모노스페이스 폰트 감지용 패턴
MONOSPACE_FONTS = frozenset(
    {
        "consolas",
        "courier",
        "courier new",
        "monaco",
        "menlo",
        "lucida console",
        "dejavu sans mono",
        "source code pro",
        "fira code",
        "fira mono",
        "jetbrains mono",
        "d2coding",
    }
)

# slide_type 추론용 closing 키워드
CLOSING_KEYWORDS = re.compile(
    r"(감사|thank|q\s*&\s*a|질문|문의|contact|끝|the\s+end)",
    re.IGNORECASE,
)


def custgeom_to_svg_path(spPr: Element) -> str | None:
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
                    coords = " ".join(
                        f"{p.get('x', '0')} {p.get('y', '0')}" for p in pts
                    )
                    parts.append(f"C {coords}")
            elif tag == "close":
                parts.append("Z")

    if not parts:
        return None
    return f"{vb_w} {vb_h} {' '.join(parts)}"
