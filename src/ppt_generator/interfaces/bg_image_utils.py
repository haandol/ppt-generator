"""배경 이미지 유틸리티 — 테마 기반 이미지 선택.

제목 슬라이드와 Takeaway 슬라이드에 배경 이미지를 적용하기 위한 공유 유틸리티.
HTML 렌더러와 PPTX 서비스 양쪽에서 사용한다.

배경 이미지 선택은 프로젝트 단위로 결정론적이다 — 프로젝트 시드(seed)가
설정되면 같은 (시드, 테마) 조합은 항상 같은 이미지를 고른다. 따라서 같은
프로젝트는 재export·경로(HTML/PPTX)와 무관하게 동일 배경을 쓰고, 프로젝트
간에는 시드가 달라 다양성이 유지된다. 시드가 설정되지 않은 경우(레거시 호출)
테마별 무작위 1회 선택을 캐시해 한 export 안에서의 일관성만 보장한다.
"""

from __future__ import annotations

import base64
import hashlib
import random
from pathlib import Path

from ppt_generator.interfaces.constants import TEMPLATE_BG_IMAGES_DIR

# 테마(dark/light)별 선택된 이미지를 캐시하여 세션 내 일관성 보장
_theme_cache: dict[str, Path] = {}

# 프로젝트 단위 결정론 선택을 위한 시드. set_project_seed 로 설정.
_project_seed: str | None = None


def reset_cache() -> None:
    """테마 캐시를 초기화한다. 새 세션/프레젠테이션 시작 시 호출."""
    _theme_cache.clear()


def set_project_seed(seed: str | None) -> None:
    """배경 선택을 고정할 프로젝트 시드를 설정한다.

    시드가 설정되면 get_bg_image_path 가 (시드, 테마) 로부터 결정론적으로
    이미지를 고른다 — 같은 프로젝트는 항상 같은 배경. 시드 변경 시 테마
    캐시도 비워 이전 선택이 남지 않게 한다. None 을 주면 결정론 모드를 끄고
    레거시 무작위 캐시 동작으로 돌아간다.
    """
    global _project_seed
    if seed != _project_seed:
        _theme_cache.clear()
    _project_seed = seed


def get_bg_image_path(color_theme: str = "dark") -> Path | None:
    """테마(dark/light) 폴더에서 배경 이미지 1개를 선택하여 반환한다.

    프로젝트 시드가 설정돼 있으면 (시드, 테마) 로부터 결정론적으로 고른다.
    그렇지 않으면 테마별 무작위 1회 선택을 캐시해 같은 테마 내에서는 동일
    이미지를 반환한다 (제목/Takeaway 슬라이드가 같은 배경을 쓰도록).

    Args:
        color_theme: "dark" 또는 "light" (기본: "dark")
    """
    theme = color_theme if color_theme in ("dark", "light") else "dark"

    if theme in _theme_cache:
        return _theme_cache[theme]

    theme_dir = TEMPLATE_BG_IMAGES_DIR / theme
    if not theme_dir.is_dir():
        return None

    # 파일 순서가 OS 에 따라 흔들리지 않도록 정렬 — 결정론 선택의 전제.
    images = sorted(theme_dir.glob("*.png"))
    if not images:
        return None

    if _project_seed is not None:
        # (시드, 테마) 해시로 인덱스를 정해 프로젝트마다 안정적으로 다른 이미지.
        digest = hashlib.sha256(f"{_project_seed}:{theme}".encode()).hexdigest()
        idx = int(digest, 16) % len(images)
        selected = images[idx]
    else:
        selected = random.choice(images)  # noqa: S311

    _theme_cache[theme] = selected
    return selected


def get_bg_image_bytes(color_theme: str = "dark") -> bytes | None:
    """배경 이미지 PNG 파일을 바이트로 읽어 반환한다 (PPTX용)."""
    path = get_bg_image_path(color_theme)
    if path is None:
        return None
    return path.read_bytes()


def get_bg_image_base64(color_theme: str = "dark") -> str | None:
    """배경 이미지를 base64로 인코딩하여 반환한다 (HTML용)."""
    image_bytes = get_bg_image_bytes(color_theme)
    if image_bytes is None:
        return None
    return base64.b64encode(image_bytes).decode("ascii")
