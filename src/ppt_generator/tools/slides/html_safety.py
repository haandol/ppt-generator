"""HTML 렌더링 경계에서 사용하는 컨텍스트별 안전 처리."""

from __future__ import annotations

import base64
import binascii
import html
import math
import posixpath
import re
from typing import Any
from urllib.parse import quote, unquote, urlsplit

_COLOR_RE = re.compile(
    r"(?:#[0-9a-fA-F]{3,8}|"
    r"(?:rgb|rgba|hsl|hsla)\([0-9.%+\-,\s]+\)|"
    r"transparent|black|white|none)"
)
_SVG_PATH_RE = re.compile(r"[MmLlHhVvCcSsQqTtAaZz0-9eE+.,\s-]+")
_DATA_IMAGE_RE = re.compile(
    r"data:image/(?P<subtype>png|jpeg|jpg|gif|webp);base64,"
    r"(?P<data>[A-Za-z0-9+/=\s]+)",
    re.IGNORECASE,
)
_ALIGNMENTS = {"left", "center", "right"}


def escape_text(value: str) -> str:
    """HTML 텍스트 노드용 이스케이프."""
    return html.escape(value, quote=False)


def escape_attr(value: str) -> str:
    """큰따옴표 HTML 속성값용 이스케이프."""
    return html.escape(value, quote=True)


def safe_href(value: str) -> str | None:
    """클릭 가능한 링크로 허용된 URL만 반환한다."""
    if any(char in value for char in "<>") or any(ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https", "mailto"}:
        return None
    return value.strip()


def safe_image_src(value: str) -> str | None:
    """프로젝트 상대경로 및 명시적으로 허용한 이미지 URL만 반환한다."""
    candidate = value.strip()
    if not candidate:
        return None
    if any(char in candidate for char in "<>") or any(
        ord(char) < 32 for char in candidate
    ):
        return None
    data_match = _DATA_IMAGE_RE.fullmatch(candidate)
    if data_match:
        normalized = safe_base64_data(data_match.group("data"))
        if normalized is None:
            return None
        return f"data:image/{data_match.group('subtype').lower()};base64,{normalized}"
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme.lower() in {"http", "https"}:
        return candidate
    if parsed.scheme or parsed.netloc or candidate.startswith(("/", "\\")):
        return None
    decoded_path = parsed.path
    for _ in range(4):
        next_path = unquote(decoded_path)
        if next_path == decoded_path:
            break
        decoded_path = next_path
    if any(ord(char) < 32 for char in decoded_path):
        return None
    decoded_path = decoded_path.replace("\\", "/")
    if decoded_path.startswith("/"):
        return None
    parts = [part for part in decoded_path.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None
    normalized = posixpath.normpath(decoded_path)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        return None
    return candidate


def safe_number(value: Any, fallback: float = 0.0) -> float:
    """렌더링에 사용할 유한한 숫자만 반환한다."""
    if isinstance(value, bool):
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return number if math.isfinite(number) else fallback


def css_number(value: Any, fallback: float = 0.0) -> str:
    """유한 숫자를 CSS/SVG에 안전한 10진 문자열로 직렬화한다."""
    number = safe_number(value, fallback)
    if number == 0:
        return "0"
    return format(number, ".15g")


def safe_base64_data(value: str) -> str | None:
    """base64를 엄격히 검증하고 공백 없는 표준 인코딩으로 정규화한다."""
    compact = "".join(value.split())
    if not compact:
        return None
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error):
        return None
    if not decoded:
        return None
    return base64.b64encode(decoded).decode("ascii")


def safe_color(value: str | None, fallback: str = "") -> str:
    """CSS color 문법의 제한된 부분집합만 허용한다."""
    if value is None:
        return fallback
    candidate = value.strip()
    return candidate if _COLOR_RE.fullmatch(candidate) else fallback


def safe_alignment(value: str | None) -> str | None:
    """문단 정렬에 허용된 CSS 식별자만 반환한다."""
    return value if value in _ALIGNMENTS else None


def safe_svg_path(value: str) -> tuple[float, float, str] | None:
    """커스텀 SVG의 viewBox 크기와 path data를 검증한다."""
    parts = value.split(" ", 2)
    if len(parts) != 3:
        return None
    try:
        width = float(parts[0])
        height = float(parts[1])
    except ValueError:
        return None
    path_data = parts[2].strip()
    if (
        not math.isfinite(width)
        or not math.isfinite(height)
        or width <= 0
        or height <= 0
        or not _SVG_PATH_RE.fullmatch(path_data)
    ):
        return None
    return width, height, path_data


def css_url(value: str) -> str:
    """검증된 URL을 속성 구분자를 포함하지 않는 CSS url() 값으로 만든다."""
    encoded = quote(
        value.replace("\r", "").replace("\n", ""),
        safe="/:;,@&=+$-_.!~*%?#[]",
    )
    return f"url({encoded})"
