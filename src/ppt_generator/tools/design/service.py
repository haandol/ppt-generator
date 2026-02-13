"""디자인 스펙 생성 서비스.

슬라이드 아웃라인에서 PptxSlideSpec 기반 디자인 스펙을 LLM으로 생성한다.
strands structured_output을 사용하여 Pydantic 모델로 직접 파싱한다.
"""

from __future__ import annotations

import json
import logging

from strands import Agent

from ppt_generator.interfaces.constants import (
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_DESIGN_SUMMARY_TEMPLATE,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    DesignSpecRequest,
    DesignSpecResponse,
    PptxSlideSpec,
    SlideOutline,
    SlideSpecOutput,
)
from ppt_generator.interfaces.spec_utils import validate_slide_spec

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
        total = len(slides)
        specs: list[PptxSlideSpec] = []
        design_summary: str = ""

        for idx, slide in enumerate(slides):
            outline_json = self._outline_to_json(slide)

            if idx == 0:
                prompt = DESIGN_SPEC_USER_PROMPT_TEMPLATE.format(
                    slide_index=idx + 1,
                    total_slides=total,
                    outline_json=outline_json,
                )
            else:
                prompt = DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE.format(
                    slide_index=idx + 1,
                    total_slides=total,
                    design_summary=design_summary,
                    outline_json=outline_json,
                )

            spec = self._generate_with_structured_output(prompt)
            specs.append(spec)

            logger.info("디자인 스펙 생성 완료: 슬라이드 %d/%d", idx + 1, total)

            # 첫 슬라이드 후 디자인 요약 추출 (LLM 호출 없이 직접 추출)
            if idx == 0:
                design_summary = self._extract_design_summary(spec)

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
        outline_json = self._outline_to_json(slide_outline)

        if design_summary:
            prompt = DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE.format(
                slide_index=1,
                total_slides=1,
                design_summary=design_summary,
                outline_json=outline_json,
            )
        else:
            prompt = DESIGN_SPEC_USER_PROMPT_TEMPLATE.format(
                slide_index=1,
                total_slides=1,
                outline_json=outline_json,
            )

        return self._generate_with_structured_output(prompt)

    @staticmethod
    def _extract_design_summary(spec: PptxSlideSpec) -> str:
        """슬라이드 스펙에서 디자인 테마 요약을 직접 추출 (LLM 호출 없음)."""
        # 텍스트 색상 수집
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

        # shape에서도 수집
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

        card_style_parts = []
        if card_fills:
            card_style_parts.append(f"fill: {', '.join(sorted(card_fills))}")
        if card_borders:
            card_style_parts.append(f"border: {', '.join(sorted(card_borders))}")
        card_style = "; ".join(card_style_parts) if card_style_parts else "없음"

        return DESIGN_SPEC_DESIGN_SUMMARY_TEMPLATE.format(
            background_color=spec.background_color or "없음",
            text_colors=", ".join(sorted(text_colors)) if text_colors else "없음",
            title_font=title_font or "없음",
            body_font=body_font or "없음",
            card_style=card_style,
        )

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
            },
            ensure_ascii=False,
            indent=2,
        )
