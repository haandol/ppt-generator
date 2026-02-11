from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScriptRequest:
    topic: str
    num_slides: int


@dataclass(frozen=True)
class ScriptResponse:
    script: str
    topic: str
    num_slides: int


@dataclass(frozen=True)
class SlideElement:
    """Freeform 슬라이드의 개별 요소 (텍스트박스, 이미지, 도형)."""

    type: str  # "textbox", "image", "shape"
    left: float  # 인치 단위, 0 ~ 13.333
    top: float  # 인치 단위, 0 ~ 7.5
    width: float  # 인치 단위
    height: float  # 인치 단위
    content: str = ""
    font_size_pt: int = 16
    bold: bool = False


@dataclass(frozen=True)
class SlideOutline:
    title: str
    bullets: list[str]
    image_idea: str
    layout_type: str
    speaker_notes: str
    elements: list[SlideElement] = field(default_factory=list)


@dataclass(frozen=True)
class OutlineRequest:
    script: str


@dataclass(frozen=True)
class OutlineResponse:
    slides: list[SlideOutline]


@dataclass(frozen=True)
class ImageRequest:
    slides: list[SlideOutline]


@dataclass(frozen=True)
class ImageResult:
    slide_index: int
    image_path: str


@dataclass(frozen=True)
class ImageResponse:
    images: list[ImageResult]


@dataclass(frozen=True)
class PptxRequest:
    slides: list[SlideOutline]
    image_paths: dict[int, str]


@dataclass(frozen=True)
class PptxResponse:
    pptx_path: str
