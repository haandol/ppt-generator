"""배경 이미지 유틸리티 — 테마 감지 및 이미지 선택.

제목 슬라이드와 Thank You 슬라이드에 배경 이미지를 적용하기 위한 공유 유틸리티.
HTML 렌더러와 PPTX 서비스 양쪽에서 사용한다.
"""

from __future__ import annotations

import base64
import random
from pathlib import Path

from ppt_generator.interfaces.constants import TEMPLATE_BG_IMAGES_DIR

# 테마(dark/light)별 선택된 이미지를 캐시하여 세션 내 일관성 보장
_theme_cache: dict[str, Path] = {}


def reset_cache() -> None:
    """테마 캐시를 초기화한다. 새 세션/프레젠테이션 시작 시 호출."""
    _theme_cache.clear()


def is_dark_background(color: str | None) -> bool:
    """배경색의 밝기를 분석하여 dark 테마 여부를 반환한다.

    W3C 상대 휘도(relative luminance) 기준 0.5 이하이면 dark로 판단.
    """
    if not color:
        return True  # 기본값: dark

    hex_color = color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) != 6:
        return True

    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
    except ValueError:
        return True

    # sRGB → 선형 변환 후 상대 휘도 계산
    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
    return luminance < 0.5


def get_bg_image_path(background_color: str | None) -> Path | None:
    """테마(dark/light) 폴더에서 배경 이미지 1개를 선택하여 반환한다.

    같은 테마 내에서는 캐시된 이미지를 반환하여 제목/Thank You 슬라이드가
    동일한 배경을 사용하도록 보장한다.
    """
    theme = "dark" if is_dark_background(background_color) else "light"

    if theme in _theme_cache:
        return _theme_cache[theme]

    theme_dir = TEMPLATE_BG_IMAGES_DIR / theme
    if not theme_dir.is_dir():
        return None

    images = [p for p in theme_dir.glob("*.png") if "logo" not in p.name.lower()]
    if not images:
        return None

    selected = random.choice(images)  # noqa: S311
    _theme_cache[theme] = selected
    return selected


def get_bg_image_bytes(background_color: str | None) -> bytes | None:
    """배경 이미지 PNG 파일을 바이트로 읽어 반환한다 (PPTX용)."""
    path = get_bg_image_path(background_color)
    if path is None:
        return None
    return path.read_bytes()


def get_bg_image_base64(background_color: str | None) -> str | None:
    """배경 이미지를 base64로 인코딩하여 반환한다 (HTML용)."""
    image_bytes = get_bg_image_bytes(background_color)
    if image_bytes is None:
        return None
    return base64.b64encode(image_bytes).decode("ascii")


# --- 로고 이미지 ---


def get_logo_image_path(background_color: str | None) -> Path | None:
    """테마에 맞는 로고 이미지 경로를 반환한다.

    각 테마 폴더(dark/light)의 aws-logo.png를 사용한다.
    """
    theme = "dark" if is_dark_background(background_color) else "light"
    logo_path = TEMPLATE_BG_IMAGES_DIR / theme / "aws-logo.png"
    if not logo_path.is_file():
        return None
    return logo_path


def get_logo_image_bytes(background_color: str | None) -> bytes | None:
    """로고 PNG 파일을 바이트로 읽어 반환한다 (PPTX용)."""
    path = get_logo_image_path(background_color)
    if path is None:
        return None
    return path.read_bytes()


def get_logo_image_base64(background_color: str | None) -> str | None:
    """로고 이미지를 base64로 인코딩하여 반환한다 (HTML용)."""
    logo_bytes = get_logo_image_bytes(background_color)
    if logo_bytes is None:
        return None
    return base64.b64encode(logo_bytes).decode("ascii")
