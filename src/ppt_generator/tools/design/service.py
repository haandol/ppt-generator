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
from strands.types.exceptions import ModelThrottledException

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
from ppt_generator.interfaces.utils import log_token_usage

logger = logging.getLogger(__name__)


class DesignService:
    """슬라이드 아웃라인 → PptxSlideSpec을 생성하는 서비스."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._last_token_usage: dict[str, int] = {}

    def generate_single_slide(
        self,
        slide_outline: SlideOutline,
        design_summary: dict | None = None,
        slide_index: int = 1,
        total_slides: int = 1,
        color_theme: str = "dark",
        prev_outline: SlideOutline | None = None,
        next_outline: SlideOutline | None = None,
    ) -> PptxSlideSpec:
        """단일 슬라이드의 디자인 스펙을 생성한다.

        Args:
            slide_outline: 슬라이드 아웃라인
            design_summary: 기존 디자인 요약 dict (제공 시 일관성 유지)
            slide_index: 슬라이드 번호 (1-based)
            total_slides: 전체 슬라이드 수
            color_theme: 색상 테마 ("dark" 또는 "light", 기본값: "dark")
            prev_outline: 이전 슬라이드 아웃라인 (첫 슬라이드면 None)
            next_outline: 다음 슬라이드 아웃라인 (마지막 슬라이드면 None)

        Returns:
            생성된 PptxSlideSpec
        """
        outline_json = self._outline_to_json(slide_outline)
        adjacent_context = self._adjacent_context_section(prev_outline, next_outline)

        if design_summary:
            summary_text = json.dumps(design_summary, ensure_ascii=False, indent=2)
            prompt = DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE.format(
                slide_index=slide_index,
                total_slides=total_slides,
                design_summary=summary_text,
                outline_json=outline_json,
                color_theme=color_theme,
                adjacent_context=adjacent_context,
            )
        else:
            prompt = DESIGN_SPEC_USER_PROMPT_TEMPLATE.format(
                slide_index=slide_index,
                total_slides=total_slides,
                outline_json=outline_json,
                color_theme=color_theme,
                adjacent_context=adjacent_context,
            )

        spec = self._generate_with_structured_output(
            prompt, label=f"slide[{slide_index}/{total_slides}]",
        )
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

        try:
            result = self._agent(prompt)
            log_token_usage(result, "design_summary")
        except ModelThrottledException:
            logger.warning("design_summary 생성 중 Bedrock 쓰로틀링 발생")
            raise
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

    @property
    def last_token_usage(self) -> dict[str, int]:
        """직전 LLM 호출의 토큰 사용량. 호출 전이면 빈 dict."""
        return self._last_token_usage

    def _generate_with_structured_output(self, prompt: str, *, label: str = "design_spec") -> PptxSlideSpec:
        """strands structured_output으로 슬라이드 스펙을 생성하고 검증."""
        try:
            result = self._agent(prompt, structured_output_model=SlideSpecOutput)
            self._last_token_usage = log_token_usage(result, label)
        except ModelThrottledException:
            logger.warning("디자인 스펙 생성 중 Bedrock 쓰로틀링 발생")
            raise
        output: SlideSpecOutput = result.structured_output
        spec = output.to_dataclass()
        return validate_slide_spec(spec)

    @staticmethod
    def _adjacent_context_section(
        prev_outline: SlideOutline | None,
        next_outline: SlideOutline | None,
    ) -> str:
        """인접 슬라이드의 아웃라인 요약을 프롬프트 섹션으로 생성한다.

        speaker_notes는 제외하여 토큰을 절약한다.
        둘 다 None이면 빈 문자열을 반환한다.
        """
        if prev_outline is None and next_outline is None:
            return ""

        def _summarize(outline: SlideOutline) -> dict:
            return {
                "title": outline.title,
                "content_summary": outline.content_summary,
                "component_hint": outline.component_hint,
                "slide_type": outline.slide_type,
            }

        parts: list[str] = ["<adjacent_slides>"]
        if prev_outline is not None:
            prev_json = json.dumps(_summarize(prev_outline), ensure_ascii=False, indent=2)
            parts.append(f"<previous_slide>\n{prev_json}\n</previous_slide>")
        if next_outline is not None:
            next_json = json.dumps(_summarize(next_outline), ensure_ascii=False, indent=2)
            parts.append(f"<next_slide>\n{next_json}\n</next_slide>")
        parts.append("</adjacent_slides>")
        return "\n".join(parts)

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
