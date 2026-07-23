from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlideOutline:
    title: str
    content_summary: str
    component_hint: str = "bullets"
    speaker_notes: str = ""
    slide_type: str = "content"
    slide_index: int = -1
    layout_plan: str = ""


@dataclass(frozen=True)
class OutlineRequest:
    topic: str
    num_slides: int
    audience_type: str = "general"
    presentation_minutes: int = 15
    purpose: str = ""
    presenter_name: str = ""
    presenter_title: str = ""
    presenter_org: str = ""


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
    presenter_name: str = ""
    presenter_title: str = ""
    presenter_org: str = ""


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
    href: str | None = None
    # 원본 폰트 이름 (예: "Amazon Ember Display"). import 시 보존해 CSS/PPTX 에
    # 실제 폰트를 지정한다. font_family("monospace" sentinel)와 독립적이다.
    font_name: str | None = None


@dataclass(frozen=True)
class PptxParagraph:
    """Paragraph: composed of one or more text runs."""

    runs: list[PptxTextRun] = field(default_factory=list)
    bullet_level: int = -1  # -1 = no bullet, 0 = level 1, 1 = level 2
    alignment: str | None = None  # 'left', 'center', 'right'
    space_before_pt: float | None = None
    space_after_pt: float | None = None


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
    # autofit 모드: "shrink"=박스 초과 시 폰트 축소(기본, LLM 생성 슬라이드용),
    # "none"=축소 없이 넘침 허용(PPTX noAutofit), "resize"=박스가 텍스트에 맞춤(spAutoFit).
    # import 시 <a:bodyPr> 에서 추출. "none"/"resize" 는 렌더 시 shrink 를 건너뛴다.
    autofit: str = "shrink"
    # normAutofit 의 fontScale(0~1). PPTX 가 저장한 실제 축소율을 그대로 적용한다.
    # 값이 있으면 렌더러의 재계산 shrink 대신 이 비율을 쓴다(PowerPoint 실제 동작).
    autofit_font_scale: float | None = None
    z_index: int | None = None  # rendering order (lower = behind, higher = front)
    grid_cell: str | None = None  # GridPlan cell id this element belongs to
    component_id: str | None = (
        None  # DesignDoc.sections[].components[].id 참조. 의미 단위 부분 수정 시 사용
    )


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
    svg_path: str | None = (
        None  # SVG path data for custom freeform shapes (shape_type="custom")
    )
    # 꺾인 커넥터(bentConnector)의 폴리라인 꼭짓점. bbox(left/top/width/height) 대비
    # 정규화 좌표 [[fx, fy], ...] (0~1). shape_type="line" 과 함께 쓰이며, 값이 있으면
    # 직선 대신 직각(elbow) 폴리라인으로 렌더한다. end_arrow/start_arrow/dash_style 적용.
    elbow_points: list[list[float]] | None = None
    # 결정 14: shape autofit 기본은 "shrink_text" (높이 고정, 폰트 자동 축소).
    # expand_height 는 height 가 늘어나며 sibling 과 충돌하기 쉬워 grid 균일성을 깬다.
    # shrink_text 는 카드 높이 통일을 보장하고, 폰트가 작아져도 font-range lint 가
    # 10pt 미만은 잡아준다. 시각적 잘림을 피하는 대신 폰트 크기를 양보하는 정책.
    autofit_mode: str = "shrink_text"  # "shrink_text" (default) | "expand_height"
    z_index: int | None = None  # rendering order (lower = behind, higher = front)
    grid_cell: str | None = None  # GridPlan cell id this element belongs to
    component_id: str | None = None  # DesignDoc.sections[].components[].id 참조
    # 도형 회전(시계방향 degree). PPTX xfrm@rot(60000분의 1도)에서 임포트한다.
    # CSS transform:rotate 로 bbox 중심 기준 회전(PowerPoint 와 동일 기준)을 적용한다.
    # 회전 커넥터(예: rot=270 인 elbow/freeform)를 무시하면 세로선이 캔버스 밖으로
    # 나가 사라지거나 방향이 어긋난다.
    rotation: float = 0.0


@dataclass(frozen=True)
class PptxImage:
    """Image: position/size and PNG byte data."""

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    image_bytes: bytes = b""
    src: str = ""  # 이미지 파일 상대경로 (e.g. "images/slide_01_img_01.png")
    image_path: str = ""  # 이미지 절대경로 (외부 파일 참조 시 사용)
    corner_radius_px: float | None = None  # 둥근 모서리 반경
    z_index: int | None = None  # rendering order (lower = behind, higher = front)
    grid_cell: str | None = None  # GridPlan cell id this element belongs to


