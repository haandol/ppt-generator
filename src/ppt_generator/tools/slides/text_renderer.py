"""PptxTextRun/PptxParagraph -> HTML 변환 렌더러.

텍스트 런, 문단의 HTML 렌더링 기본 함수를 제공한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxParagraph, PptxTextRun


def escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def run_to_html(run: PptxTextRun) -> str:
    """PptxTextRun -> <span> 변환."""
    styles: list[str] = []
    if run.font_size_pt:
        styles.append(f"font-size:{run.font_size_pt}pt")
    if run.color:
        styles.append(f"color:{run.color}")
    if run.bold:
        styles.append("font-weight:bold")
    if run.italic:
        styles.append("font-style:italic")
    if run.font_family == "monospace":
        styles.append("font-family:'Source Code Pro',Consolas,'Courier New',monospace")

    text = escape_html(run.text)
    if styles:
        inner = f'<span style="{";".join(styles)}">{text}</span>'
    else:
        inner = text
    if run.href:
        href = escape_html(run.href)
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline">{inner}</a>'
    return inner


def paragraph_to_html(para: PptxParagraph, *, nowrap: bool = False) -> str:
    """PptxParagraph -> HTML 변환.

    nowrap=True 이면 white-space:nowrap을 적용하여 PPT의 한 줄 레이아웃을 유지한다.
    """
    runs_html = "".join(run_to_html(r) for r in para.runs)
    style_props: list[str] = []
    if para.alignment:
        style_props.append(f"text-align:{para.alignment}")
    if nowrap:
        style_props.append("white-space:nowrap")

    style_attr = f' style="{";".join(style_props)}"' if style_props else ""

    if para.bullet_level >= 0:
        indent = 20 * (para.bullet_level + 1)
        li_styles = [f"margin-left:{indent}px"]
        if para.alignment:
            li_styles.append(f"text-align:{para.alignment}")
        if nowrap:
            li_styles.append("white-space:nowrap")
        return f'<li style="{";".join(li_styles)}">{runs_html}</li>'
    return f"<p{style_attr}>{runs_html}</p>"
