"""레이아웃 인덱스 → 슬라이드 레이아웃 매핑.

AWS PPTX 템플릿 내 슬라이드 레이아웃 인덱스와 placeholder 정보를 정의합니다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutInfo:
    """슬라이드 레이아웃 매핑 정보."""

    layout_index: int
    layout_name: str
    title_ph: int | None = None
    subtitle_ph: int | None = None
    body_ph: int | None = None
    picture_ph: int | None = None


# layout_index → LayoutInfo 매핑
#
# 템플릿: "2026 Confidential AWS Powerpoint Template Light & Dark Themes.pptx"
#
# [0]  Title Side 1A             - CENTER_TITLE(ph0) + SUBTITLE(ph1)
# [22] Title and Bulleted Content - TITLE(ph0) + OBJECT(ph1)
# [28] Title, Content, and Image w/ Gradient - TITLE(ph0) + OBJECT(ph1) + PICTURE(ph14)
# [21] Title and Content         - TITLE(ph0) + OBJECT(ph1)
# [87] Thank You Option 1       - BODY placeholders only
# [88] Blank                     - No placeholders
LAYOUT_MAP: dict[int, LayoutInfo] = {
    0: LayoutInfo(
        layout_index=0,
        layout_name="Title Side 1A",
        title_ph=0,
        subtitle_ph=1,
    ),
    28: LayoutInfo(
        layout_index=28,
        layout_name="2_Title, Content, and Image w/ Gradient",
        title_ph=0,
        body_ph=1,
        picture_ph=14,
    ),
    22: LayoutInfo(
        layout_index=22,
        layout_name="Title and Bulleted Content",
        title_ph=0,
        body_ph=1,
    ),
    21: LayoutInfo(
        layout_index=21,
        layout_name="Title and Content",
        title_ph=0,
        body_ph=1,
    ),
    87: LayoutInfo(
        layout_index=87,
        layout_name="Thank You Option 1",
    ),
    88: LayoutInfo(
        layout_index=88,
        layout_name="Blank",
    ),
}

DEFAULT_LAYOUT_INDEX = 22


def find_blank_layout_index(prs) -> int:
    """프레젠테이션에서 placeholder가 없는 blank 레이아웃 인덱스를 찾습니다.

    찾지 못하면 LAYOUT_MAP[88]에 등록된 기본 인덱스를 반환합니다.
    """
    for i, layout in enumerate(prs.slide_layouts):
        name_lower = layout.name.lower()
        if "blank" in name_lower and len(layout.placeholders) == 0:
            return i
    return LAYOUT_MAP[88].layout_index


def get_layout_info(layout_index: int) -> LayoutInfo:
    """layout_index에 대응하는 LayoutInfo를 반환합니다.

    알 수 없는 layout_index이면 text_only(22)로 폴백합니다.
    """
    return LAYOUT_MAP.get(layout_index, LAYOUT_MAP[DEFAULT_LAYOUT_INDEX])
