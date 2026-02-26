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
    shape_type: Literal["rectangle", "rounded_rectangle", "ellipse", "line"] = "rectangle"
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


class SlideSpecOutput(BaseModel):
    """LLM structured_output용 슬라이드 스펙 Pydantic 모델."""

    background_color: str | None = None
    speaker_notes: str = ""
    textboxes: list[TextBoxOutput] = Field(default_factory=list)
    shapes: list[ShapeOutput] = Field(default_factory=list)

    def to_dataclass(self) -> PptxSlideSpec:
        """Pydantic 모델을 기존 PptxSlideSpec dataclass로 변환."""
        textboxes = [
            PptxTextBox(
                left_px=tb.left_px,
                top_px=tb.top_px,
                width_px=tb.width_px,
                height_px=tb.height_px,
                paragraphs=[
                    PptxParagraph(
                        runs=[
                            PptxTextRun(
                                text=r.text,
                                font_size_pt=r.font_size_pt,
                                color=r.color,
                                bold=r.bold,
                                italic=r.italic,
                                font_family=r.font_family,
                            )
                            for r in p.runs
                        ],
                        bullet_level=p.bullet_level,
                        alignment=p.alignment,
                    )
                    for p in tb.paragraphs
                ],
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
                paragraphs=[
                    PptxParagraph(
                        runs=[
                            PptxTextRun(
                                text=r.text,
                                font_size_pt=r.font_size_pt,
                                color=r.color,
                                bold=r.bold,
                                italic=r.italic,
                                font_family=r.font_family,
                            )
                            for r in p.runs
                        ],
                        bullet_level=p.bullet_level,
                        alignment=p.alignment,
                    )
                    for p in s.paragraphs
                ],
                line_spacing_pt=s.line_spacing_pt,
                padding_left_px=s.padding_left_px,
                padding_right_px=s.padding_right_px,
                padding_top_px=s.padding_top_px,
                padding_bottom_px=s.padding_bottom_px,
                vertical_alignment=s.vertical_alignment,
                end_arrow=s.end_arrow,
                start_arrow=s.start_arrow,
                dash_style=s.dash_style,
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
