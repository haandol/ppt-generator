"""DESIGN.md — 사람이 편집하는 디자인 의도 단일 소스의 파서/직렬화.

DESIGN.md 는 세 영역으로 구성된 구조화 마크다운이다:

    # DESIGN

    ## 전역 디자인 시스템
    - theme: dark
    - background_color: #0F172A
    - text_colors: #FFFFFF, #E0E0E0
    - title_font_pt: 32
    - body_font_pt: 20
    - card_fills: #1E293B
    - card_borders: #334155
    - header_region: top=64, height=64
    - content_region: top=148, height=508
    - footer_region: top=664, height=24

    ## 톤 & 방향
    (자유 산문 — 색감/격식/청중/여백 등 수치로 안 떨어지는 의도)

    ## 페이지별 요청
    ### 3. 아키텍처 개요
    (해당 슬라이드 자유 산문)

전역 디자인 시스템은 기존 머신 디자인 요약(design_summary dict)과 round-trip 한다.
톤·페이지 요청은 산문 그대로 보존해 생성 프롬프트에 주입한다.

파서는 알려진 섹션/키만 읽고 모르는 것은 무시(폴백)하므로, 사용자가 자유
편집해도 깨지지 않는다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 섹션 헤더 alias (한/영). 정규화된 키로 매핑.
_SECTION_SYSTEM = "system"
_SECTION_TONE = "tone"
_SECTION_PAGES = "pages"

_SECTION_ALIASES: dict[str, str] = {
    "전역 디자인 시스템": _SECTION_SYSTEM,
    "design system": _SECTION_SYSTEM,
    "global design system": _SECTION_SYSTEM,
    "톤 & 방향": _SECTION_TONE,
    "톤 및 방향": _SECTION_TONE,
    "tone & direction": _SECTION_TONE,
    "tone": _SECTION_TONE,
    "페이지별 요청": _SECTION_PAGES,
    "페이지별 특별 요청": _SECTION_PAGES,
    "per-slide requests": _SECTION_PAGES,
    "per slide requests": _SECTION_PAGES,
    "page requests": _SECTION_PAGES,
}

# 전역 디자인 시스템 key alias → design_summary 정식 키.
_KEY_ALIASES: dict[str, str] = {
    "theme": "color_theme",
    "color_theme": "color_theme",
    "background": "background_color",
    "background_color": "background_color",
    "text_colors": "text_colors",
    "title_font_pt": "title_font_pt",
    "body_font_pt": "body_font_pt",
    "card_fills": "card_fills",
    "card_borders": "card_borders",
    "header_region": "header_region",
    "content_region": "content_region",
    "footer_region": "footer_region",
    "background_image": "background_image",
    "title_bg": "background_image",
}

_LIST_KEYS = {"text_colors", "card_fills", "card_borders"}
_INT_KEYS = {"title_font_pt", "body_font_pt"}
_REGION_KEYS = {"header_region", "content_region", "footer_region"}

# 배경 이미지 자동 주입 정책. title/closing 슬라이드 export 시 적용.
#   "gradient" (기본): 테마별 그라데이션 배경 PNG 자동 주입 (design/0010)
#   "none": 자동 주입 끔 — 단색 배경으로 마감
_BG_IMAGE_KEY = "background_image"
_BG_IMAGE_VALUES = {"gradient", "none"}


@dataclass
class PageRequest:
    """페이지별 특별 요청 한 건."""

    number: int | None  # 1-based 슬라이드 번호 (없으면 None)
    title: str  # 슬라이드 제목 (보정 매칭용)
    text: str  # 요청 산문


@dataclass
class DesignDocMd:
    """DESIGN.md 를 파싱한 결과."""

    design_summary: dict = field(default_factory=dict)
    tone: str = ""
    page_requests: list[PageRequest] = field(default_factory=list)

    def directives_for(self, slide_index: int, title: str) -> str:
        """해당 슬라이드(1-based index + 제목)에 적용할 디자인 지시 텍스트를 만든다.

        전역 톤은 모든 슬라이드에, 페이지별 요청은 매칭된 슬라이드에만 붙인다.
        붙일 게 없으면 빈 문자열.
        """
        parts: list[str] = []
        if self.tone.strip():
            parts.append(
                "<design_direction>\n"
                "Apply this overall design direction across the deck:\n"
                f"{self.tone.strip()}\n"
                "</design_direction>"
            )
        req = match_page_request(self.page_requests, slide_index, title)
        if req is not None and req.text.strip():
            parts.append(
                "<slide_specific_request>\n"
                "This specific slide has a special design request — honor it:\n"
                f"{req.text.strip()}\n"
                "</slide_specific_request>"
            )
        return "\n\n".join(parts)


def _normalize_title(title: str) -> str:
    """제목 보정 매칭용 정규화 — 공백/대소문자/문장부호 차이를 흡수."""
    return re.sub(r"[\s\W]+", "", title or "").lower()


def match_page_request(
    requests: list[PageRequest], slide_index: int, title: str
) -> PageRequest | None:
    """페이지 요청을 슬라이드에 매칭한다 (번호 1차 → 제목 보정 → 실패).

    Args:
        requests: 파싱된 페이지 요청 목록
        slide_index: 1-based 슬라이드 번호
        title: 슬라이드 제목
    """
    # 1) 번호 매칭
    for req in requests:
        if req.number is not None and req.number == slide_index:
            return req
    # 2) 제목 보정 매칭
    norm = _normalize_title(title)
    if norm:
        for req in requests:
            if req.title and _normalize_title(req.title) == norm:
                return req
    return None


# --------------------------------------------------------------------------
# 파싱
# --------------------------------------------------------------------------


def parse_design_doc_md(text: str) -> DesignDocMd:
    """DESIGN.md 문자열을 DesignDocMd 로 파싱한다.

    알려진 섹션/키만 읽고 나머지는 무시한다. 파싱 중 예외가 나도
    가능한 부분만 채워 반환한다 (사용자 자유 편집 견고성).
    """
    doc = DesignDocMd()
    if not text or not text.strip():
        return doc

    # ## 헤더로 섹션 분할
    section = None
    system_lines: list[str] = []
    tone_lines: list[str] = []
    page_blocks: list[tuple[int | None, str, list[str]]] = []
    cur_page: tuple[int | None, str, list[str]] | None = None

    for raw in text.splitlines():
        h2 = re.match(r"^\s*##\s+(.*?)\s*$", raw)
        if h2 and not raw.lstrip().startswith("###"):
            name = h2.group(1).strip().lower()
            section = _SECTION_ALIASES.get(name)
            cur_page = None
            continue

        if section == _SECTION_SYSTEM:
            system_lines.append(raw)
        elif section == _SECTION_TONE:
            tone_lines.append(raw)
        elif section == _SECTION_PAGES:
            h3 = re.match(r"^\s*###\s+(.*?)\s*$", raw)
            if h3:
                number, title = _parse_page_header(h3.group(1).strip())
                cur_page = (number, title, [])
                page_blocks.append(cur_page)
            elif cur_page is not None:
                cur_page[2].append(raw)

    doc.design_summary = _parse_system_lines(system_lines)
    doc.tone = _strip_prose(tone_lines)
    doc.page_requests = [
        PageRequest(number=n, title=t, text=_strip_prose(body))
        for (n, t, body) in page_blocks
    ]
    return doc


def _strip_prose(lines: list[str]) -> str:
    """산문 블록에서 HTML 주석(placeholder 힌트) 라인을 제거하고 정리한다.

    초안의 `<!-- ... -->` 안내 문구가 톤/요청 텍스트로 오인되지 않게 한다.
    """
    text = "\n".join(lines)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text.strip()


def _parse_page_header(header: str) -> tuple[int | None, str]:
    """'3. 아키텍처 개요' → (3, '아키텍처 개요'). 번호 없으면 (None, header)."""
    m = re.match(r"^(\d+)\s*[.):\-]\s*(.*)$", header)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return None, header


def _parse_system_lines(lines: list[str]) -> dict:
    """전역 디자인 시스템 bullet 라인을 design_summary dict 로 파싱한다."""
    summary: dict = {}
    for raw in lines:
        # "- key: value" 또는 "key: value"
        m = re.match(r"^\s*[-*]?\s*([\w &]+?)\s*:\s*(.+?)\s*$", raw)
        if not m:
            continue
        raw_key = m.group(1).strip().lower()
        value = m.group(2).strip()
        key = _KEY_ALIASES.get(raw_key)
        if key is None:
            continue  # 모르는 키는 무시
        try:
            summary[key] = _coerce_value(key, value)
        except Exception:
            logger.warning("DESIGN.md: '%s' 값 파싱 실패, 무시: %r", raw_key, value)
    return summary


def _coerce_value(key: str, value: str):
    if key in _LIST_KEYS:
        return [v.strip() for v in value.split(",") if v.strip()]
    if key in _INT_KEYS:
        return int(re.sub(r"[^\d-]", "", value))
    if key in _REGION_KEYS:
        return _parse_region(value)
    if key == _BG_IMAGE_KEY:
        # 값 뒤에 인라인 주석(예: "none  (gradient=...)")이 붙어도 첫 토큰만 취한다.
        m = re.match(r"\s*([a-zA-Z_]+)", value)
        v = m.group(1).lower() if m else ""
        return v if v in _BG_IMAGE_VALUES else "gradient"
    return value


def _parse_region(value: str) -> dict:
    """'top=64, height=64' → {'top_px': 64, 'height_px': 64}."""
    region: dict = {}
    for part in re.split(r"[,;]", value):
        kv = re.match(r"\s*(\w+)\s*=\s*(-?\d+)\s*", part)
        if not kv:
            continue
        name = kv.group(1).lower()
        num = int(kv.group(2))
        if name in ("top", "top_px"):
            region["top_px"] = num
        elif name in ("height", "height_px"):
            region["height_px"] = num
    return region


# --------------------------------------------------------------------------
# 직렬화 (초안 생성)
# --------------------------------------------------------------------------


def render_design_doc_md(
    design_summary: dict,
    *,
    tone: str = "",
    page_requests: list[PageRequest] | None = None,
) -> str:
    """design_summary(+선택적 톤/페이지요청)를 DESIGN.md 문자열로 직렬화한다.

    초안 생성에 쓰인다. design_summary 의 정식 키를 그대로 출력하므로
    parse_design_doc_md 와 round-trip 한다.
    """
    lines: list[str] = ["# DESIGN", "", "## 전역 디자인 시스템"]
    lines.extend(_render_system_lines(design_summary))
    lines.append("")
    lines.append("## 톤 & 방향")
    if tone.strip():
        lines.append(tone.strip())
    else:
        lines.append(
            "<!-- 색감·격식·청중·여백 등 디자인 의도를 자유롭게 적으세요. "
            "예: 차분한 기업 톤, 임원 대상이라 여백을 넉넉히. -->"
        )
    lines.append("")
    lines.append("## 페이지별 요청")
    if page_requests:
        for req in page_requests:
            head = (
                f"### {req.number}. {req.title}"
                if req.number is not None
                else f"### {req.title}"
            )
            lines.append(head)
            if req.text.strip():
                lines.append(req.text.strip())
            lines.append("")
    else:
        lines.append(
            "<!-- 특정 슬라이드에만 적용할 요청을 '### 번호. 제목' 아래에 적으세요. "
            "예: ### 3. 아키텍처 개요 → 좌우 비교 레이아웃으로. -->"
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_system_lines(summary: dict) -> list[str]:
    """design_summary dict 를 '- key: value' bullet 라인으로 직렬화한다."""
    # 사람이 읽기 좋은 순서로 출력
    order = [
        "color_theme",
        "background_color",
        "background_image",
        "text_colors",
        "title_font_pt",
        "body_font_pt",
        "card_fills",
        "card_borders",
        "header_region",
        "content_region",
        "footer_region",
    ]
    out: list[str] = []
    for key in order:
        if key == _BG_IMAGE_KEY:
            # 배경 정책은 항상 노출해 사용자가 끌 수 있게 한다 (기본 gradient).
            val = summary.get(_BG_IMAGE_KEY) or "gradient"
            out.append(
                f"- {key}: {val}  (gradient=테마 그라데이션 배경 자동 / none=단색 배경)"
            )
            continue
        if key not in summary or summary[key] in (None, [], {}):
            continue
        out.append(f"- {key}: {_render_value(key, summary[key])}")
    return out


def _render_value(key: str, value) -> str:
    if key in _LIST_KEYS and isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if key in _REGION_KEYS and isinstance(value, dict):
        parts = []
        if "top_px" in value:
            parts.append(f"top={value['top_px']}")
        if "height_px" in value:
            parts.append(f"height={value['height_px']}")
        return ", ".join(parts)
    return str(value)
