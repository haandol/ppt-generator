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
        return f'<span style="{";".join(styles)}">{text}</span>'
    return text


def paragraph_to_html(para: PptxParagraph) -> str:
    """PptxParagraph -> HTML 변환."""
    runs_html = "".join(run_to_html(r) for r in para.runs)
    align_style = ""
    if para.alignment:
        align_style = f' style="text-align:{para.alignment}"'

    if para.bullet_level >= 0:
        indent = 20 * (para.bullet_level + 1)
        return f'<li style="margin-left:{indent}px{(";text-align:" + para.alignment) if para.alignment else ""}">{runs_html}</li>'
    return f"<p{align_style}>{runs_html}</p>"
