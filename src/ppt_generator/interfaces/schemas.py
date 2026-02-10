from dataclasses import dataclass


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
class SlideOutline:
    title: str
    bullets: list[str]
    image_idea: str
    layout_type: str
    speaker_notes: str


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
