"""DESIGN.md — 사람이 편집하는 디자인 의도 단일 소스의 파서/직렬화.

DESIGN.md 는 네 영역으로 구성된 구조화 마크다운이다:

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

    ## AI Slop 방지 원칙
    - subject_specificity: ...
    - visual_hierarchy: ...
    - layout_rhythm: ...
    - decoration_policy: ...
    - content_grounding: ...

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
_SECTION_ANTI_SLOP = "anti_slop"
_SECTION_PAGES = "pages"

_SECTION_ALIASES: dict[str, str] = {
    "전역 디자인 시스템": _SECTION_SYSTEM,
    "design system": _SECTION_SYSTEM,
    "global design system": _SECTION_SYSTEM,
    "톤 & 방향": _SECTION_TONE,
    "톤 및 방향": _SECTION_TONE,
    "tone & direction": _SECTION_TONE,
    "tone": _SECTION_TONE,
    "ai slop 방지 원칙": _SECTION_ANTI_SLOP,
    "ai slop guardrails": _SECTION_ANTI_SLOP,
    "anti-slop guardrails": _SECTION_ANTI_SLOP,
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
    anti_slop: str = ""
    page_requests: list[PageRequest] = field(default_factory=list)

    def warn_unbound_requests(self, slide_titles: list[str]) -> None:
        """어느 페이지에도 적용할 수 없는 수동 요청을 조용히 버리지 않는다."""
        normalized = [_normalize_title(title) for title in slide_titles]
        for request in self.page_requests:
            norm = _normalize_title(request.title)
            index = (request.number or 0) - 1
            exact = 0 <= index < len(slide_titles) and (
                not request.title.strip() or normalized[index] == norm
            )
            if not exact and (not norm or normalized.count(norm) != 1):
                logger.warning(
                    "DESIGN.md: unbound or ambiguous page request %r (%s)",
                    request.title,
                    request.number,
                )

    def directives_for(
        self, slide_index: int, title: str, *, slide_titles: list[str] | None = None
    ) -> str:
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
        if self.anti_slop.strip():
            parts.append(
                "<anti_slop_guardrails>\n"
                "Use these deck-specific guardrails to avoid generic AI-generated design:\n"
                f"{self.anti_slop.strip()}\n"
                "</anti_slop_guardrails>"
            )
        req = match_page_request(
            self.page_requests, slide_index, title, slide_titles=slide_titles
        )
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


def remap_page_request_numbers(text: str, positions: dict[int, int]) -> str:
    """슬라이드 이동에 따라 페이지 요청 번호만 바꾸고 사람이 쓴 산문을 보존한다.

    알려진 페이지 요청 섹션의 번호만 수정한다. 코드 블록과 다른 섹션은 건드리지 않는다.
    """
    output: list[str] = []
    section: str | None = None
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            output.append(line)
            continue
        if fence is None:
            heading = re.match(r"^\s*##\s+(.*?)\s*$", line)
            if heading:
                section = _SECTION_ALIASES.get(heading.group(1).strip().lower())
            if section == _SECTION_PAGES:
                match = re.match(r"^\s*###\s+(\d+)(?=\s*[.):\-])", line)
                if match and int(match.group(1)) in positions:
                    old = match.group(1)
                    new = str(positions[int(old)])
                    if old.startswith("0"):
                        new = new.zfill(len(old))
                    line = line[: match.start(1)] + new + line[match.end(1) :]
        output.append(line)
    return "".join(output)


def match_page_request(
    requests: list[PageRequest],
    slide_index: int,
    title: str,
    *,
    slide_titles: list[str] | None = None,
) -> PageRequest | None:
    """이동한 페이지의 의도가 다른 슬라이드에 적용되지 않도록 매칭한다.

    번호와 제목이 맞는 요청을 우선하고 제목 없는 번호 전용 요청도 허용한다.
    제목 보정은 후보와 덱 내 대상이 유일할 때만 사용하며 모호함은 경고한다.
    """
    norm = _normalize_title(title)
    exact = [
        req
        for req in requests
        if req.number == slide_index
        and (not req.title.strip() or _normalize_title(req.title) == norm)
    ]
    candidates = exact or [
        req for req in requests if norm and _normalize_title(req.title) == norm
    ]
    if not exact and candidates and slide_titles is not None:
        if sum(_normalize_title(value) == norm for value in slide_titles) != 1:
            logger.warning(
                "DESIGN.md: ambiguous page title %r; request not applied", title
            )
            return None
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        logger.warning(
            "DESIGN.md: ambiguous page requests for slide %d (%s)", slide_index, title
        )
    elif any(req.number == slide_index for req in requests):
        logger.warning(
            "DESIGN.md: no matching page request for slide %d (%s)", slide_index, title
        )
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
    anti_slop_lines: list[str] = []
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
        elif section == _SECTION_ANTI_SLOP:
            anti_slop_lines.append(raw)
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
    doc.anti_slop = _strip_prose(anti_slop_lines)
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
    anti_slop: str = "",
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
    lines.append("## AI Slop 방지 원칙")
    if anti_slop.strip():
        lines.append(anti_slop.strip())
    else:
        lines.append(
            "<!-- 주제 고유성, 정보 위계, 레이아웃 리듬, 장식 기능, 콘텐츠 근거를 "
            "덱에 맞게 적으세요. -->"
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
