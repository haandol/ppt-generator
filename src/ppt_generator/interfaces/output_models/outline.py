"""아웃라인 생성 응답과 발표 구성 검증."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

ComponentHint = Literal[
    "bullets",
    "two_column",
    "vs_comparison",
    "step_cards",
    "code_block",
    "arch_diagram",
    "pipeline",
    "quote",
    "summary_grid",
    "agenda",
    "info_cards",
    "feature_list",
    "cta",
    "process_flow",
    "quote_code",
    "concept_list",
    "custom",
]


class SlideOutlineOutput(BaseModel):
    """클라이언트가 생성하는 단일 슬라이드 아웃라인."""

    model_config = ConfigDict(extra="forbid")

    title: str
    content_summary: str
    component_hint: ComponentHint
    slide_type: Literal["title", "closing", "content"]
    layout_plan: str
    speaker_notes: str
    source_refs: list[str]
    assumptions: list[str]
    slide_index: int | None = None


class OutlineOutput(BaseModel):
    """클라이언트가 생성하는 전체 아웃라인."""

    model_config = ConfigDict(extra="forbid")

    slides: list[SlideOutlineOutput]

    @model_validator(mode="after")
    def validate_required_composition(self) -> "OutlineOutput":
        """필수 발표 골격과 슬라이드 수를 저장 전에 검증한다."""
        count = len(self.slides)
        if not 4 <= count <= 20:
            raise ValueError("outline must contain 4~20 slides")
        if self.slides[0].slide_type != "title":
            raise ValueError("slide 1 must be title")
        agenda = self.slides[1]
        if agenda.slide_type != "content" or agenda.component_hint != "agenda":
            raise ValueError("slide 2 must be a content agenda slide")
        if self.slides[-1].slide_type != "closing":
            raise ValueError("last slide must be closing")
        if any(slide.slide_type != "content" for slide in self.slides[2:-1]):
            raise ValueError("slides between agenda and closing must be content")
        return self
