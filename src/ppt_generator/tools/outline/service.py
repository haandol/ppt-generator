"""Outline generation service.

LLM 호출을 클라이언트로 오프로딩했다. 이 서비스는 두 단계를 제공한다:

- ``prepare``: 클라이언트가 아웃라인을 생성하는 데 필요한 system/user 프롬프트와
  출력 JSON 스키마를 조립해 반환한다 (LLM 호출 없음).
- ``ingest``: 클라이언트가 스키마대로 생성해 돌려준 JSON 을 검증하고,
  발표자 정보 주입 등 후처리를 거쳐 ``OutlineResponse`` 로 만든다.

프롬프트·스키마·후처리 로직은 서버가 그대로 소유한다.
"""

import logging
from dataclasses import replace

from ppt_generator.interfaces.constants import (
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.handoff import build_llm_task
from ppt_generator.interfaces.llm_output_models import OutlineOutput
from ppt_generator.interfaces.schemas import (
    OutlineRequest,
    OutlineResponse,
    SlideOutline,
)
from ppt_generator.interfaces.utils import extract_json_from_response

logger = logging.getLogger(__name__)


class OutlineService:
    def prepare(self, request: OutlineRequest) -> dict:
        """클라이언트가 아웃라인을 생성하는 데 필요한 LLM 태스크를 조립한다.

        Returns:
            build_llm_task 결과 — system_prompt, user_prompt, response_schema.
        """
        if not request.topic.strip():
            raise ValueError("Topic is empty.")

        user_prompt = OUTLINE_USER_PROMPT_TEMPLATE.format(
            topic=request.topic,
            num_slides=request.num_slides,
            audience_type=request.audience_type,
            presentation_minutes=request.presentation_minutes,
            purpose=request.purpose or "general presentation",
        )
        return build_llm_task(
            system_prompt=OUTLINE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=OutlineOutput.model_json_schema(),
        )

    def ingest(self, outline_text: str, request: OutlineRequest) -> OutlineResponse:
        """클라이언트가 생성한 아웃라인 JSON 을 검증·후처리해 응답으로 만든다.

        Args:
            outline_text: 클라이언트가 스키마대로 생성한 아웃라인 (JSON 문자열,
                markdown fence 허용).
            request: 원래 요청 (발표자 정보 주입에 사용).

        Raises:
            ValueError: JSON 파싱 실패 또는 'slides' 배열 누락.
        """
        output = self._parse_json(outline_text)
        slides = self._build_slides(output)
        slides = self._inject_presenter_info(slides, request)
        return OutlineResponse(slides=slides)

    def _parse_json(self, text: str) -> OutlineOutput:
        data = extract_json_from_response(text)
        return OutlineOutput.model_validate(data)

    @staticmethod
    def _inject_presenter_info(
        slides: list[SlideOutline],
        request: OutlineRequest,
    ) -> list[SlideOutline]:
        """title 슬라이드의 content_summary에 발표자 정보를 주입한다."""
        if not request.presenter_name:
            return slides
        parts = [f"발표자: {request.presenter_name}"]
        if request.presenter_title:
            parts.append(request.presenter_title)
        if request.presenter_org:
            parts.append(request.presenter_org)
        presenter_line = " / ".join(parts)
        result: list[SlideOutline] = []
        for slide in slides:
            if slide.slide_type == "title":
                new_summary = f"{slide.content_summary}. {presenter_line}"
                result.append(replace(slide, content_summary=new_summary))
            else:
                result.append(slide)
        return result

    def _build_slides(self, output: OutlineOutput) -> list[SlideOutline]:
        slides: list[SlideOutline] = []
        for i, item in enumerate(output.slides):
            slides.append(
                SlideOutline(
                    title=item.title,
                    content_summary=item.content_summary,
                    component_hint=item.component_hint,
                    speaker_notes=item.speaker_notes,
                    slide_type=item.slide_type,
                    slide_index=i,
                    layout_plan=item.layout_plan,
                )
            )
        return slides
