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

    xfrm 의 flipH/flipV 는 도형 bounding box 내에서 좌표를 미러링하므로(flipH:
    x→w−x, flipV: y→h−y), 이를 무시하면 꺾인 화살표(L자 커넥터 등)가 반대 방향으로
    그려져 연결 대상 도형에서 어긋난다. 여기서 좌표에 flip 을 직접 반영해 svg_path 를
    자기완결적으로 만든다.

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

    xfrm = spPr.find(qn("a:xfrm"))
    flip_h = xfrm is not None and xfrm.get("flipH") == "1"
    flip_v = xfrm is not None and xfrm.get("flipV") == "1"

    # (명령문자, [(x, y), ...]) 형태로 먼저 수집한다. flip 은 viewBox(vb_w/vb_h)를
    # 알아야 미러링할 수 있으므로 전체 path 를 훑어 vb 크기를 먼저 확정한 뒤 적용한다.
    commands: list[tuple[str, list[tuple[float, float]]]] = []
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
                    commands.append(("M", [_pt_xy(pt)]))
            elif tag == "lnTo":
                pt = cmd.find(qn("a:pt"))
                if pt is not None:
                    commands.append(("L", [_pt_xy(pt)]))
            elif tag == "cubicBezTo":
                pts = cmd.findall(qn("a:pt"))
                if len(pts) == 3:
                    commands.append(("C", [_pt_xy(p) for p in pts]))
            elif tag == "close":
                commands.append(("Z", []))

    if not commands:
        return None

    def _mirror(x: float, y: float) -> tuple[float, float]:
        return (vb_w - x if flip_h else x, vb_h - y if flip_v else y)

    parts: list[str] = []
    for letter, coords in commands:
        if letter == "Z":
            parts.append("Z")
            continue
        mirrored = [_mirror(x, y) for x, y in coords]
        coord_str = " ".join(f"{_fmt_num(x)} {_fmt_num(y)}" for x, y in mirrored)
        parts.append(f"{letter} {coord_str}")

    return f"{vb_w} {vb_h} {' '.join(parts)}"


def _pt_xy(pt: Element) -> tuple[float, float]:
    """a:pt 요소에서 (x, y) 좌표를 float 로 읽는다."""
    return (float(pt.get("x", "0")), float(pt.get("y", "0")))


def _fmt_num(value: float) -> str:
    """좌표를 정수면 정수 문자열로, 아니면 float 문자열로 포맷한다."""
    if value == int(value):
        return str(int(value))
    return str(value)
