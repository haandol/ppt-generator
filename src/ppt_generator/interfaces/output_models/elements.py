"""텍스트·도형 응답과 공통 렌더 모델 변환."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
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
    grid_cell: str | None = None
    component_id: str | None = None  # design_doc.sections[].components[].id 참조


class ShapeOutput(BaseModel):
    """LLM 출력용 도형 Pydantic 모델."""

    left_px: float = Field(
        description=(
            "Shape left coordinate. For line shapes this is the minimum x of the "
            "two endpoints, not stroke thickness."
        )
    )
    top_px: float = Field(
        description=(
            "Shape top coordinate. For line shapes this is the minimum y of the "
            "two endpoints, not stroke thickness."
        )
    )
    width_px: float = Field(
        description=(
            "Shape width. For line shapes this is the signed horizontal endpoint "
            "delta: use 0 for an exactly vertical line. Never encode stroke "
            "thickness here."
        )
    )
    height_px: float = Field(
        description=(
            "Shape height. For line shapes this is the signed vertical endpoint "
            "delta: use 0 for an exactly horizontal line. Never encode stroke "
            "thickness here."
        )
    )
    shape_type: Literal["rectangle", "rounded_rectangle", "ellipse", "line"] = (
        "rectangle"
    )
    fill_color: str | None = None
    border_color: str | None = None
    border_width_pt: float | None = Field(
        default=None,
        description=(
            "Border or line stroke thickness in points. For line shapes this is "
            "the only field that controls stroke thickness."
        ),
    )
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
    end_arrow: bool = Field(
        default=False,
        description=(
            "Place an arrowhead at the line end endpoint. That endpoint must stop "
            "on the target box boundary and must not penetrate the box."
        ),
    )
    start_arrow: bool = Field(
        default=False,
        description=(
            "Place an arrowhead at the line start endpoint. That endpoint must stop "
            "on the target box boundary and must not penetrate the box."
        ),
    )
    dash_style: Literal["solid", "dash", "dot"] | None = None
    svg_path: str | None = None
    # 결정 14: 기본 shrink_text (높이 고정, 폰트 자동 축소)
    autofit_mode: Literal["expand_height", "shrink_text"] = "shrink_text"
    grid_cell: str | None = None
    component_id: str | None = None  # design_doc.sections[].components[].id 참조


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


def textbox_output_to_dataclass(tb: TextBoxOutput) -> PptxTextBox:
    """TextBoxOutput → PptxTextBox 변환 (component_id 보존)."""
    return PptxTextBox(
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
        z_index=getattr(tb, "z_index", None),
        grid_cell=tb.grid_cell,
        component_id=tb.component_id,
    )


def shape_output_to_dataclass(s: ShapeOutput) -> PptxShape:
    """ShapeOutput → PptxShape 변환 (component_id 보존)."""
    return PptxShape(
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
        z_index=getattr(s, "z_index", None),
        grid_cell=s.grid_cell,
        component_id=s.component_id,
    )