@dataclass(frozen=True)
class GridCell:
    """A single cell of GridPlan.

    Identifies a rectangular slot inside a region (header/content/footer).
    Coordinates are derived from the parent region + content_columns/content_rows;
    this dataclass only carries the abstract location.
    """

    id: str
    region: str  # "header" | "content" | "footer"
    row: int = 1  # 1-based
    col: int = 1  # 1-based
    row_span: int = 1
    col_span: int = 1
    role: str = ""  # free-form label for debugging/lint messages


@dataclass(frozen=True)
class GridPlan:
    """Slide-level grid plan.

    Declares which y-axis regions the slide uses, how the content region is
    subdivided into rows/columns, and the list of cells that elements can
    reference via PptxTextBox.grid_cell / PptxShape.grid_cell.
    """

    regions: list[str] = field(
        default_factory=list
    )  # subset of ["header", "content", "footer"]
    content_columns: int = 1  # 1..4
    content_rows: int = 1  # 1..N
    cells: list[GridCell] = field(default_factory=list)


@dataclass(frozen=True)
class LayoutNode:
    """슬라이드 레이아웃 트리의 노드. 임의 깊이의 의미 단위 묶음을 표현한다.

    kind 별 의미:
      - "section": 슬라이드의 큰 의미 영역 (보통 1개 이상의 grid cell 과 매핑)
      - "group": section 안의 중간 묶음 (예: 다이어그램 안의 LLM 서브시스템)
      - "component": 리프. 실제 textbox/shape 가 component_id 로 참조하는 노드

    id 는 트리 path 형태 (e.g. "right_diagram", "right_diagram.llm_box",
    "right_diagram.functions.web_search"). lower_snake_case + dot 구분.
    role 은 자유 라벨 ("card_title", "axis_label", "llm_box",...).
    cell_id 는 연결된 GridPlan cell id (없으면 빈 문자열).
    children 는 비어 있으면 leaf (component).

    좌표 필드 (left_px/top_px/width_px/height_px) 는 노드의 bounding box 를
    명시한다. section/group 은 자식들이 차지하는 영역 전체, component 는 해당
    textbox/shape 와 동일한 bbox 가 들어간다. 자식 bbox 의 합집합은 부모 bbox
    안에 들어가야 한다 (lint 로 검증 가능). LLM 부분 수정 시 "이 노드 영역만
    이동/리사이즈" 가 자연스럽게 가능해진다.
    """

    id: str
    kind: str = "component"  # "section" | "group" | "component"
    role: str = ""
    description: str = ""
    cell_id: str = ""
    left_px: float | None = None
    top_px: float | None = None
    width_px: float | None = None
    height_px: float | None = None
    children: list["LayoutNode"] = field(default_factory=list)


@dataclass(frozen=True)
class DesignDoc:
    """슬라이드의 구조/의도 메타데이터.

    `speaker_notes` 와 분리되어 발표 narrative 가 아닌 *디자인 의도* 만 담는다.
    `layout` 은 슬라이드 레이아웃 트리이며 (section → group → component) LLM
    부분 수정 시 의미 단위 path 로 요소를 지칭하기 위한 인덱스 역할이다.
    """

    topic: str = ""
    layout_summary: str = ""
    layout: list[LayoutNode] = field(default_factory=list)


@dataclass(frozen=True)
class PptxSlideSpec:
    """Full slide spec: background color, textbox list, shape list, image list."""

    background_color: str | None = None
    background_image_bytes: bytes = b""  # in-memory PNG bytes (not serialized)
    background_image_src: str = ""  # relative path (e.g. "images/slide_01_bg.png")
    textboxes: list[PptxTextBox] = field(default_factory=list)
    shapes: list[PptxShape] = field(default_factory=list)
    images: list[PptxImage] = field(default_factory=list)
    speaker_notes: str = ""
    slide_type: str = "content"
    grid_plan: GridPlan | None = None
    design_doc: DesignDoc | None = None


# --- Design spec schema ---


@dataclass(frozen=True)
class DesignSpec:
    """Full presentation design spec."""

    slides: list[PptxSlideSpec] = field(default_factory=list)
