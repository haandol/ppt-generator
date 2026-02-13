from __future__ import annotations

import json
import logging
import re
import uuid

from strands import Agent

from bs4 import BeautifulSoup

from ppt_generator.interfaces.constants import (
    SLIDES_TEMPLATE_PATH,
    SLIDES_DESIGN_SUMMARY_PROMPT,
    SLIDES_MAX_PER_BATCH,
    SLIDES_MODIFY_SINGLE_USER_PROMPT_TEMPLATE,
    SLIDES_MODIFY_USER_PROMPT_TEMPLATE,
    SLIDES_USER_PROMPT_TEMPLATE,
    SLIDES_BATCH_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
    SlidesResponse,
    SlideOutline,
)

logger = logging.getLogger(__name__)


class SlidesService:
    def __init__(self, agent: Agent, modify_agent: Agent) -> None:
        self._agent = agent
        self._modify_agent = modify_agent
        self._sessions: dict[str, str] = {}

    def generate(self, slides: list[SlideOutline]) -> SlidesResponse:
        if not slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        if len(slides) <= SLIDES_MAX_PER_BATCH:
            html = self._generate_single(slides)
        else:
            html = self._generate_batched(slides)

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = html

        logger.info("HTML 슬라이드 생성 완료: session_id=%s, 슬라이드 수=%d", session_id, len(slides))
        return SlidesResponse(session_id=session_id, html=html)

    def generate_from_design_spec(self, design_spec: DesignSpec) -> SlidesResponse:
        """DesignSpec(PptxSlideSpec 리스트)을 결정론적으로 HTML로 변환한다.

        LLM 호출 없이 PptxSlideSpec → position:absolute HTML div로 변환.
        """
        if not design_spec.slides:
            raise ValueError("디자인 스펙에 슬라이드가 없습니다.")

        sections: list[str] = []
        for idx, spec in enumerate(design_spec.slides):
            section_html = self._spec_to_html_section(idx, spec)
            sections.append(section_html)

        combined = "\n".join(sections)
        html = self._wrap_with_template(combined)

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = html

        logger.info(
            "Design Spec → HTML 변환 완료: session_id=%s, 슬라이드 수=%d",
            session_id, len(design_spec.slides),
        )
        return SlidesResponse(session_id=session_id, html=html)

    @staticmethod
    def _spec_to_html_section(slide_index: int, spec: PptxSlideSpec) -> str:
        """PptxSlideSpec 하나를 <section> HTML로 결정론적 변환."""
        bg = spec.background_color or "#1a1a2e"
        notes_attr = ""
        if spec.speaker_notes:
            escaped_notes = spec.speaker_notes.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
            notes_attr = f' data-speaker-notes="{escaped_notes}"'

        parts: list[str] = []
        parts.append(
            f'<section id="slide-{slide_index}"{notes_attr}>'
            f'<div style="position:absolute;top:0;left:0;right:0;bottom:0;'
            f'background-color:{bg};overflow:hidden;">'
        )

        # shapes를 먼저 렌더링 (z-order 하단)
        for shape in spec.shapes:
            parts.append(_shape_to_html(shape))

        # textboxes를 나중에 렌더링 (z-order 상단)
        for tb in spec.textboxes:
            parts.append(_textbox_to_html(tb))

        parts.append("</div></section>")
        return "\n".join(parts)

    def modify(self, session_id: str, modification_request: str, slide_index: int = -1) -> SlidesResponse:
        if not modification_request.strip():
            raise ValueError("수정 요청이 비어있습니다.")
        current_html = self.get_session_html(session_id)

        if slide_index >= 0:
            html = self._modify_single_slide(current_html, slide_index, modification_request)
        else:
            prompt = SLIDES_MODIFY_USER_PROMPT_TEMPLATE.format(
                current_html=current_html,
                modification_request=modification_request,
            )
            result = str(self._modify_agent(prompt))
            html = self._extract_full_html(result)

        self._sessions[session_id] = html
        return SlidesResponse(session_id=session_id, html=html)

    def _modify_single_slide(self, full_html: str, slide_index: int, modification_request: str) -> str:
        soup = BeautifulSoup(full_html, "html.parser")
        slides_container = soup.find("body")
        if slides_container is None:
            raise ValueError("HTML body를 찾을 수 없습니다.")

        sections = slides_container.find_all("section", recursive=False)
        if slide_index >= len(sections):
            raise IndexError(f"슬라이드 인덱스 범위 초과: {slide_index} (총 {len(sections)}장)")

        target_html = str(sections[slide_index])
        prompt = SLIDES_MODIFY_SINGLE_USER_PROMPT_TEMPLATE.format(
            slide_index=slide_index,
            current_slide_html=target_html,
            modification_request=modification_request,
        )
        result = str(self._modify_agent(prompt))
        modified_section_html = self._extract_sections(result)

        modified_section = BeautifulSoup(modified_section_html, "html.parser").find("section")
        if modified_section is None:
            raise ValueError("수정된 슬라이드 section을 파싱할 수 없습니다.")

        sections[slide_index].replace_with(modified_section)
        return str(soup)

    def get_session_html(self, session_id: str) -> str:
        html = self._sessions.get(session_id)
        if html is None:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")
        return html

    def update_session_html(self, session_id: str, html: str) -> None:
        if session_id not in self._sessions:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")
        self._sessions[session_id] = html

    # --- 생성 내부 메서드 ---

    def _generate_single(self, slides: list[SlideOutline], start_index: int = 0) -> str:
        all_sections: list[str] = []
        for i, slide in enumerate(slides):
            outline_json = json.dumps(
                {"slides": [self._slide_to_dict(slide)]},
                ensure_ascii=False,
                indent=2,
            )

            prompt = SLIDES_USER_PROMPT_TEMPLATE.format(
                outline_json=outline_json,
            )
            result = str(self._agent(prompt))

            section = self._extract_sections(result)
            all_sections.append(section)

        combined = "\n".join(all_sections)
        html = self._wrap_with_template(combined)
        return html

    def _generate_batched(self, slides: list[SlideOutline]) -> str:
        chunks = self._chunk_slides(slides, SLIDES_MAX_PER_BATCH)

        # 첫 배치: 전체 HTML 문서 생성
        first_chunk = chunks[0]
        first_html = self._generate_single(first_chunk)

        if len(chunks) == 1:
            return first_html

        # 디자인 요약 추출
        design_summary = self._extract_design_summary(first_html)

        # 후속 배치: 슬라이드 div만 생성
        continuation_divs: list[str] = []
        offset = len(first_chunk)
        for chunk in chunks[1:]:
            divs = self._generate_continuation_batch(chunk, design_summary, offset)
            continuation_divs.append(divs)
            offset += len(chunk)

        return self._combine_html_batches(first_html, continuation_divs)

    def _extract_design_summary(self, html: str) -> str:
        prompt = SLIDES_DESIGN_SUMMARY_PROMPT.format(html=html)
        result = str(self._agent(prompt))
        return result.strip()

    def _generate_continuation_batch(
        self,
        slides: list[SlideOutline],
        design_summary: str,
        offset: int,
    ) -> str:
        all_sections: list[str] = []
        for i, slide in enumerate(slides):
            outline_json = json.dumps(
                {"slides": [self._slide_to_dict(slide)]},
                ensure_ascii=False,
                indent=2,
            )

            prompt = SLIDES_BATCH_USER_PROMPT_TEMPLATE.format(
                design_summary=design_summary,
                outline_json=outline_json,
            )
            result = str(self._agent(prompt))

            section = self._extract_sections(result)
            all_sections.append(section)

        return "\n".join(all_sections)

    @staticmethod
    def _chunk_slides(slides: list[SlideOutline], chunk_size: int) -> list[list[SlideOutline]]:
        return [slides[i : i + chunk_size] for i in range(0, len(slides), chunk_size)]

    @staticmethod
    def _combine_html_batches(first_html: str, continuation_sections: list[str]) -> str:
        insertion = "\n".join(continuation_sections)
        # <script> 태그 앞에 새 section들을 삽입 (IIFE가 모든 section을 인식하도록)
        soup = BeautifulSoup(first_html, "html.parser")
        body = soup.find("body")
        if body:
            new_sections = BeautifulSoup(insertion, "html.parser")
            script_tag = body.find("script")
            for section in new_sections.find_all("section", recursive=False):
                if script_tag:
                    script_tag.insert_before(section)
                else:
                    body.append(section)
            return str(soup)
        # 폴백: </body> 앞에 삽입
        match = re.search(r"</body>", first_html, re.IGNORECASE)
        if match:
            pos = match.start()
            return first_html[:pos] + "\n" + insertion + "\n" + first_html[pos:]
        return first_html + "\n" + insertion

    # --- 유틸리티 ---

    @staticmethod
    def _slide_to_dict(slide: SlideOutline) -> dict:
        d = {
            "title": slide.title,
            "content_summary": slide.content_summary,
            "component_hint": slide.component_hint,
        }
        if slide.speaker_notes:
            d["speaker_notes"] = slide.speaker_notes
        return d

    @staticmethod
    def _extract_full_html(text: str) -> str:
        """전체 수정 시 LLM 응답에서 완전한 HTML 문서를 추출."""
        # 1단계: 마크다운 코드블록에서 추출
        code_block = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        # 2단계: <!DOCTYPE html> 또는 <html> 태그로 시작하는 부분 추출
        doctype_match = re.search(r"(<!DOCTYPE html>.*)", text, re.DOTALL | re.IGNORECASE)
        if doctype_match:
            return doctype_match.group(1).strip()

        html_match = re.search(r"(<html[\s>].*)", text, re.DOTALL | re.IGNORECASE)
        if html_match:
            return html_match.group(1).strip()

        # 폴백: 전체 텍스트를 HTML로 간주
        logger.warning("HTML 추출 실패, 원본 텍스트를 그대로 사용합니다.")
        return text.strip()

    @staticmethod
    def _wrap_with_template(sections_html: str) -> str:
        """section 요소들을 HTML 템플릿에 삽입하여 완전한 HTML 문서 생성."""
        template = SLIDES_TEMPLATE_PATH.read_text(encoding="utf-8")
        return template.replace("{slides_content}", sections_html.strip())

    @staticmethod
    def _extract_sections(text: str) -> str:
        """LLM 응답에서 <section> 요소들을 추출."""
        # 1단계: 마크다운 코드블록에서 추출
        code_block = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        # 2단계: 완전한 HTML 문서가 반환된 경우 section들만 추출
        if "<!DOCTYPE html>" in text.lower() or "<html" in text.lower():
            soup = BeautifulSoup(text, "html.parser")
            sections = soup.find_all("section")
            if sections:
                return "\n".join(str(s) for s in sections)

        # 3단계: <section> 태그가 있으면 section만 추출
        if "<section" in text:
            parts: list[str] = []
            for section_match in re.finditer(r"(<section[\s>].*?</section>)", text, re.DOTALL):
                parts.append(section_match.group(0))
            if parts:
                return "\n".join(parts)

        # 폴백: 전체 텍스트를 반환
        logger.warning("section 추출 실패, 원본 텍스트를 그대로 사용합니다.")
        return text.strip()


