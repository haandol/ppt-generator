"""LLM structured_output용 Pydantic 모델.

strands Agent의 structured_output_model로 사용되며,
to_dataclass() 메서드로 내부 dataclass(PptxSlideSpec)로 변환한다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)


class TextRunOutput(BaseModel):
    """LLM 출력용 텍스트 런 Pydantic 모델."""

    text: str
    font_size_pt: int | None = None
    color: str | None = None
    bold: bool = False
    italic: bool = False
    font_family: Literal["monospace"] | None = None
    href: str | None = None


class ParagraphOutput(BaseModel):
    """LLM 출력용 단락 Pydantic 모델."""

    runs: list[TextRunOutput] = Field(default_factory=list)
    bullet_level: int = Field(default=-1, ge=-1, le=1)
    alignment: Literal["left", "center", "right"] | None = None


class TextBoxOutput(BaseModel):
    """LLM 출력용 텍스트박스 Pydantic 모델."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    paragraphs: list[ParagraphOutput] = Field(default_factory=list)
    line_spacing_pt: float | None = None
    vertical_alignment: Literal["top", "middle", "bottom"] = "top"
    padding_left_px: float | None = None
    padding_right_px: float | None = None
    padding_top_px: float | None = None
    padding_bottom_px: float | None = None


class ShapeOutput(BaseModel):
    """LLM 출력용 도형 Pydantic 모델."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    shape_type: Literal["rectangle", "rounded_rectangle", "ellipse", "line"] = (
        "rectangle"
    )
    fill_color: str | None = None
    border_color: str | None = None
    border_width_pt: float | None = None
    corner_radius_px: float | None = None
    text: str | None = None
    text_color: str | None = None
    text_size_pt: int | None = None
    text_bold: bool = False
    paragraphs: list[ParagraphOutput] = Field(default_factory=list)
    line_spacing_pt: float | None = None
    padding_left_px: float | None = None
    padding_right_px: float | None = None
    padding_top_px: float | None = None
    padding_bottom_px: float | None = None
    vertical_alignment: Literal["top", "middle", "bottom"] = "top"
    end_arrow: bool = False
    start_arrow: bool = False
    dash_style: Literal["solid", "dash", "dot"] | None = None
    svg_path: str | None = None
    autofit_mode: Literal["expand_height", "shrink_text"] = "expand_height"


# --- Visual QA models ---


class VisualQAIssue(BaseModel):
    """Visual QA 분석에서 발견된 개별 이슈."""

    issue_type: Literal[
        "text_truncation",
        "overlap",
        "overflow",
        "contrast",
        "misalignment",
        "inconsistent_font_size",
        "inconsistent_spacing",
        "wrong_vertical_alignment",
        "arrow_disconnected",
        "zero_gap",
        "small_font",
        "insufficient_padding",
        "content_too_sparse",
        "content_too_dense",
        "unbalanced_spacing",
        "inconsistent_padding",
    ]
    severity: Literal["high", "medium", "low"]
    element_type: Literal["textbox", "shape"]
    element_index: int = Field(ge=0)
    description: str
    suggested_fix: str


class VisualQAOutput(BaseModel):
    """Visual QA 스크린샷 분석 결과."""

    has_issues: bool
    issues: list[VisualQAIssue] = Field(default_factory=list)
    overall_quality: Literal["good", "needs_improvement", "poor"]


def _convert_paragraphs(paragraphs: list[ParagraphOutput]) -> list[PptxParagraph]:
    """ParagraphOutput 리스트를 PptxParagraph dataclass 리스트로 변환한다."""
    return [
        PptxParagraph(
            runs=[
                PptxTextRun(
                    text=r.text,
                    font_size_pt=r.font_size_pt,
                    color=r.color,
                    bold=r.bold,
                    italic=r.italic,
                    font_family=r.font_family,
                    href=r.href,
                )
                for r in p.runs
            ],
            bullet_level=p.bullet_level,
            alignment=p.alignment,
        )
        for p in paragraphs
    ]


class OverflowContent(BaseModel):
    """슬라이드에 담지 못한 초과 컨텐츠. 별도 슬라이드로 삽입을 제안한다."""

    title: str = Field(description="초과 컨텐츠로 만들 슬라이드 제목")
    content_summary: str = Field(description="초과 컨텐츠 요약 (outline 형식)")
    component_hint: str = Field(default="bullets", description="권장 component_hint")
    insert_after: int = Field(
        description="삽입 권장 위치 (현재 슬라이드의 1-based index)"
    )
    reason: str = Field(description="왜 현재 슬라이드에 담지 못했는지 짧은 설명")


class SlideSpecOutput(BaseModel):
    """LLM structured_output용 슬라이드 스펙 Pydantic 모델."""

    background_color: str | None = None
    speaker_notes: str = ""
    textboxes: list[TextBoxOutput] = Field(default_factory=list)
    shapes: list[ShapeOutput] = Field(default_factory=list)
    overflow: list[OverflowContent] = Field(default_factory=list)

    def to_dataclass(self) -> PptxSlideSpec:
        """Pydantic 모델을 기존 PptxSlideSpec dataclass로 변환."""
        textboxes = [
            PptxTextBox(
                left_px=tb.left_px,
                top_px=tb.top_px,
                width_px=tb.width_px,
                height_px=tb.height_px,
                paragraphs=_convert_paragraphs(tb.paragraphs),
                line_spacing_pt=tb.line_spacing_pt,
                vertical_alignment=tb.vertical_alignment,
                padding_left_px=tb.padding_left_px,
                padding_right_px=tb.padding_right_px,
                padding_top_px=tb.padding_top_px,
                padding_bottom_px=tb.padding_bottom_px,
            )
            for tb in self.textboxes
        ]
        shapes = [
            PptxShape(
                left_px=s.left_px,
                top_px=s.top_px,
                width_px=s.width_px,
                height_px=s.height_px,
                shape_type=s.shape_type,
                fill_color=s.fill_color,
                border_color=s.border_color,
                border_width_pt=s.border_width_pt,
                corner_radius_px=s.corner_radius_px,
                text=s.text,
                text_color=s.text_color,
                text_size_pt=s.text_size_pt,
                text_bold=s.text_bold,
                paragraphs=_convert_paragraphs(s.paragraphs),
                line_spacing_pt=s.line_spacing_pt,
                padding_left_px=s.padding_left_px,
                padding_right_px=s.padding_right_px,
                padding_top_px=s.padding_top_px,
                padding_bottom_px=s.padding_bottom_px,
                vertical_alignment=s.vertical_alignment,
                end_arrow=s.end_arrow,
                start_arrow=s.start_arrow,
                dash_style=s.dash_style,
                svg_path=s.svg_path,
                autofit_mode=s.autofit_mode,
            )
            for s in self.shapes
        ]
        return PptxSlideSpec(
            background_color=self.background_color,
            textboxes=textboxes,
            shapes=shapes,
            images=[],
            speaker_notes=self.speaker_notes,
        )


# --- Design Review models ---


class DesignReviewIssue(BaseModel):
    """Design review에서 발견된 개별 이슈."""

    rule_id: Literal[
        "font_size_floor",
        "lr_font_consistency",
        "vstack_overlap",
        "vstack_height_uniformity",
        "vstack_gap_uniformity",
        "lr_bottom_alignment",
        "same_level_overlap",
    ]
    severity: Literal["high", "medium"]
    description: str


class DesignReviewOutput(BaseModel):
    """Design spec 리뷰 결과."""

    has_high_severity: bool
    issues: list[DesignReviewIssue] = Field(default_factory=list)
