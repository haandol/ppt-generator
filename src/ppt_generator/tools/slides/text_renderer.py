"""PptxTextRun/PptxParagraph -> HTML 변환 렌더러.

텍스트 런, 문단의 HTML 렌더링 기본 함수를 제공한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxParagraph, PptxTextRun
from ppt_generator.tools.slides.html_safety import (
    css_number,
    escape_attr,
    escape_text,
    safe_alignment,
    safe_color,
    safe_href,
    safe_number,
)


def escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return escape_text(text)


# PowerPoint 기본 탭 stop = 1인치 = 96px(@96dpi). 코드블록 등 탭 들여쓰기 렌더에 사용.
_TAB_STOP_PX = 96.0


# 폰트 서브패밀리(굵기/폭/광학 크기) 접미사. "Amazon Ember Display" 처럼 서브패밀리
# 이름이 붙은 폰트는 종종 설치돼 있지 않지만(예: "Amazon Ember" 만 설치), 접미사를
# 뗀 베이스 패밀리는 설치돼 있는 경우가 많다. 폴백 체인에 베이스명을 끼워 넣으면
# sans-serif 로 떨어지기 전에 같은 계열로 렌더돼 글자 폭/줄바꿈이 원본에 가까워진다.
_FONT_SUBFAMILY_SUFFIXES = (
    "display",
    "text",
    "heading",
    "caption",
    "subhead",
    "thin",
    "extralight",
    "ultralight",
    "light",
    "regular",
    "medium",
    "semibold",
    "demibold",
    "bold",
    "extrabold",
    "black",
    "heavy",
    "condensed",
    "narrow",
    "extended",
)


def _base_family_names(font_name: str) -> list[str]:
    """폰트명에서 서브패밀리 접미사를 순차적으로 떼어낸 베이스 패밀리 후보들.

    예) "Amazon Ember Display" → ["Amazon Ember"]
        "Amazon Ember Condensed Light" → ["Amazon Ember Condensed", "Amazon Ember"]
    원본명 자체는 포함하지 않는다(호출부에서 맨 앞에 이미 넣으므로).
    """
    tokens = font_name.split()
    candidates: list[str] = []
    while len(tokens) > 1 and tokens[-1].lower() in _FONT_SUBFAMILY_SUFFIXES:
        tokens = tokens[:-1]
        candidates.append(" ".join(tokens))
    return candidates


def run_to_html(run: PptxTextRun, *, font_scale: float = 1.0) -> str:
    """PptxTextRun -> <span> 변환.

    font_scale 이 1.0 미만이면 shrink_text autofit 으로 폰트를 비례 축소한다.
    """
    styles: list[str] = []
    size_pt = safe_number(run.font_size_pt)
    scale = safe_number(font_scale, 1.0)
    if size_pt > 0:
        size_pt = size_pt * scale if 0 < scale < 1.0 else size_pt
        styles.append(f"font-size:{size_pt:.2f}pt")
    if run.color:
        color = safe_color(run.color)
        if color:
            styles.append(f"color:{color}")
    if run.bold:
        styles.append("font-weight:bold")
    if run.italic:
        styles.append("font-style:italic")
    if run.font_family == "monospace":
        styles.append("font-family:'Source Code Pro',Consolas,'Courier New',monospace")
    elif getattr(run, "font_name", None):
        # 원본 폰트명 보존 + 안전한 fallback 체인. 폰트가 설치/웹폰트로 있으면 원본과
        # 동일하게 렌더된다. 서브패밀리명("Amazon Ember Display" 등)이 미설치일 때를
        # 대비해 베이스 패밀리명("Amazon Ember")을 sans-serif 앞에 끼워 넣어, 폰트
        # 폴백으로 글자 폭이 달라져 줄바꿈이 어긋나는 것을 최소화한다.
        safe_name = run.font_name.replace("'", "").replace('"', "")
        family_chain = [f"'{safe_name}'"]
        for base in _base_family_names(safe_name):
            family_chain.append(f"'{base}'")
        family_chain += [
            "'Noto Sans KR'",
            "'Malgun Gothic'",
            "'Apple SD Gothic Neo'",
            "sans-serif",
        ]
        styles.append("font-family:" + ",".join(family_chain))

    # run.text 내 개행(\n)은 PPTX 의 <a:br>(문단 내 소프트 줄바꿈)에서 유래한다.
    # HTML 에서는 개행이 공백으로 접히므로 명시적 <br> 로 변환해 줄바꿈을 보존한다.
    # 탭/연속 공백(코드 블록 들여쓰기 등)도 HTML 에서 접히므로 보존한다.
    # 탭(\t)은 PowerPoint 기본 탭 stop(1인치=96px)만큼 들여쓴다. 예전엔 &nbsp;×4
    # (약 20px)로 대체해 원본 대비 들여쓰기가 크게 부족했고, 절대 배치된 도형(예:
    # 코드블록 위 강조 박스)과 텍스트가 어긋났다(slide13). 정확한 탭 stop 누적 정렬은
    # 불가하지만, 탭 1개=1인치 고정 spacer 가 PPT 기본 동작에 가장 근접한다.
    tab_px = _TAB_STOP_PX * (font_scale if 0 < font_scale < 1.0 else 1.0)
    tab_span = f'<span style="display:inline-block;width:{tab_px:.1f}px"></span>'

    def _preserve_ws(part: str) -> str:
        escaped = escape_html(part)
        escaped = escaped.replace("\t", tab_span)
        # 연속된 공백 2개 이상은 첫 칸만 일반 공백, 나머지는 &nbsp; (줄바꿈 지점 유지)
        escaped = escaped.replace("  ", " &nbsp;")
        return escaped

    text = "<br>".join(_preserve_ws(part) for part in run.text.split("\n"))
    if styles:
        inner = f'<span style="{";".join(styles)}">{text}</span>'
    else:
        inner = text
    if run.href:
        href = safe_href(run.href)
        if href is not None:
            return (
                f'<a href="{escape_attr(href)}" target="_blank" '
                'rel="noopener noreferrer" '
                f'style="color:inherit;text-decoration:underline">{inner}</a>'
            )
    return inner


def paragraph_to_html(
    para: PptxParagraph,
    *,
    nowrap: bool = False,
    font_scale: float = 1.0,
    line_height_pt: float | None = None,
) -> str:
    """PptxParagraph -> HTML 변환.

    nowrap=True 이면 white-space:nowrap을 적용하여 PPT의 한 줄 레이아웃을 유지한다.
    font_scale 이 1.0 미만이면 모든 run 의 폰트를 비례 축소한다 (shrink_text autofit).
    line_height_pt 가 주어지면 <p>/<li> 에 직접 line-height 를 적용한다 — 전역 CSS
    `p{line-height:1.5}` 가 컨테이너 상속을 덮어쓰는 것을 막기 위함이다 (import/0003).
    """
    runs_html = "".join(run_to_html(r, font_scale=font_scale) for r in para.runs)
    style_props: list[str] = []
    alignment = safe_alignment(para.alignment)
    if alignment:
        style_props.append(f"text-align:{alignment}")
    if nowrap:
        style_props.append("white-space:nowrap")
    if line_height_pt and line_height_pt > 0:
        style_props.append(f"line-height:{css_number(line_height_pt)}pt")

    style_attr = f' style="{";".join(style_props)}"' if style_props else ""

    bullet_level = safe_number(para.bullet_level, -1)
    if bullet_level >= 0:
        indent = 20 * (int(bullet_level) + 1)
        li_styles = [f"margin-left:{css_number(indent)}px"]
        if alignment:
            li_styles.append(f"text-align:{alignment}")
        if nowrap:
            li_styles.append("white-space:nowrap")
        if line_height_pt and line_height_pt > 0:
            li_styles.append(f"line-height:{css_number(line_height_pt)}pt")
        return f'<li style="{";".join(li_styles)}">{runs_html}</li>'
    return f"<p{style_attr}>{runs_html}</p>"
