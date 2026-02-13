from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ScriptRequest:
    outline: "OutlineResponse"


@dataclass(frozen=True)
class ScriptResponse:
    slides: list["SlideOutline"]


@dataclass(frozen=True)
class SlideOutline:
    title: str
    content_summary: str
    component_hint: str = "bullets"
    speaker_notes: str = ""


@dataclass(frozen=True)
class OutlineRequest:
    topic: str
    num_slides: int


@dataclass(frozen=True)
class OutlineResponse:
    slides: list[SlideOutline]


@dataclass(frozen=True)
class ExportPptxRequest:
    session_id: str


@dataclass(frozen=True)
class ExportPptxResponse:
    pptx_path: str


@dataclass(frozen=True)
class SlidesRequest:
    slides: list[SlideOutline]


@dataclass(frozen=True)
class SlidesResponse:
    session_id: str
    html: str


@dataclass
class ProjectMetadata:
    topic: str = ""
    num_slides: int = 0
    steps_completed: dict[str, str] = field(default_factory=dict)


# --- PPTX 요소 스키마 (LLM 변환용) ---


@dataclass(frozen=True)
class PptxTextRun:
    """텍스트 런: 동일한 서식이 적용된 텍스트 조각."""

    text: str
    font_size_pt: int | None = None
    color: str | None = None
    bold: bool = False
    italic: bool = False
    font_family: str | None = None


@dataclass(frozen=True)
class PptxParagraph:
    """단락: 하나 이상의 텍스트 런으로 구성."""

    runs: list[PptxTextRun] = field(default_factory=list)
    bullet_level: int = -1  # -1 = 불릿 아님, 0 = 1단계, 1 = 2단계
    alignment: str | None = None  # 'left', 'center', 'right'


@dataclass(frozen=True)
class PptxTextBox:
    """텍스트박스: 위치/크기와 단락 목록."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    paragraphs: list[PptxParagraph] = field(default_factory=list)
    line_spacing_pt: float | None = None  # pt 단위 줄간격
    vertical_alignment: str | None = None  # "top", "middle", "bottom"


@dataclass(frozen=True)
class PptxShape:
    """도형: 위치/크기, 배경색, 내부 텍스트(옵션).

    shape_type: "rectangle" | "rounded_rectangle" | "ellipse" | "line"
    """

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    shape_type: str = "rectangle"
    fill_color: str | None = None
    border_color: str | None = None
    border_width_pt: float | None = None
    corner_radius_px: float | None = None
    text: str | None = None
    text_color: str | None = None
    text_size_pt: int | None = None
    text_bold: bool = False
    paragraphs: list[PptxParagraph] = field(default_factory=list)
    line_spacing_pt: float | None = None
    padding_left_px: float | None = None
    padding_right_px: float | None = None
    padding_top_px: float | None = None
    padding_bottom_px: float | None = None
    vertical_alignment: str | None = None  # "top", "middle", "bottom"


@dataclass(frozen=True)
class PptxImage:
    """이미지: 위치/크기와 PNG 바이트 데이터."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    image_bytes: bytes = b""


@dataclass(frozen=True)
class PptxSlideSpec:
    """슬라이드 전체 스펙: 배경색, 텍스트박스 목록, 도형 목록, 이미지 목록."""

    background_color: str | None = None
    textboxes: list[PptxTextBox] = field(default_factory=list)
    shapes: list[PptxShape] = field(default_factory=list)
    images: list[PptxImage] = field(default_factory=list)
    speaker_notes: str = ""


# --- 디자인 스펙 스키마 ---


@dataclass(frozen=True)
class DesignSpec:
    """프레젠테이션 전체 디자인 스펙."""

    slides: list[PptxSlideSpec] = field(default_factory=list)


@dataclass(frozen=True)
class DesignSpecRequest:
    """디자인 스펙 생성 입력."""

    slides: list[SlideOutline] = field(default_factory=list)


@dataclass(frozen=True)
class DesignSpecResponse:
    """디자인 스펙 생성 출력."""

    design_spec: DesignSpec = field(default_factory=DesignSpec)


# --- Pydantic 출력 모델 (strands structured_output용) ---


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
    vertical_alignment: Literal["top", "middle", "bottom"] | None = None


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
    vertical_alignment: Literal["top", "middle", "bottom"] | None = None


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
