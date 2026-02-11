from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

from strands import Agent

from bs4 import BeautifulSoup

from ppt_generator.interfaces.constants import (
    REVEALJS_TEMPLATE_PATH,
    SLIDES_BATCH_USER_PROMPT_TEMPLATE,
    SLIDES_DESIGN_SUMMARY_PROMPT,
    SLIDES_MAX_PER_BATCH,
    SLIDES_MODIFY_SINGLE_USER_PROMPT_TEMPLATE,
    SLIDES_MODIFY_USER_PROMPT_TEMPLATE,
    SLIDES_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.schemas import SlidesRequest, SlidesResponse, SlideOutline

logger = logging.getLogger(__name__)


class SlidesService:
    def __init__(self, agent: Agent, modify_agent: Agent) -> None:
        self._agent = agent
        self._modify_agent = modify_agent
        self._sessions: dict[str, tuple[str, dict[int, str]]] = {}

    def generate(self, request: SlidesRequest) -> SlidesResponse:
        if not request.slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        if len(request.slides) <= SLIDES_MAX_PER_BATCH:
            html = self._generate_single(request.slides, request.image_paths)
        else:
            html = self._generate_batched(request.slides, request.image_paths)

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = (html, dict(request.image_paths))

        logger.info("HTML 슬라이드 생성 완료: session_id=%s, 슬라이드 수=%d", session_id, len(request.slides))
        return SlidesResponse(session_id=session_id, html=html)

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

        _, image_paths = self._sessions[session_id]
        self._sessions[session_id] = (html, image_paths)
        return SlidesResponse(session_id=session_id, html=html)

    def _modify_single_slide(self, full_html: str, slide_index: int, modification_request: str) -> str:
        soup = BeautifulSoup(full_html, "html.parser")
        slides_container = soup.find("div", class_="slides")
        if slides_container is None:
            raise ValueError("reveal.js slides 컨테이너를 찾을 수 없습니다.")

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
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")
        return session[0]

    def get_session_image_paths(self, session_id: str) -> dict[int, str]:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")
        return session[1]

    def update_session_html(self, session_id: str, html: str) -> None:
        if session_id not in self._sessions:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")
        _, image_paths = self._sessions[session_id]
        self._sessions[session_id] = (html, image_paths)

    # --- 생성 내부 메서드 ---

    def _generate_single(self, slides: list[SlideOutline], image_paths: dict[int, str]) -> str:
        outline_json = json.dumps(
            {"slides": [self._slide_to_dict(s) for s in slides]},
            ensure_ascii=False,
            indent=2,
        )
        image_data = self._build_image_data(slides, image_paths, start_index=0)

        prompt = SLIDES_USER_PROMPT_TEMPLATE.format(
            outline_json=outline_json,
            image_data=image_data,
        )
        result = str(self._agent(prompt))

        sections_html = self._extract_sections(result)
        sections_html = self._replace_image_placeholders(sections_html, image_paths)
        html = self._wrap_with_revealjs_template(sections_html)
        return html

    def _generate_batched(self, slides: list[SlideOutline], image_paths: dict[int, str]) -> str:
        chunks = self._chunk_slides(slides, SLIDES_MAX_PER_BATCH)

        # 첫 배치: 전체 HTML 문서 생성
        first_chunk = chunks[0]
        first_image_paths = {i: image_paths[i] for i in range(len(first_chunk)) if i in image_paths}
        first_html = self._generate_single(first_chunk, first_image_paths)

        if len(chunks) == 1:
            return first_html

        # 디자인 요약 추출
        design_summary = self._extract_design_summary(first_html)

        # 후속 배치: 슬라이드 div만 생성
        continuation_divs: list[str] = []
        offset = len(first_chunk)
        for chunk in chunks[1:]:
            divs = self._generate_continuation_batch(chunk, image_paths, design_summary, offset)
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
        image_paths: dict[int, str],
        design_summary: str,
        offset: int,
    ) -> str:
        outline_json = json.dumps(
            {"slides": [self._slide_to_dict(s) for s in slides]},
            ensure_ascii=False,
            indent=2,
        )
        image_data = self._build_image_data(slides, image_paths, start_index=offset)

        prompt = SLIDES_BATCH_USER_PROMPT_TEMPLATE.format(
            design_summary=design_summary,
            outline_json=outline_json,
            image_data=image_data,
        )
        result = str(self._agent(prompt))

        # 후속 배치는 section만 반환되므로 코드블록 추출 후 placeholder 치환
        sections = self._extract_sections(result)
        sections = self._replace_image_placeholders(sections, image_paths)
        return sections

    @staticmethod
    def _chunk_slides(slides: list[SlideOutline], chunk_size: int) -> list[list[SlideOutline]]:
        return [slides[i : i + chunk_size] for i in range(0, len(slides), chunk_size)]

    @staticmethod
    def _combine_html_batches(first_html: str, continuation_sections: list[str]) -> str:
        insertion = "\n".join(continuation_sections)
        # </div><!-- .slides --> 또는 마지막 </section> 뒤에 삽입
        # reveal.js 구조에서 slides 컨테이너의 닫힘 태그 앞에 삽입
        soup = BeautifulSoup(first_html, "html.parser")
        slides_container = soup.find("div", class_="slides")
        if slides_container:
            new_sections = BeautifulSoup(insertion, "html.parser")
            for section in new_sections.find_all("section", recursive=False):
                slides_container.append(section)
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
        d: dict = {
            "title": slide.title,
            "bullets": slide.bullets,
            "image_idea": slide.image_idea,
            "layout_type": slide.layout_type,
            "speaker_notes": slide.speaker_notes,
        }
        if slide.elements:
            d["elements"] = [
                {
                    "type": e.type,
                    "left": e.left,
                    "top": e.top,
                    "width": e.width,
                    "height": e.height,
                    "content": e.content,
                    "font_size_pt": e.font_size_pt,
                    "bold": e.bold,
                }
                for e in slide.elements
            ]
        return d

    @staticmethod
    def _build_image_data(
        slides: list[SlideOutline],
        image_paths: dict[int, str],
        start_index: int = 0,
    ) -> str:
        lines: list[str] = []
        for i, slide in enumerate(slides):
            global_idx = start_index + i
            if global_idx in image_paths and Path(image_paths[global_idx]).exists():
                lines.append(
                    f"- 슬라이드 {global_idx} ({slide.layout_type}): "
                    f"이미지 있음 → {{IMAGE_{global_idx}}} placeholder를 사용하세요."
                )
            else:
                lines.append(f"- 슬라이드 {global_idx} ({slide.layout_type}): 이미지 없음")
        return "\n".join(lines)

    @staticmethod
    def _replace_image_placeholders(html: str, image_paths: dict[int, str]) -> str:
        for idx, path in image_paths.items():
            file_path = Path(path).resolve()
            if not file_path.exists():
                logger.warning("이미지 파일 누락: %s", path)
                continue
            html = html.replace(f"{{IMAGE_{idx}}}", f"file://{file_path}")
        return html

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
    def _wrap_with_revealjs_template(sections_html: str) -> str:
        """section 요소들을 reveal.js 템플릿에 삽입하여 완전한 HTML 문서 생성."""
        # style 태그와 section 태그 분리
        style_parts: list[str] = []
        remaining = sections_html
        for style_match in re.finditer(r"<style[^>]*>.*?</style>", sections_html, re.DOTALL):
            style_parts.append(style_match.group(0))
        if style_parts:
            for sp in style_parts:
                remaining = remaining.replace(sp, "")

        custom_style = "\n".join(style_parts)
        slides_content = remaining.strip()

        template = REVEALJS_TEMPLATE_PATH.read_text(encoding="utf-8")
        return template.replace("{custom_style}", custom_style).replace("{slides_content}", slides_content)

    @staticmethod
    def _extract_sections(text: str) -> str:
        """LLM 응답에서 <section> 요소들(및 선행 <style> 태그)을 추출."""
        # 1단계: 마크다운 코드블록에서 추출
        code_block = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        # 2단계: 완전한 HTML 문서가 반환된 경우 section들만 추출
        if "<!DOCTYPE html>" in text.lower() or "<html" in text.lower():
            soup = BeautifulSoup(text, "html.parser")
            # style 태그들 추출
            style_tags = []
            for style in soup.find_all("style"):
                style_tags.append(str(style))
            # section 태그들 추출
            sections = soup.find_all("section")
            if sections:
                parts = style_tags + [str(s) for s in sections]
                return "\n".join(parts)

        # 3단계: <section> 태그가 있으면 그대로 반환
        if "<section" in text:
            # style 태그와 section 태그를 포함한 부분만 추출
            parts: list[str] = []
            for style_match in re.finditer(r"<style[^>]*>.*?</style>", text, re.DOTALL):
                parts.append(style_match.group(0))
            for section_match in re.finditer(r"(<section[\s>].*?</section>)", text, re.DOTALL):
                parts.append(section_match.group(0))
            if parts:
                return "\n".join(parts)

        # 폴백: 전체 텍스트를 반환
        logger.warning("section 추출 실패, 원본 텍스트를 그대로 사용합니다.")
        return text.strip()
