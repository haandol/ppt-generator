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
        # 동일하게, 없으면 sans-serif 계열로 대체된다.
        safe_name = run.font_name.replace("'", "").replace('"', "")
        styles.append(
            f"font-family:'{safe_name}','Noto Sans KR','Malgun Gothic',"
            "'Apple SD Gothic Neo',sans-serif"
        )

    # run.text 내 개행(\n)은 PPTX 의 <a:br>(문단 내 소프트 줄바꿈)에서 유래한다.
    # HTML 에서는 개행이 공백으로 접히므로 명시적 <br> 로 변환해 줄바꿈을 보존한다.
    # 탭/연속 공백(코드 블록 들여쓰기 등)도 HTML 에서 접히므로 &nbsp; 로 보존한다.
    def _preserve_ws(part: str) -> str:
        escaped = escape_html(part)
        escaped = escaped.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")
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
    para: PptxParagraph, *, nowrap: bool = False, font_scale: float = 1.0
) -> str:
    """PptxParagraph -> HTML 변환.

    nowrap=True 이면 white-space:nowrap을 적용하여 PPT의 한 줄 레이아웃을 유지한다.
    font_scale 이 1.0 미만이면 모든 run 의 폰트를 비례 축소한다 (shrink_text autofit).
    """
    runs_html = "".join(run_to_html(r, font_scale=font_scale) for r in para.runs)
    style_props: list[str] = []
    alignment = safe_alignment(para.alignment)
    if alignment:
        style_props.append(f"text-align:{alignment}")
    if nowrap:
        style_props.append("white-space:nowrap")

    style_attr = f' style="{";".join(style_props)}"' if style_props else ""

    bullet_level = safe_number(para.bullet_level, -1)
    if bullet_level >= 0:
        indent = 20 * (int(bullet_level) + 1)
        li_styles = [f"margin-left:{css_number(indent)}px"]
        if alignment:
            li_styles.append(f"text-align:{alignment}")
        if nowrap:
            li_styles.append("white-space:nowrap")
        return f'<li style="{";".join(li_styles)}">{runs_html}</li>'
    return f"<p{style_attr}>{runs_html}</p>"
