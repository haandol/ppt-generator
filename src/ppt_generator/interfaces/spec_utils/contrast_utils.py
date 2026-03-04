"""텍스트-배경 색상 대비 보정 유틸리티.

WCAG AA 기준 contrast ratio를 검사하고, 부족 시 텍스트 색상을 자동 보정한다.
"""

from __future__ import annotations


def _hex_to_relative_luminance(hex_color: str) -> float:
    """hex 색상 → W3C 상대 휘도(relative luminance).

    sRGB 감마 보정을 적용한 표준 계산.
    잘못된 입력 시 0.0(어두운 색 가정)을 반환한다.
    """
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return 0.0

    try:
        r = int(c[0:2], 16) / 255.0
        g = int(c[2:4], 16) / 255.0
        b = int(c[4:6], 16) / 255.0
    except ValueError:
        return 0.0

    def linearize(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(l1: float, l2: float) -> float:
    """두 상대 휘도 값의 contrast ratio를 계산한다.

    항상 (밝은 쪽 + 0.05) / (어두운 쪽 + 0.05) 형태로 반환 (≥ 1.0).
    """
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_text_contrast(
    text_color: str,
    bg_color: str,
    font_size_pt: int = 16,
    bold: bool = False,
) -> str:
    """텍스트-배경 대비가 WCAG AA 미달 시 텍스트 색상을 보정하여 반환한다.

    대형 텍스트(≥18pt bold 또는 ≥24pt)는 3:1, 그 외 4.5:1 기준.
    대비 부족 시 #FFFFFF / #000000 중 대비가 높은 쪽으로 교체한다.
    """
    is_large = (font_size_pt >= 18 and bold) or font_size_pt >= 24
    threshold = 3.0 if is_large else 4.5

    text_lum = _hex_to_relative_luminance(text_color)
    bg_lum = _hex_to_relative_luminance(bg_color)

    ratio = _contrast_ratio(text_lum, bg_lum)
    if ratio >= threshold:
        return text_color

    # 대비 부족 → 흰색/검정 중 대비가 높은 쪽 선택
    white_lum = 1.0  # #FFFFFF
    black_lum = 0.0  # #000000
    ratio_white = _contrast_ratio(white_lum, bg_lum)
    ratio_black = _contrast_ratio(black_lum, bg_lum)

    return "#FFFFFF" if ratio_white >= ratio_black else "#000000"
