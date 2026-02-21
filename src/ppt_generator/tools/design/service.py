"""디자인 스펙 생성 서비스.

슬라이드 아웃라인에서 PptxSlideSpec 기반 디자인 스펙을 LLM으로 생성한다.
strands structured_output을 사용하여 Pydantic 모델로 직접 파싱한다.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace

from strands import Agent

from ppt_generator.interfaces.constants import (
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
    DESIGN_SUMMARY_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.llm_output_models import SlideSpecOutput
from ppt_generator.interfaces.schemas import (
    OutlineResponse,
    PptxSlideSpec,
    SlideOutline,
)
from ppt_generator.interfaces.spec_utils import validate_slide_spec

logger = logging.getLogger(__name__)


class DesignService:
    """슬라이드 아웃라인 → PptxSlideSpec을 생성하는 서비스."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def generate_single_slide(
        self,
        slide_outline: SlideOutline,
        design_summary: dict | None = None,
        slide_index: int = 1,
        total_slides: int = 1,
        color_theme: str = "dark",
    ) -> PptxSlideSpec:
        """단일 슬라이드의 디자인 스펙을 생성한다.

        Args:
            slide_outline: 슬라이드 아웃라인
            design_summary: 기존 디자인 요약 dict (제공 시 일관성 유지)
            slide_index: 슬라이드 번호 (1-based)
            total_slides: 전체 슬라이드 수
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")

        Returns:
            생성된 PptxSlideSpec
        """
        outline_json = self._outline_to_json(slide_outline)

        if design_summary:
            summary_text = json.dumps(design_summary, ensure_ascii=False, indent=2)
            prompt = DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE.format(
                slide_index=slide_index,
                total_slides=total_slides,
                design_summary=summary_text,
                outline_json=outline_json,
                color_theme=color_theme,
            )
        else:
            prompt = DESIGN_SPEC_USER_PROMPT_TEMPLATE.format(
                slide_index=slide_index,
                total_slides=total_slides,
                outline_json=outline_json,
                color_theme=color_theme,
            )

        spec = self._generate_with_structured_output(prompt)
        return replace(spec, slide_type=slide_outline.slide_type)

    def generate_design_summary(
        self,
        outline: OutlineResponse,
        color_theme: str = "dark",
    ) -> dict:
        """전체 아웃라인을 기반으로 design_summary를 LLM으로 사전 생성한다.

        Args:
            outline: 전체 아웃라인 (OutlineResponse)
            color_theme: 색상 테마 ("dark" 또는 "light")

        Returns:
            extract_design_summary()와 동일한 형식의 dict
        """
        outline_json = json.dumps(
            [
                {
                    "title": s.title,
                    "content_summary": s.content_summary,
                    "component_hint": s.component_hint,
                    "slide_type": s.slide_type,
                }
                for s in outline.slides
            ],
            ensure_ascii=False,
            indent=2,
        )

        prompt = DESIGN_SUMMARY_USER_PROMPT_TEMPLATE.format(
            total_slides=len(outline.slides),
            color_theme=color_theme,
            outline_json=outline_json,
        )

        result = self._agent(prompt)
        raw_text = str(result)

        # JSON 블록 추출 (```json ... ``` 또는 순수 JSON)
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(1)

        summary = json.loads(raw_text.strip())
        logger.info("design_summary LLM 생성 완료: %s", summary)
        return summary

    @staticmethod
    def extract_design_summary(spec: PptxSlideSpec) -> dict:
        """슬라이드 스펙에서 디자인 테마 요약을 직접 추출 (LLM 호출 없음)."""
        text_colors: set[str] = set()
        title_font: int | None = None
        body_font: int | None = None

        for tb in spec.textboxes:
            for para in tb.paragraphs:
                for run in para.runs:
                    if run.color:
                        text_colors.add(run.color)
                    if run.font_size_pt:
                        if run.bold and (title_font is None or run.font_size_pt > title_font):
                            title_font = run.font_size_pt
                        elif not run.bold and (body_font is None or run.font_size_pt > body_font):
                            body_font = run.font_size_pt

        card_fills: set[str] = set()
        card_borders: set[str] = set()
        for s in spec.shapes:
            if s.fill_color:
                card_fills.add(s.fill_color)
            if s.border_color:
                card_borders.add(s.border_color)
            for para in s.paragraphs:
                for run in para.runs:
                    if run.color:
                        text_colors.add(run.color)
                    if run.font_size_pt:
                        if run.bold and (title_font is None or run.font_size_pt > title_font):
                            title_font = run.font_size_pt
                        elif not run.bold and (body_font is None or run.font_size_pt > body_font):
                            body_font = run.font_size_pt
            if s.text_color:
                text_colors.add(s.text_color)

        return {
            "background_color": spec.background_color or None,
            "text_colors": sorted(text_colors) if text_colors else [],
            "title_font_pt": title_font,
            "body_font_pt": body_font,
            "card_fills": sorted(card_fills) if card_fills else [],
            "card_borders": sorted(card_borders) if card_borders else [],
        }

    def _generate_with_structured_output(self, prompt: str) -> PptxSlideSpec:
        """strands structured_output으로 슬라이드 스펙을 생성하고 검증."""
        result = self._agent(prompt, structured_output_model=SlideSpecOutput)
        output: SlideSpecOutput = result.structured_output
        spec = output.to_dataclass()
        return validate_slide_spec(spec)

    @staticmethod
    def _outline_to_json(slide: SlideOutline) -> str:
        """SlideOutline을 JSON 문자열로 변환."""
        return json.dumps(
            {
                "title": slide.title,
                "content_summary": slide.content_summary,
                "component_hint": slide.component_hint,
                "speaker_notes": slide.speaker_notes,
                "slide_type": slide.slide_type,
            },
            ensure_ascii=False,
            indent=2,
        )
