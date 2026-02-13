"""디자인 스펙 생성 서비스.

슬라이드 아웃라인에서 PptxSlideSpec 기반 디자인 스펙을 LLM으로 생성한다.
"""

from __future__ import annotations

import json
import logging
import re

from strands import Agent

from ppt_generator.interfaces.constants import (
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_DESIGN_SUMMARY_PROMPT,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    DesignSpecRequest,
    DesignSpecResponse,
    PptxSlideSpec,
    SlideOutline,
)
from ppt_generator.interfaces.spec_utils import (
    parse_slide_spec,
    validate_slide_spec,
)

logger = logging.getLogger(__name__)


class DesignService:
    """슬라이드 아웃라인 → DesignSpec(PptxSlideSpec 리스트)을 생성하는 서비스."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def generate(self, request: DesignSpecRequest) -> DesignSpecResponse:
        """슬라이드 아웃라인 목록으로부터 전체 디자인 스펙을 생성한다.

        첫 슬라이드 생성 후 디자인 요약을 추출하여 후속 슬라이드에 전달,
        프레젠테이션 전체의 시각적 일관성을 유지한다.
        """
        if not request.slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        slides = request.slides
        specs: list[PptxSlideSpec] = []
        design_summary: str = ""

        for idx, slide in enumerate(slides):
            outline_json = json.dumps(
                {
                    "title": slide.title,
                    "content_summary": slide.content_summary,
                    "component_hint": slide.component_hint,
                    "speaker_notes": slide.speaker_notes,
                },
                ensure_ascii=False,
                indent=2,
            )

            if idx == 0:
                prompt = DESIGN_SPEC_USER_PROMPT_TEMPLATE.format(
                    outline_json=outline_json,
                )
            else:
                prompt = DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE.format(
                    design_summary=design_summary,
                    outline_json=outline_json,
                )

            raw_result = str(self._agent(prompt))
            spec = self._parse_and_validate(raw_result)
            specs.append(spec)

            logger.info("디자인 스펙 생성 완료: 슬라이드 %d/%d", idx + 1, len(slides))

            # 첫 슬라이드 후 디자인 요약 추출
            if idx == 0:
                design_summary = self._extract_design_summary(raw_result)

        design_spec = DesignSpec(slides=specs)
        return DesignSpecResponse(design_spec=design_spec)

    def generate_single_slide(
        self,
        slide_outline: SlideOutline,
        design_summary: str = "",
    ) -> PptxSlideSpec:
        """단일 슬라이드의 디자인 스펙을 생성한다.

        Args:
            slide_outline: 슬라이드 아웃라인
            design_summary: 기존 디자인 요약 (제공 시 일관성 유지)

        Returns:
            생성된 PptxSlideSpec
        """
        outline_json = json.dumps(
            {
                "title": slide_outline.title,
                "content_summary": slide_outline.content_summary,
                "component_hint": slide_outline.component_hint,
                "speaker_notes": slide_outline.speaker_notes,
            },
            ensure_ascii=False,
            indent=2,
        )

        if design_summary:
            prompt = DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE.format(
                design_summary=design_summary,
                outline_json=outline_json,
            )
        else:
            prompt = DESIGN_SPEC_USER_PROMPT_TEMPLATE.format(
                outline_json=outline_json,
            )

        raw_result = str(self._agent(prompt))
        return self._parse_and_validate(raw_result)

    def _extract_design_summary(self, spec_json_text: str) -> str:
        """첫 슬라이드 스펙에서 디자인 테마 요약을 추출."""
        prompt = DESIGN_SPEC_DESIGN_SUMMARY_PROMPT.format(
            spec_json=spec_json_text,
        )
        result = str(self._agent(prompt))
        return result.strip()

    @staticmethod
    def _parse_and_validate(raw_text: str) -> PptxSlideSpec:
        """LLM 응답에서 JSON을 추출하고 PptxSlideSpec으로 파싱 및 검증."""
        json_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
        json_text = re.sub(r"\s*```$", "", json_text.strip())
        data = json.loads(json_text)
        spec = parse_slide_spec(data)
        return validate_slide_spec(spec)
