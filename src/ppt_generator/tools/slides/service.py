from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

from strands import Agent

from bs4 import BeautifulSoup

from ppt_generator.interfaces.constants import (
    DEFAULT_LAYOUT_INDEX,
    LAYOUT_REGIONS,
    SLIDES_TEMPLATE_PATH,
    SLIDES_DESIGN_SUMMARY_PROMPT,
    SLIDES_MAX_PER_BATCH,
    SLIDES_MODIFY_SINGLE_USER_PROMPT_TEMPLATE,
    SLIDES_MODIFY_USER_PROMPT_TEMPLATE,
    SLIDES_REGION_BATCH_USER_PROMPT_TEMPLATE,
    SLIDES_REGION_USER_PROMPT_TEMPLATE,
    build_layout_skeleton,
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

        # region 기반 좌표 검증
        layout_index = self._detect_layout_index_from_html(modified_section_html)
        modified_section_html = self._validate_region_styles(modified_section_html, layout_index)

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

    def _generate_single(self, slides: list[SlideOutline], image_paths: dict[int, str], start_index: int = 0) -> str:
        all_sections: list[str] = []
        for i, slide in enumerate(slides):
            global_idx = start_index + i
            image_placeholder = f"{{IMAGE_{global_idx}}}" if global_idx in image_paths else None
            skeleton = build_layout_skeleton(
                layout_index=slide.layout_index,
                slide_index=global_idx,
                image_placeholder=image_placeholder,
            )
            outline_json = json.dumps(
                {"slides": [self._slide_to_dict(slide)]},
                ensure_ascii=False,
                indent=2,
            )
            image_data = self._build_image_data([slide], image_paths, start_index=global_idx)

            prompt = SLIDES_REGION_USER_PROMPT_TEMPLATE.format(
                outline_json=outline_json,
                image_data=image_data,
                skeleton_html=skeleton,
            )
            result = str(self._agent(prompt))

            section = self._extract_sections(result)
            section = self._validate_region_styles(section, slide.layout_index)
            all_sections.append(section)

        combined = "\n".join(all_sections)
        combined = self._replace_image_placeholders(combined, image_paths)
        html = self._wrap_with_template(combined)
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
        all_sections: list[str] = []
        for i, slide in enumerate(slides):
            global_idx = offset + i
            image_placeholder = f"{{IMAGE_{global_idx}}}" if global_idx in image_paths else None
            skeleton = build_layout_skeleton(
                layout_index=slide.layout_index,
                slide_index=global_idx,
                image_placeholder=image_placeholder,
            )
            outline_json = json.dumps(
                {"slides": [self._slide_to_dict(slide)]},
                ensure_ascii=False,
                indent=2,
            )
            image_data = self._build_image_data([slide], image_paths, start_index=global_idx)

            prompt = SLIDES_REGION_BATCH_USER_PROMPT_TEMPLATE.format(
                design_summary=design_summary,
                outline_json=outline_json,
                image_data=image_data,
                skeleton_html=skeleton,
            )
            result = str(self._agent(prompt))

            section = self._extract_sections(result)
            section = self._validate_region_styles(section, slide.layout_index)
            all_sections.append(section)

        combined = "\n".join(all_sections)
        combined = self._replace_image_placeholders(combined, image_paths)
        return combined

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

    # --- 좌표 검증 ---

    @staticmethod
    def _validate_region_styles(section_html: str, layout_index: int) -> str:
        """LLM이 region div의 좌표를 변경했을 경우 LAYOUT_REGIONS 원본 좌표로 복원."""
        regions = LAYOUT_REGIONS.get(layout_index, LAYOUT_REGIONS[DEFAULT_LAYOUT_INDEX])
        soup = BeautifulSoup(section_html, "html.parser")

        for region_div in soup.find_all("div", attrs={"data-region": True}):
            region_name = region_div["data-region"]
            if region_name not in regions:
                continue
            coords = regions[region_name]
            correct_style = (
                f"position:absolute; left:{coords['left']}px; top:{coords['top']}px; "
                f"width:{coords['width']}px; height:{coords['height']}px; overflow:hidden;"
            )
            region_div["style"] = correct_style

        return str(soup)

    @staticmethod
    def _detect_layout_index_from_html(section_html: str) -> int:
        """section HTML의 data-region 이름들로 layout_index를 추정."""
        soup = BeautifulSoup(section_html, "html.parser")
        region_names = {
            div["data-region"]
            for div in soup.find_all("div", attrs={"data-region": True})
        }
        if not region_names:
            return DEFAULT_LAYOUT_INDEX

        for layout_index, regions in LAYOUT_REGIONS.items():
            if set(regions.keys()) == region_names:
                return layout_index
        return DEFAULT_LAYOUT_INDEX

    # --- 유틸리티 ---

    @staticmethod
    def _slide_to_dict(slide: SlideOutline) -> dict:
        return {
            "title": slide.title,
            "content_summary": slide.content_summary,
            "layout_index": slide.layout_index,
        }

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
                    f"- 슬라이드 {global_idx} (layout_index={slide.layout_index}): "
                    f"이미지 있음 → {{IMAGE_{global_idx}}} placeholder를 사용하세요."
                )
            else:
                lines.append(f"- 슬라이드 {global_idx} (layout_index={slide.layout_index}): 이미지 없음")
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
