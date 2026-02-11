from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from pathlib import Path

from strands import Agent

from ppt_generator.interfaces.constants import (
    SLIDES_HEIGHT_PX,
    SLIDES_USER_PROMPT_TEMPLATE,
    SLIDES_WIDTH_PX,
)
from ppt_generator.interfaces.schemas import SlidesRequest, SlidesResponse, SlideOutline

logger = logging.getLogger(__name__)


class SlidesService:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._sessions: dict[str, str] = {}

    def generate(self, request: SlidesRequest) -> SlidesResponse:
        if not request.slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        outline_json = json.dumps(
            {"slides": [self._slide_to_dict(s) for s in request.slides]},
            ensure_ascii=False,
            indent=2,
        )
        image_data = self._build_image_data(request.slides, request.image_paths)

        prompt = SLIDES_USER_PROMPT_TEMPLATE.format(
            outline_json=outline_json,
            image_data=image_data,
        )
        result = str(self._agent(prompt))

        html = self._extract_html(result)
        html = self._replace_image_placeholders(html, request.image_paths)

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = html

        logger.info("HTML 슬라이드 생성 완료: session_id=%s, 슬라이드 수=%d", session_id, len(request.slides))
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
    def _build_image_data(slides: list[SlideOutline], image_paths: dict[int, str]) -> str:
        lines: list[str] = []
        for i, slide in enumerate(slides):
            if i in image_paths and Path(image_paths[i]).exists():
                lines.append(f"- 슬라이드 {i} ({slide.layout_type}): 이미지 있음 → {{IMAGE_{i}}} placeholder를 사용하세요.")
            else:
                lines.append(f"- 슬라이드 {i} ({slide.layout_type}): 이미지 없음")
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
                f'<html><head><meta charset="UTF-8"></head><body style="margin:0;padding:0;">\n'
                f"{text.strip()}\n"
                "</body></html>"
            )

        # 폴백: 전체 텍스트를 HTML로 간주
        logger.warning("HTML 추출 실패, 원본 텍스트를 그대로 사용합니다.")
        return text.strip()
