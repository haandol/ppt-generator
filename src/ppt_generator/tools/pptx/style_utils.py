"""HTML 스타일 파싱 및 PPTX 좌표/폰트 변환 유틸리티.

ExportService에서 self 상태에 의존하지 않는 순수 함수들을 모아둔 모듈.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from pptx.dml.color import RGBColor

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
    PPTX_FONT_MIN_SIZE_PT,
    PPTX_FONT_SCALE_FACTOR,
    REM_TO_PX,
)

logger = logging.getLogger(__name__)


@dataclass
class RichTextFragment:
    """HTML 요소에서 추출한 서식 정보를 담는 데이터 구조."""

    text: str
    font_size: int | None = None
    color: str | None = None
    bold: bool = False
    italic: bool = False
    bullet_level: int = -1  # -1 = 불릿 아님, 0 = 1단계, 1 = 2단계
    paragraph_break: bool = False  # True이면 이 fragment 앞에서 새 paragraph 시작


def parse_inline_style(style_str: str | None) -> dict[str, str]:
    """인라인 style 문자열을 key-value dict로 파싱."""
    if not style_str:
        return {}
    result: dict[str, str] = {}
    for part in style_str.split(";"):
        part = part.strip()
        if ":" not in part:
            continue
        key, _, value = part.partition(":")
        result[key.strip().lower()] = value.strip()
    return result


def px_to_inches(value: str, axis: str) -> float | None:
    """CSS px 값을 PPTX 인치 단위로 변환."""
    match = re.match(r"(-?\d+(?:\.\d+)?)\s*px", value.strip())
    if not match:
        if re.match(r"-?\d+(?:\.\d+)?$", value.strip()):
            px = float(value.strip())
        else:
            logger.warning("px이 아닌 단위 무시: %s", value)
            return None
    else:
        px = float(match.group(1))
    factor = EXPORT_PX_TO_INCHES_X if axis == "x" else EXPORT_PX_TO_INCHES_Y
    return px * factor


def extract_font_size(style: dict[str, str]) -> int | None:
    """CSS style dict에서 폰트 크기를 px 단위 정수로 추출."""
    fs = style.get("font-size", "")
    match = re.match(r"(\d+(?:\.\d+)?)\s*px", fs)
    if match:
        return int(float(match.group(1)))
    match = re.match(r"(\d+(?:\.\d+)?)\s*pt", fs)
    if match:
        return int(float(match.group(1)))
    match = re.match(r"(\d+(?:\.\d+)?)\s*rem", fs)
    if match:
        return int(float(match.group(1)) * REM_TO_PX)
    match = re.match(r"(\d+(?:\.\d+)?)\s*em", fs)
    if match:
        return int(float(match.group(1)) * REM_TO_PX)
    return None


def is_bold(element, style: dict[str, str]) -> bool:
    """HTML 요소와 스타일에서 bold 여부를 판별."""
    if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return True
    if element.find(("strong", "b")):
        return True
    fw = style.get("font-weight", "")
    if fw in ("bold", "bolder") or (fw.isdigit() and int(fw) >= 700):
        return True
    return False


def extract_color(style: dict[str, str]) -> RGBColor | None:
    """CSS style dict에서 텍스트 색상을 RGBColor로 추출."""
    color_str = style.get("color", "")
    return parse_color(color_str)


def parse_color(color_str: str) -> RGBColor | None:
    """CSS 색상 문자열을 python-pptx RGBColor로 변환."""
    if not color_str:
        return None
    # #RRGGBB or #RGB
    hex_match = re.match(r"#([0-9a-fA-F]{6})", color_str)
    if hex_match:
        hex_val = hex_match.group(1)
        return RGBColor(int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16))
    short_hex = re.match(r"#([0-9a-fA-F]{3})(?:\s|;|$)", color_str)
    if short_hex:
        h = short_hex.group(1)
        return RGBColor(int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
    # rgb(r, g, b)
    rgb_match = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color_str)
    if rgb_match:
        return RGBColor(int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))
    return None


def resolve_int(value) -> int | None:
    """값을 int로 변환. 실패 시 None 반환."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def scale_font_size(raw_pt: int | None) -> int | None:
    """HTML에서 추출한 폰트 크기를 프레젠테이션에 적합하게 스케일업한다."""
    if raw_pt is None:
        return None
    scaled = int(raw_pt * PPTX_FONT_SCALE_FACTOR)
    return max(scaled, PPTX_FONT_MIN_SIZE_PT)


def merge_styles(
    parent: dict[str, str | None], inline: dict[str, str], tag: str,
) -> dict[str, str | None]:
    """부모 style을 자식에 전파하되, 자식의 명시적 style이 우선."""
    merged: dict[str, str | None] = dict(parent)

    fs = extract_font_size(inline)
    if fs is not None:
        merged["font_size"] = fs

    color_str = inline.get("color", "")
    if color_str:
        merged["color"] = color_str

    fw = inline.get("font-weight", "")
    if fw in ("bold", "bolder") or (fw.isdigit() and int(fw) >= 700):
        merged["bold"] = True
    elif tag in ("strong", "b"):
        merged["bold"] = True

    fs_style = inline.get("font-style", "")
    if fs_style == "italic":
        merged["italic"] = True
    elif tag in ("em", "i"):
        merged["italic"] = True

    return merged


def get_position_and_size(style: dict[str, str]) -> tuple[float, float, float, float]:
    """CSS style dict에서 위치와 크기를 인치 단위 튜플로 추출."""
    left = px_to_inches(style.get("left", "0"), "x") or 0.0
    top = px_to_inches(style.get("top", "0"), "y") or 0.0
    width = px_to_inches(style.get("width", "72"), "x") or 1.0
    height = px_to_inches(style.get("height", "72"), "y") or 1.0
    return left, top, width, height
