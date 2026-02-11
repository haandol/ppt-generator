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
    theme: str = "light"  # "light" | "dark"
    title_ph: int | None = None
    subtitle_ph: int | None = None
    body_ph: int | None = None
    picture_ph: int | None = None


# layout_index → LayoutInfo 매핑
#
# 템플릿: "2026 Confidential AWS Powerpoint Template Light & Dark Themes.pptx"
# theme: 레이아웃 이름에 "Dark"/"Gradient" 포함 또는 배경이 어두운 경우 "dark"
#
# [0]  Title Side 1A             - CENTER_TITLE(ph0) + SUBTITLE(ph1)
# [22] Title and Bulleted Content - TITLE(ph0) + OBJECT(ph1)
# [28] Title, Content, and Image w/ Gradient - TITLE(ph0) + OBJECT(ph1) + PICTURE(ph14)
# [21] Title and Content         - TITLE(ph0) + OBJECT(ph1)
# [87] Thank You Option 1       - BODY placeholders only
# [20] Blank                     - 메타데이터 placeholder만 (Date/Footer/SlideNumber)
LAYOUT_MAP: dict[int, LayoutInfo] = {
    0: LayoutInfo(
        layout_index=0,
        layout_name="Title Side 1A",
        theme="light",
        title_ph=0,
        subtitle_ph=1,
    ),
    28: LayoutInfo(
        layout_index=28,
        layout_name="2_Title, Content, and Image w/ Gradient",
        theme="dark",
        title_ph=0,
        body_ph=1,
        picture_ph=14,
    ),
    22: LayoutInfo(
        layout_index=22,
        layout_name="Title and Bulleted Content",
        theme="light",
        title_ph=0,
        body_ph=1,
    ),
    21: LayoutInfo(
        layout_index=21,
        layout_name="Title and Content",
        theme="light",
        title_ph=0,
        body_ph=1,
    ),
    87: LayoutInfo(
        layout_index=87,
        layout_name="Thank You Option 1",
        theme="light",
    ),
    88: LayoutInfo(
        layout_index=88,
        layout_name="Blank",
        theme="light",
    ),
}

DEFAULT_LAYOUT_INDEX = 22


# PP_PLACEHOLDER enum의 실제 int 값 (python-pptx 내부)
# DATE=16, FOOTER=15, SLIDE_NUMBER=13
_METADATA_PH_TYPES = {13, 15, 16}


def _count_content_placeholders(layout) -> int:
    """Date/Footer/Slide Number 등 메타데이터 placeholder를 제외한 콘텐츠 placeholder 수."""
    return sum(
        1 for p in layout.placeholders
        if int(p.placeholder_format.type) not in _METADATA_PH_TYPES
    )


def find_blank_layout_index(prs) -> int:
    """프레젠테이션에서 콘텐츠 placeholder가 없는 blank 레이아웃 인덱스를 찾습니다.

    Date/Footer/Slide Number placeholder는 메타데이터로 간주하여 무시합니다.
    "do not use" 레이아웃은 제외합니다.

    3단계 폴백:
    1. 이름에 'blank'가 포함되고 콘텐츠 placeholder가 없는 레이아웃
    2. 콘텐츠 placeholder가 없는 아무 레이아웃 ('do not use' 제외)
    3. 콘텐츠 placeholder 수가 가장 적은 레이아웃 ('do not use' 제외)
    """
    # 1단계: blank + 콘텐츠 placeholder 없음
    for i, layout in enumerate(prs.slide_layouts):
        name_lower = layout.name.lower()
        if "blank" in name_lower and _count_content_placeholders(layout) == 0:
            return i

    # 2단계: 콘텐츠 placeholder가 없는 아무 레이아웃 (do not use 제외)
    for i, layout in enumerate(prs.slide_layouts):
        name_lower = layout.name.lower()
        if "do not use" in name_lower:
            continue
        if _count_content_placeholders(layout) == 0:
            return i

    # 3단계: 콘텐츠 placeholder 최소 레이아웃 (do not use 제외)
    min_ph_count = float("inf")
    min_idx = 0
    for i, layout in enumerate(prs.slide_layouts):
        name_lower = layout.name.lower()
        if "do not use" in name_lower:
            continue
        ph_count = _count_content_placeholders(layout)
        if ph_count < min_ph_count:
            min_ph_count = ph_count
            min_idx = i
    return min_idx


def get_layout_info(layout_index: int) -> LayoutInfo:
    """layout_index에 대응하는 LayoutInfo를 반환합니다.

    알 수 없는 layout_index이면 text_only(22)로 폴백합니다.
    """
    return LAYOUT_MAP.get(layout_index, LAYOUT_MAP[DEFAULT_LAYOUT_INDEX])
