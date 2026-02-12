from __future__ import annotations

from dataclasses import dataclass, field


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
    layout_index: int
    component_hint: str = "bullets"


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


@dataclass(frozen=True)
class PptxParagraph:
    """단락: 하나 이상의 텍스트 런으로 구성."""

    runs: list[PptxTextRun] = field(default_factory=list)
    bullet_level: int = -1  # -1 = 불릿 아님, 0 = 1단계, 1 = 2단계


@dataclass(frozen=True)
class PptxTextBox:
    """텍스트박스: 위치/크기와 단락 목록."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    paragraphs: list[PptxParagraph] = field(default_factory=list)


@dataclass(frozen=True)
class PptxShape:
    """도형: 위치/크기, 배경색, 내부 텍스트(옵션)."""

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


@dataclass(frozen=True)
class PptxSlideSpec:
    """슬라이드 전체 스펙: 배경색, 텍스트박스 목록, 도형 목록."""

    background_color: str | None = None
    textboxes: list[PptxTextBox] = field(default_factory=list)
    shapes: list[PptxShape] = field(default_factory=list)
