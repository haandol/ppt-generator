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
