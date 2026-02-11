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
# 템플릿: "2026 Confidential AWS Powerpoint Template Light & Dark Themes.pptx" (97종)
# theme: "dark" = 이름에 Dark/Gradient 포함 또는 어두운 배경, 나머지 "light"
# [95] Do Not Use 레이아웃은 제외
#
# title_ph/subtitle_ph/body_ph/picture_ph: 주요 콘텐츠 placeholder idx
# (extra placeholder는 생략, python-pptx에서 인덱스로 직접 접근 가능)
LAYOUT_MAP: dict[int, LayoutInfo] = {
    # --- Title/Cover (0~8) ---
    0: LayoutInfo(layout_index=0, layout_name="Title Side 1A", theme="light", title_ph=0, subtitle_ph=1),
    1: LayoutInfo(layout_index=1, layout_name="Title Slide 1B", theme="light", title_ph=0, subtitle_ph=1),
    2: LayoutInfo(layout_index=2, layout_name="Title Slide 1C", theme="light", title_ph=0, subtitle_ph=1),
    3: LayoutInfo(layout_index=3, layout_name="Title Slide 2A", theme="light", title_ph=0, subtitle_ph=1),
    4: LayoutInfo(layout_index=4, layout_name="Title Slide 2B", theme="light", title_ph=0, subtitle_ph=1),
    5: LayoutInfo(layout_index=5, layout_name="1_Title Slide 2B", theme="light", title_ph=0, subtitle_ph=1),
    6: LayoutInfo(layout_index=6, layout_name="2_Title Slide 1B", theme="light", title_ph=0),
    7: LayoutInfo(layout_index=7, layout_name="3_Title Slide 1B", theme="light", title_ph=0),
    8: LayoutInfo(layout_index=8, layout_name="1_Title Slide 1B", theme="light", title_ph=0),
    # --- Agenda (9~14) ---
    9: LayoutInfo(layout_index=9, layout_name="Agenda Slide 1", theme="light", title_ph=0, body_ph=10),
    10: LayoutInfo(layout_index=10, layout_name="Agenda Slide 2", theme="light", title_ph=0, body_ph=10),
    11: LayoutInfo(layout_index=11, layout_name="Agenda Slide 3", theme="light", title_ph=0, body_ph=10),
    12: LayoutInfo(layout_index=12, layout_name="1_Agenda Slide 4", theme="light", title_ph=0, body_ph=10, picture_ph=15),
    13: LayoutInfo(layout_index=13, layout_name="2_Agenda Slide 5", theme="light", title_ph=0),
    14: LayoutInfo(layout_index=14, layout_name="1_Agenda Slide 6", theme="light", title_ph=0, picture_ph=14),
    # --- Title Only / Blank (15~20) ---
    15: LayoutInfo(layout_index=15, layout_name="Title Only", theme="light", title_ph=0),
    16: LayoutInfo(layout_index=16, layout_name="Title Only Gradient 1", theme="dark", title_ph=0),
    17: LayoutInfo(layout_index=17, layout_name="Title Only Gradient 2", theme="dark", title_ph=0),
    18: LayoutInfo(layout_index=18, layout_name="Title Only Gradient 3", theme="dark", title_ph=0),
    19: LayoutInfo(layout_index=19, layout_name="Title and Subtitle", theme="light", title_ph=0, body_ph=10),
    20: LayoutInfo(layout_index=20, layout_name="Blank", theme="light"),
    # --- Content (21~26, 86) ---
    21: LayoutInfo(layout_index=21, layout_name="Title and Content", theme="light", title_ph=0, body_ph=1),
    22: LayoutInfo(layout_index=22, layout_name="Title and Bulleted Content", theme="light", title_ph=0, body_ph=1),
    23: LayoutInfo(layout_index=23, layout_name="Title, Subtitle, and Content", theme="light", title_ph=0, body_ph=1),
    24: LayoutInfo(layout_index=24, layout_name="Title, Subtitle, and Bulleted Content", theme="light", title_ph=0, body_ph=1),
    25: LayoutInfo(layout_index=25, layout_name="Title, Content, and Image", theme="light", title_ph=0, body_ph=1),
    26: LayoutInfo(layout_index=26, layout_name="1_Title, Content, and Image", theme="light", title_ph=0, body_ph=1),
    86: LayoutInfo(layout_index=86, layout_name="Content with Caption", theme="light", title_ph=0, body_ph=1),
    # --- Two Content (27, 29~39) ---
    27: LayoutInfo(layout_index=27, layout_name="Two Content", theme="light", title_ph=0, body_ph=1),
    28: LayoutInfo(layout_index=28, layout_name="2_Title, Content, and Image w/ Gradient", theme="dark", title_ph=0, body_ph=1, picture_ph=14),
    29: LayoutInfo(layout_index=29, layout_name="1_Two Content", theme="light", title_ph=0, body_ph=1),
    30: LayoutInfo(layout_index=30, layout_name="Comparison", theme="light", title_ph=0, body_ph=1),
    31: LayoutInfo(layout_index=31, layout_name="1_Comparison w/ divider", theme="light", title_ph=0, body_ph=1),
    32: LayoutInfo(layout_index=32, layout_name="Two Content with Bullets", theme="light", title_ph=0, body_ph=1),
    33: LayoutInfo(layout_index=33, layout_name="Two Content with Subtitle", theme="light", title_ph=0, body_ph=1),
    34: LayoutInfo(layout_index=34, layout_name="Two Content, Subtitle, and Bullets", theme="light", title_ph=0, body_ph=1),
    35: LayoutInfo(layout_index=35, layout_name="1_Two Content, Subtitle, and Bullets images", theme="light", title_ph=0, body_ph=1, picture_ph=15),
    36: LayoutInfo(layout_index=36, layout_name="2_Two Content, Subtitle, and Bullets images", theme="light", title_ph=0, body_ph=10, picture_ph=16),
    37: LayoutInfo(layout_index=37, layout_name="3_Two Content, Subtitle, and Bullets image", theme="light", title_ph=0, body_ph=10, picture_ph=14),
    38: LayoutInfo(layout_index=38, layout_name="3_Two Content, Subtitle, and Bullets diagonal images", theme="light", title_ph=0, body_ph=10, picture_ph=15),
    39: LayoutInfo(layout_index=39, layout_name="4_Two Content, Subtitle, and Bullets diagonal images 2", theme="light", title_ph=0, body_ph=10, picture_ph=15),
    # --- Three Column (40~48) ---
    40: LayoutInfo(layout_index=40, layout_name="Three column with subheadings", theme="light", title_ph=0, body_ph=1),
    41: LayoutInfo(layout_index=41, layout_name="2_Three-column, subtitle, bullets layout", theme="light", title_ph=0, body_ph=10),
    42: LayoutInfo(layout_index=42, layout_name="3_Two Content, Subtitle, and Bullets images", theme="light", title_ph=0, body_ph=1, picture_ph=16),
    43: LayoutInfo(layout_index=43, layout_name="4_Two Content, Subtitle, and Bullets images", theme="light", title_ph=0, body_ph=1),
    44: LayoutInfo(layout_index=44, layout_name="2_Three column with subheadings Comparison", theme="light", title_ph=0, body_ph=1),
    45: LayoutInfo(layout_index=45, layout_name="2_Three column with subheadings boxes", theme="light", title_ph=0, body_ph=1),
    46: LayoutInfo(layout_index=46, layout_name="3_Three column with subheadings boxes", theme="light", title_ph=0, body_ph=1),
    47: LayoutInfo(layout_index=47, layout_name="1_Three column with subheadings", theme="light", title_ph=0, body_ph=1, picture_ph=17),
    48: LayoutInfo(layout_index=48, layout_name="2_Three column with subheadings numbers", theme="light", title_ph=0, body_ph=2),
    # --- Four/Five/Six Column (49~55) ---
    49: LayoutInfo(layout_index=49, layout_name="Four column with subheadings", theme="light", title_ph=0, body_ph=1),
    50: LayoutInfo(layout_index=50, layout_name="1_Four column with subheadings Images", theme="light", title_ph=0, body_ph=1, picture_ph=20),
    51: LayoutInfo(layout_index=51, layout_name="2_Four column with subheadings Images 2", theme="light", title_ph=0, body_ph=1, picture_ph=20),
    52: LayoutInfo(layout_index=52, layout_name="3_Four column with subheadings Images rectangle", theme="light", title_ph=0, body_ph=1, picture_ph=20),
    53: LayoutInfo(layout_index=53, layout_name="4_Collage images, Subtitle, and content", theme="light", title_ph=0, body_ph=10, picture_ph=17),
    54: LayoutInfo(layout_index=54, layout_name="1_Five column with subheadings", theme="light", title_ph=0, body_ph=1),
    55: LayoutInfo(layout_index=55, layout_name="2_Six column with subheadings", theme="light", title_ph=0, body_ph=25, picture_ph=42),
    # --- Picture/Photo (56~63) ---
    56: LayoutInfo(layout_index=56, layout_name="Picture with Caption", theme="light", title_ph=0, body_ph=2, picture_ph=1),
    57: LayoutInfo(layout_index=57, layout_name="1_Picture with Caption_Half Page", theme="light", title_ph=0, body_ph=2, picture_ph=1),
    58: LayoutInfo(layout_index=58, layout_name="2_Picture with Caption_Blue Image", theme="light", title_ph=0, body_ph=2, picture_ph=13),
    59: LayoutInfo(layout_index=59, layout_name="3_Picture with Caption_Blue Image 2", theme="light", title_ph=0, body_ph=2, picture_ph=20),
    60: LayoutInfo(layout_index=60, layout_name="3_Picture with Caption_Circle Image", theme="light", title_ph=0, body_ph=2, picture_ph=15),
    61: LayoutInfo(layout_index=61, layout_name="3_Title, content layout, and circle icons", theme="light", title_ph=0, body_ph=21, picture_ph=36),
    62: LayoutInfo(layout_index=62, layout_name="4_Title, content layout, and circle icons, image", theme="light", title_ph=0, body_ph=21, picture_ph=34),
    63: LayoutInfo(layout_index=63, layout_name="Full Screen Photo", theme="light", picture_ph=10),
    # --- Special (64~70) ---
    64: LayoutInfo(layout_index=64, layout_name="Customer logo wall light", theme="light", title_ph=0, body_ph=13),
    65: LayoutInfo(layout_index=65, layout_name="3_Case Study 1", theme="light", title_ph=0, body_ph=14, picture_ph=29),
    66: LayoutInfo(layout_index=66, layout_name="3_Case Study 2", theme="light", title_ph=0, body_ph=14, picture_ph=33),
    67: LayoutInfo(layout_index=67, layout_name="3_Case Study 3", theme="light", title_ph=0, body_ph=14, picture_ph=20),
    68: LayoutInfo(layout_index=68, layout_name="3_Case Study 4", theme="light", title_ph=0, body_ph=14, picture_ph=29),
    69: LayoutInfo(layout_index=69, layout_name="3_Case Study 5", theme="light", title_ph=0, body_ph=14, picture_ph=29),
    70: LayoutInfo(layout_index=70, layout_name="4_AWS Roles", theme="light", title_ph=0, body_ph=14, picture_ph=48),
    # --- Quote (71~74) ---
    71: LayoutInfo(layout_index=71, layout_name="Quote", theme="light", title_ph=0, body_ph=15),
    72: LayoutInfo(layout_index=72, layout_name="Quote Gradient 1", theme="dark", title_ph=0, body_ph=15),
    73: LayoutInfo(layout_index=73, layout_name="Quote Gradient 2", theme="dark", title_ph=0, body_ph=15),
    74: LayoutInfo(layout_index=74, layout_name="Quote Gradient 3", theme="dark", title_ph=0, body_ph=15),
    # --- Section Header (75~80) ---
    75: LayoutInfo(layout_index=75, layout_name="Section Header Option 2", theme="light", title_ph=0),
    76: LayoutInfo(layout_index=76, layout_name="1_Section Header Option 2 with image", theme="light", title_ph=0, picture_ph=14),
    77: LayoutInfo(layout_index=77, layout_name="Section Header Option 1", theme="light", title_ph=0),
    78: LayoutInfo(layout_index=78, layout_name="1_Section Header Option 1 with image", theme="light", title_ph=0, picture_ph=16),
    79: LayoutInfo(layout_index=79, layout_name="Section Header Option 3", theme="light", title_ph=0),
    80: LayoutInfo(layout_index=80, layout_name="1_Section Header Option 3 with image", theme="light", title_ph=0, picture_ph=14),
    # --- Code (81~82) ---
    81: LayoutInfo(layout_index=81, layout_name="Code", theme="light", title_ph=0, body_ph=1),
    82: LayoutInfo(layout_index=82, layout_name="Code - Two Content", theme="light", title_ph=0, body_ph=1),
    # --- Q&A / Video (83~85) ---
    83: LayoutInfo(layout_index=83, layout_name="Q&A", theme="light", title_ph=0),
    84: LayoutInfo(layout_index=84, layout_name="Video or Demo Divider", theme="light", title_ph=0),
    85: LayoutInfo(layout_index=85, layout_name="Video", theme="light"),
    # --- Thank You (87~92) ---
    87: LayoutInfo(layout_index=87, layout_name="Thank You Option 1", theme="light", body_ph=10),
    88: LayoutInfo(layout_index=88, layout_name="1_Thank You Option 1 Alt", theme="light", body_ph=10, picture_ph=14),
    89: LayoutInfo(layout_index=89, layout_name="Thank You Option 2", theme="light", body_ph=10),
    90: LayoutInfo(layout_index=90, layout_name="1_Thank You Option 2 Alt", theme="light", body_ph=10, picture_ph=16),
    91: LayoutInfo(layout_index=91, layout_name="Thank You Option 3", theme="light", body_ph=10),
    92: LayoutInfo(layout_index=92, layout_name="1_Thank You Option 3 Alt", theme="light", body_ph=10, picture_ph=14),
    # --- Other (93~94, 96) ---
    93: LayoutInfo(layout_index=93, layout_name="Title and Vertical Text", theme="light", title_ph=0, body_ph=1),
    94: LayoutInfo(layout_index=94, layout_name="Vertical Title and Text", theme="light", title_ph=0, body_ph=1),
    96: LayoutInfo(layout_index=96, layout_name="Title Only Dark", theme="dark"),
}

DEFAULT_LAYOUT_INDEX = 22


def get_layout_info(layout_index: int) -> LayoutInfo:
    """layout_index에 대응하는 LayoutInfo를 반환합니다.

    알 수 없는 layout_index이면 text_only(22)로 폴백합니다.
    """
    return LAYOUT_MAP.get(layout_index, LAYOUT_MAP[DEFAULT_LAYOUT_INDEX])
