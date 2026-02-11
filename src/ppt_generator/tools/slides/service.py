from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from pathlib import Path

from strands import Agent

from ppt_generator.interfaces.constants import (
    SLIDES_BATCH_USER_PROMPT_TEMPLATE,
    SLIDES_DESIGN_SUMMARY_PROMPT,
    SLIDES_MAX_PER_BATCH,
    SLIDES_MODIFY_USER_PROMPT_TEMPLATE,
    SLIDES_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.schemas import SlidesRequest, SlidesResponse, SlideOutline

logger = logging.getLogger(__name__)


class SlidesService:
    def __init__(self, agent: Agent, modify_agent: Agent) -> None:
        self._agent = agent
        self._modify_agent = modify_agent
        self._sessions: dict[str, str] = {}

    def generate(self, request: SlidesRequest) -> SlidesResponse:
        if not request.slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        if len(request.slides) <= SLIDES_MAX_PER_BATCH:
            html = self._generate_single(request.slides, request.image_paths)
        else:
            html = self._generate_batched(request.slides, request.image_paths)

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = html

        logger.info("HTML 슬라이드 생성 완료: session_id=%s, 슬라이드 수=%d", session_id, len(request.slides))
        return SlidesResponse(session_id=session_id, html=html)

    def modify(self, session_id: str, modification_request: str) -> SlidesResponse:
        if not modification_request.strip():
            raise ValueError("수정 요청이 비어있습니다.")
        current_html = self.get_session_html(session_id)
        prompt = SLIDES_MODIFY_USER_PROMPT_TEMPLATE.format(
            current_html=current_html,
            modification_request=modification_request,
        )
        result = str(self._modify_agent(prompt))
        html = self._extract_html(result)
        self._sessions[session_id] = html
        return SlidesResponse(session_id=session_id, html=html)

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

        html = self._extract_html(result)
        html = self._replace_image_placeholders(html, image_paths)
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

        # 후속 배치는 div만 반환되므로 코드블록 추출 후 placeholder 치환
        divs = self._extract_divs(result)
        divs = self._replace_image_placeholders(divs, image_paths)
        return divs

    @staticmethod
    def _chunk_slides(slides: list[SlideOutline], chunk_size: int) -> list[list[SlideOutline]]:
        return [slides[i : i + chunk_size] for i in range(0, len(slides), chunk_size)]

    @staticmethod
    def _combine_html_batches(first_html: str, continuation_divs: list[str]) -> str:
        insertion = "\n".join(continuation_divs)
        # </body> 앞에 후속 div 삽입
        match = re.search(r"</body>", first_html, re.IGNORECASE)
        if match:
            pos = match.start()
            return first_html[:pos] + "\n" + insertion + "\n" + first_html[pos:]
        # </body>가 없으면 끝에 추가
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
            file_path = Path(path)
            if not file_path.exists():
                logger.warning("이미지 파일 누락: %s", path)
                continue
            data = file_path.read_bytes()
            suffix = file_path.suffix.lower().lstrip(".")
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}.get(suffix, "image/png")
            b64 = base64.b64encode(data).decode("ascii")
            data_uri = f"data:{mime};base64,{b64}"
            html = html.replace(f"{{IMAGE_{idx}}}", data_uri)
        return html

    @staticmethod
    def _extract_html(text: str) -> str:
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

        # 3단계: <div class="slide"> 태그가 있으면 기본 HTML 구조로 감싸기
        if '<div class="slide"' in text or "<div class='slide'" in text:
            return (
                "<!DOCTYPE html>\n"
                '<html><head><meta charset="UTF-8"></head><body style="margin:0;padding:0;">\n'
                f"{text.strip()}\n"
                "</body></html>"
            )

        # 폴백: 전체 텍스트를 HTML로 간주
        logger.warning("HTML 추출 실패, 원본 텍스트를 그대로 사용합니다.")
        return text.strip()

    @staticmethod
    def _extract_divs(text: str) -> str:
        """후속 배치 응답에서 슬라이드 div들만 추출."""
        # 코드블록 안에 있으면 추출
        code_block = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        # <div class="slide" ...> 패턴들을 찾아서 반환
        divs = re.findall(r"(<div class=[\"']slide[\"'].*?</div>\s*</div>)", text, re.DOTALL)
        if divs:
            return "\n".join(divs)

        # 폴백: 전체 텍스트 반환
        return text.strip()