# ---------------------------------------------------------------------------
# PptxSlideSpec → HTML 변환 헬퍼 (모듈 수준)
# ---------------------------------------------------------------------------

def _escape_html(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run_to_html(run: PptxTextRun) -> str:
    """PptxTextRun → <span> 변환."""
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
        styles.append("font-family:'Roboto Mono',monospace")

    text = _escape_html(run.text)
    if styles:
        return f'<span style="{";".join(styles)}">{text}</span>'
    return text


def _paragraph_to_html(para: PptxParagraph) -> str:
    """PptxParagraph → HTML 변환."""
    runs_html = "".join(_run_to_html(r) for r in para.runs)
    align_style = ""
    if para.alignment:
        align_style = f" style=\"text-align:{para.alignment}\""

    if para.bullet_level >= 0:
        indent = 20 * (para.bullet_level + 1)
        return f'<li style="margin-left:{indent}px{(";text-align:" + para.alignment) if para.alignment else ""}">{runs_html}</li>'
    return f"<p{align_style}>{runs_html}</p>"


def _textbox_to_html(tb: PptxTextBox) -> str:
    """PptxTextBox → position:absolute <div> 변환."""
    style = (
        f"position:absolute;"
        f"left:{tb.left_px}px;top:{tb.top_px}px;"
        f"width:{tb.width_px}px;height:{tb.height_px}px;"
        f"overflow:hidden;"
    )
    if tb.line_spacing_pt:
        style += f"line-height:{tb.line_spacing_pt}pt;"
    if tb.vertical_alignment == "middle":
        style += "display:flex;flex-direction:column;justify-content:center;"
    elif tb.vertical_alignment == "bottom":
        style += "display:flex;flex-direction:column;justify-content:flex-end;"

    # 불릿 그룹핑
    has_bullets = any(p.bullet_level >= 0 for p in tb.paragraphs)
    inner_parts: list[str] = []
    if has_bullets:
        bullet_items: list[str] = []
        for para in tb.paragraphs:
            html = _paragraph_to_html(para)
            if para.bullet_level >= 0:
                bullet_items.append(html)
            else:
                if bullet_items:
                    inner_parts.append(f'<ul style="list-style:disc;padding-left:20px;margin:0">{"".join(bullet_items)}</ul>')
                    bullet_items = []
                inner_parts.append(html)
        if bullet_items:
            inner_parts.append(f'<ul style="list-style:disc;padding-left:20px;margin:0">{"".join(bullet_items)}</ul>')
    else:
        for para in tb.paragraphs:
            inner_parts.append(_paragraph_to_html(para))

    return f'<div style="{style}">{"".join(inner_parts)}</div>'


def _shape_to_html(shape: PptxShape) -> str:
    """PptxShape → position:absolute <div> 변환."""
    style = (
        f"position:absolute;"
        f"left:{shape.left_px}px;top:{shape.top_px}px;"
        f"width:{shape.width_px}px;height:{shape.height_px}px;"
    )
    if shape.fill_color:
        style += f"background-color:{shape.fill_color};"
    if shape.border_color:
        bw = shape.border_width_pt or 1
        style += f"border:{bw}pt solid {shape.border_color};"
    if shape.corner_radius_px:
        style += f"border-radius:{shape.corner_radius_px}px;"
    if shape.shape_type == "rounded_rectangle" and not shape.corner_radius_px:
        style += "border-radius:8px;"
    if shape.shape_type == "ellipse":
        style += "border-radius:50%;"

    style += "overflow:hidden;"

    # 패딩
    pl = shape.padding_left_px or 8
    pr = shape.padding_right_px or 8
    pt_ = shape.padding_top_px or 4
    pb = shape.padding_bottom_px or 4
    style += f"padding:{pt_}px {pr}px {pb}px {pl}px;box-sizing:border-box;"

    # 수직 정렬
    if shape.vertical_alignment == "middle":
        style += "display:flex;flex-direction:column;justify-content:center;"
    elif shape.vertical_alignment == "bottom":
        style += "display:flex;flex-direction:column;justify-content:flex-end;"

    inner = ""
    if shape.paragraphs:
        para_parts: list[str] = []
        for para in shape.paragraphs:
            para_parts.append(_paragraph_to_html(para))
        inner = "".join(para_parts)
    elif shape.text:
        text_style = ""
        if shape.text_color:
            text_style += f"color:{shape.text_color};"
        if shape.text_size_pt:
            text_style += f"font-size:{shape.text_size_pt}pt;"
        if shape.text_bold:
            text_style += "font-weight:bold;"
        escaped = _escape_html(shape.text).replace("\n", "<br>")
        inner = f'<span style="{text_style}">{escaped}</span>'

    return f'<div style="{style}">{inner}</div>'
