from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScriptRequest:
    outline: "OutlineResponse"
    audience_type: str = "general"
    presentation_minutes: int = 15
    purpose: str = ""


@dataclass(frozen=True)
class ScriptResponse:
    slides: list["SlideOutline"]


@dataclass(frozen=True)
class SlideOutline:
    title: str
    content_summary: str
    component_hint: str = "bullets"
    speaker_notes: str = ""
    slide_type: str = "content"
    slide_index: int = -1


@dataclass(frozen=True)
class OutlineRequest:
    topic: str
    num_slides: int
    audience_type: str = "general"
    presentation_minutes: int = 15
    purpose: str = ""


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
    slide_htmls: list[str]
    container_html: str


@dataclass
class ProjectMetadata:
    topic: str = ""
    num_slides: int = 0
    steps_completed: dict[str, str] = field(default_factory=dict)
    audience_type: str = "general"
    presentation_minutes: int = 15
    purpose: str = ""
    source: str = "generated"  # "generated" | "imported"


# --- PPTX element schemas (for LLM conversion) ---


@dataclass(frozen=True)
class PptxTextRun:
    """Text run: a text fragment with uniform formatting."""

    text: str
    font_size_pt: int | None = None
    color: str | None = None
    bold: bool = False
    italic: bool = False
    font_family: str | None = None


@dataclass(frozen=True)
class PptxParagraph:
    """Paragraph: composed of one or more text runs."""

    runs: list[PptxTextRun] = field(default_factory=list)
    bullet_level: int = -1  # -1 = no bullet, 0 = level 1, 1 = level 2
    alignment: str | None = None  # 'left', 'center', 'right'


@dataclass(frozen=True)
class PptxTextBox:
    """Textbox: position/size and list of paragraphs."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    paragraphs: list[PptxParagraph] = field(default_factory=list)
    line_spacing_pt: float | None = None  # line spacing in pt
    vertical_alignment: str = "top"  # "top", "middle", "bottom"
    padding_left_px: float | None = None
    padding_right_px: float | None = None
    padding_top_px: float | None = None
    padding_bottom_px: float | None = None
    z_index: int | None = None  # rendering order (lower = behind, higher = front)


@dataclass(frozen=True)
class PptxShape:
    """Shape: position/size, background color, inner text (optional).

    shape_type:
      Basic: "rectangle" | "rounded_rectangle" | "ellipse" | "line"
      Arrows: "up_arrow" | "down_arrow" | "left_arrow" | "right_arrow" | "chevron"
      Polygons: "triangle" | "diamond" | "pentagon" | "hexagon" | "trapezoid"
                | "parallelogram" | "cross"
      Stars: "star_4" | "star_5" | "heart"
      Flowchart: "flowchart_process" | "flowchart_decision" | "flowchart_terminator"
      Custom: "custom" (requires svg_path)
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
    vertical_alignment: str = "top"  # "top", "middle", "bottom"
    end_arrow: bool = False  # arrowhead at end point (right/bottom)
    start_arrow: bool = False  # arrowhead at start point (left/top)
    dash_style: str | None = None  # "solid", "dash", "dot" (line shape only)
    svg_path: str | None = None  # SVG path data for custom freeform shapes (shape_type="custom")
    autofit_mode: str = "expand_height"  # "expand_height" (default) | "shrink_text" (keep height, shrink font)
    z_index: int | None = None  # rendering order (lower = behind, higher = front)


@dataclass(frozen=True)
class PptxImage:
    """Image: position/size and PNG byte data."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    image_bytes: bytes = b""
    src: str = ""  # 이미지 파일 상대경로 (e.g. "images/slide_01_img_01.png")
    z_index: int | None = None  # rendering order (lower = behind, higher = front)


@dataclass(frozen=True)
class PptxSlideSpec:
    """Full slide spec: background color, textbox list, shape list, image list."""

    background_color: str | None = None
    textboxes: list[PptxTextBox] = field(default_factory=list)
    shapes: list[PptxShape] = field(default_factory=list)
    images: list[PptxImage] = field(default_factory=list)
    speaker_notes: str = ""
    slide_type: str = "content"


# --- Design spec schema ---


@dataclass(frozen=True)
class DesignSpec:
    """Full presentation design spec."""

    slides: list[PptxSlideSpec] = field(default_factory=list)


