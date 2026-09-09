"""LLM 출력용 Pydantic 모델.

두 역할을 한다:
- ``prepare_*`` 도구가 ``model_json_schema()`` 로 출력 스키마를 만들어 클라이언트에
  넘긴다 (클라이언트가 따라야 할 형식).
- ``ingest_*`` 도구가 ``model_validate()`` 로 클라이언트 JSON 을 검증한 뒤
  ``to_dataclass()`` 로 내부 dataclass(PptxSlideSpec)로 변환한다.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ppt_generator.interfaces.line_geometry import (
    ARROW_ENDPOINT_BOUNDARY_TOLERANCE_PX,
    line_endpoints,
)
from ppt_generator.interfaces.layout_derivation import derive_layout_bboxes
from ppt_generator.interfaces.schemas import (
    DesignDoc,
    GridCell,
    GridPlan,
    LayoutNode,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)

ComponentHint = Literal[
    "bullets",
    "two_column",
    "vs_comparison",
    "step_cards",
    "code_block",
    "arch_diagram",
    "pipeline",
    "quote",
    "summary_grid",
    "agenda",
    "info_cards",
    "feature_list",
    "cta",
    "process_flow",
    "quote_code",
    "concept_list",
    "custom",
]


class SlideOutlineOutput(BaseModel):
    """클라이언트가 생성하는 단일 슬라이드 아웃라인."""

    model_config = ConfigDict(extra="forbid")

    title: str
    content_summary: str
    component_hint: ComponentHint
    slide_type: Literal["title", "closing", "content"]
    layout_plan: str
    speaker_notes: str
    source_refs: list[str]
    assumptions: list[str]
    slide_index: int | None = None


class OutlineOutput(BaseModel):
    """클라이언트가 생성하는 전체 아웃라인."""

    model_config = ConfigDict(extra="forbid")

    slides: list[SlideOutlineOutput]

    @model_validator(mode="after")
    def validate_required_composition(self) -> "OutlineOutput":
        """필수 발표 골격과 슬라이드 수를 저장 전에 검증한다."""
        count = len(self.slides)
        if not 4 <= count <= 20:
            raise ValueError("outline must contain 4~20 slides")
        if self.slides[0].slide_type != "title":
            raise ValueError("slide 1 must be title")
        agenda = self.slides[1]
        if agenda.slide_type != "content" or agenda.component_hint != "agenda":
            raise ValueError("slide 2 must be a content agenda slide")
        if self.slides[-1].slide_type != "closing":
            raise ValueError("last slide must be closing")
        if any(slide.slide_type != "content" for slide in self.slides[2:-1]):
            raise ValueError("slides between agenda and closing must be content")
        return self


class DesignRegionOutput(BaseModel):
    """덱 전체가 공유하는 세로 영역."""

    model_config = ConfigDict(extra="forbid")

    top_px: float = Field(ge=0)
    height_px: float = Field(gt=0)


class DesignThemeOutput(BaseModel):
    """DESIGN.md 초안의 수치 디자인 시스템."""

    model_config = ConfigDict(extra="forbid")

    background_color: str
    background_image: Literal["gradient", "none"] = "gradient"
    text_colors: list[str]
    title_font_pt: int = Field(ge=28, le=36)
    body_font_pt: int = Field(ge=16, le=22)
    card_fills: list[str]
    card_borders: list[str]
    header_region: DesignRegionOutput
    content_region: DesignRegionOutput
    footer_region: DesignRegionOutput

    @model_validator(mode="after")
    def validate_region_order(self) -> "DesignThemeOutput":
        header_bottom = self.header_region.top_px + self.header_region.height_px
        content_bottom = self.content_region.top_px + self.content_region.height_px
        footer_bottom = self.footer_region.top_px + self.footer_region.height_px
        if header_bottom > self.content_region.top_px:
            raise ValueError("header_region overlaps content_region")
        if content_bottom > self.footer_region.top_px:
            raise ValueError("content_region overlaps footer_region")
        if footer_bottom > 688:
            raise ValueError("footer_region exceeds the 688px safe area")
        return self


class DesignPageRequestOutput(BaseModel):
    """특정 슬라이드에만 적용할 디자인 요청."""

    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    title: str = Field(min_length=1)
    request: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_nonblank_request(self) -> "DesignPageRequestOutput":
        """빈 요청은 거부하되 바인딩 키인 원본 제목을 변경하지 않는다."""
        if not self.title.strip() or not self.request.strip():
            raise ValueError("page request title and request must not be blank")
        return self


class AntiSlopGuardrailsOutput(BaseModel):
    """DESIGN.md에 저장되는 덱별 AI Slop 방지 기준."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject_specificity: str = Field(min_length=1)
    visual_hierarchy: str = Field(min_length=1)
    layout_rhythm: str = Field(min_length=1)
    decoration_policy: str = Field(min_length=1)
    content_grounding: str = Field(min_length=1)
    max_consecutive_same_archetype: Literal[2] = Field(
        default=2,
        description="Legacy client field. Repetition is reviewed for purpose, not prohibited.",
    )


class DesignDocDraftOutput(BaseModel):
    """DESIGN.md 초안 생성 단계의 전체 출력."""

    model_config = ConfigDict(extra="forbid")

    theme: DesignThemeOutput
    tone: str
    anti_slop: AntiSlopGuardrailsOutput
    page_requests: list[DesignPageRequestOutput]


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


class GridCellOutput(BaseModel):
    """LLM 출력용 GridCell Pydantic 모델."""

    id: str
    region: Literal["header", "content", "footer"] = "content"
    row: int = Field(default=1, ge=1)
    col: int = Field(default=1, ge=1)
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
    role: str = ""


class GridLayoutOutput(BaseModel):
    """Stage 2: 슬라이드의 거시 레이아웃 결정.

    어떤 region 을 쓸지, content 를 몇 행/열로 나눌지의 최상위 결정.
    이 결정 후 cell_assignment 단계에서 cell 정의로 내려간다.
    """

    regions: list[Literal["header", "content", "footer"]] = Field(default_factory=list)
    content_columns: int = Field(default=1, ge=1, le=4)
    content_rows: int = Field(default=1, ge=1)


class GridCellAssignmentOutput(BaseModel):
    """Stage 3: grid_layout 위에서 각 cell 의 위치/span/region/role 할당.

    Stage 2 의 layout 을 받아 실제 cell 목록을 정의한다. 이 단계 후 element 단계에서
    각 textbox/shape 가 cell id 를 참조해 좌표·스타일을 채운다.
    """

    cells: list[GridCellOutput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_cell_ids(self) -> "GridCellAssignmentOutput":
        duplicates = _duplicate_values([cell.id for cell in self.cells])
        if duplicates:
            raise ValueError(f"grid cell ids must be unique: {duplicates}")
        return self


# --- DesignDoc (의미 단위 레이아웃 트리) ---


class LayoutNodeOutput(BaseModel):
    """슬라이드 레이아웃 트리 노드 (flat 표현).

    트리 구조이지만 LLM structured output 의 schema 재귀 제약 때문에 평탄한
    리스트 + parent_id 참조로 직렬화한다. 변환 시 parent_id 를 이용해 트리로
    재구성한다. id 자체가 dot-joined path (e.g. "right_diagram.functions.web_search")
    이므로 path 에서 parent 를 유추할 수도 있지만, 명시적 parent_id 가 더 안전하다.

    kind:
      - "section": 큰 의미 영역 (보통 grid cell 과 매핑, parent_id 없음)
      - "group": section 안의 중간 묶음 (옵션)
      - "component": 리프. textbox/shape 가 component_id 로 참조

    bbox 는 LLM 응답에 포함하지 않는다. 서버가 component_id 로 연결된 실제 element
    좌표에서 leaf → group → section 순으로 파생한다.
    """

    id: str
    parent_id: str | None = ""  # 부모 노드 id (빈 문자열 또는 null 이면 root section)
    kind: Literal["section", "group", "component"] = "component"
    role: str | None = (
        ""  # "llm_box" | "context_bus" | "function_card" | "card_title" |...
    )
    description: str | None = ""  # 1-2 문장 의미 설명
    cell_id: str | None = ""  # GridPlan.cells[].id (없거나 null 가능)


class DesignDocOutput(BaseModel):
    """슬라이드의 구조/의도 메타데이터.

    `speaker_notes` 와 분리해 *디자인 의도* 만 담는다. LLM 부분 수정 요청 시
    트리 path 로 요소를 지칭하기 위한 인덱스 역할.
    `layout` 은 flat 노드 리스트. 변환 시 parent_id 로 트리 재구성.
    """

    topic: str = Field(min_length=1)
    layout_summary: str = Field(min_length=1)
    layout: list[LayoutNodeOutput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_layout_references(self) -> "DesignDocOutput":
        duplicates = _duplicate_values([node.id for node in self.layout])
        if duplicates:
            raise ValueError(f"layout node ids must be unique: {duplicates}")

        seen: set[str] = set()
        roots = 0
        child_count: Counter[str] = Counter()
        for node in self.layout:
            parent_id = node.parent_id or ""
            if parent_id and parent_id not in seen:
                raise ValueError(
                    f"layout node {node.id!r} references missing or later parent "
                    f"{parent_id!r}"
                )
            if not parent_id:
                roots += 1
                if node.kind != "section":
                    raise ValueError("root layout nodes must be sections")
            else:
                child_count[parent_id] += 1
            seen.add(node.id)
        for node in self.layout:
            if node.kind in {"section", "group"} and child_count[node.id] == 0:
                raise ValueError(f"{node.kind} node {node.id!r} must have children")
            if node.kind == "component" and child_count[node.id] > 0:
                raise ValueError(f"component node {node.id!r} cannot have children")
        if roots == 0:
            raise ValueError("design_doc must contain at least one root section")
        if not self.topic.strip() or not self.layout_summary.strip():
            raise ValueError("design_doc topic and layout_summary must be non-empty")
        return self


def _duplicate_values(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


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
        "label_intrusion",
        "decoration_overlap",
        "arrow_through_card",
        "orphan_label_no_arrow",
        "label_line_overlap",
        "hidden_decorative_strip",
        "wrong_z_order",
    ]
    severity: Literal["high", "medium", "low"]
    element_type: Literal["textbox", "shape"]
    element_index: int = Field(ge=0)
    related_element_type: Literal["textbox", "shape"] | None = None
    related_element_index: int | None = Field(default=None, ge=0)
    description: str
    suggested_fix: str

    @model_validator(mode="after")
    def validate_related_element(self) -> "VisualQAIssue":
        if (self.related_element_type is None) != (self.related_element_index is None):
            raise ValueError(
                "related_element_type and related_element_index must be set together"
            )
        return self


class VisualQAOutput(BaseModel):
    """Visual QA 스크린샷 분석 결과."""

    has_issues: bool
    issues: list[VisualQAIssue] = Field(default_factory=list)
    overall_quality: Literal["good", "needs_improvement", "poor"]

    @model_validator(mode="after")
    def derive_summary(self) -> "VisualQAOutput":
        """이슈 목록을 정본으로 삼아 요약 필드를 정규화한다."""
        self.has_issues = bool(self.issues)
        if not self.issues:
            self.overall_quality = "good"
        elif any(issue.severity == "high" for issue in self.issues):
            self.overall_quality = "poor"
        else:
            self.overall_quality = "needs_improvement"
        return self


VisualQAPatchField = Literal[
    "left_px",
    "top_px",
    "width_px",
    "height_px",
    "padding_left_px",
    "padding_right_px",
    "padding_top_px",
    "padding_bottom_px",
    "line_spacing_pt",
    "vertical_alignment",
    "autofit",
    "autofit_mode",
    "fill_color",
    "border_color",
    "text_color",
    "text_size_pt",
    "z_index",
    "font_size_pt",
    "color",
    "background_color",
]


class VisualQAPatchOperation(BaseModel):
    """검증된 시각 이슈가 허용한 단일 replace operation."""

    model_config = ConfigDict(extra="forbid")

    element_type: Literal["slide", "textbox", "shape"]
    element_index: int = Field(default=-1, ge=-1)
    field: VisualQAPatchField
    value: str | float | int | bool | None
    paragraph_index: int | None = Field(default=None, ge=0)
    run_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "VisualQAPatchOperation":
        run_field = self.field in {"font_size_pt", "color"}
        if self.element_type == "slide":
            if self.element_index != -1 or self.field != "background_color":
                raise ValueError("slide patch only supports background_color")
            if self.paragraph_index is not None or self.run_index is not None:
                raise ValueError("slide patch cannot target a paragraph run")
        elif self.element_index < 0:
            raise ValueError("element patch requires element_index >= 0")
        if run_field:
            if self.paragraph_index is None or self.run_index is None:
                raise ValueError("run patch requires paragraph_index and run_index")
        elif self.paragraph_index is not None or self.run_index is not None:
            raise ValueError("element field patch cannot target a paragraph run")
        return self


class VisualQAFixPatchOutput(BaseModel):
    """Visual QA 수정 결과 — 전체 spec이 아닌 허용 필드 replace 목록."""

    model_config = ConfigDict(extra="forbid")

    operations: list[VisualQAPatchOperation] = Field(default_factory=list)


def _convert_flat_layout(flat_nodes: list["LayoutNodeOutput"]) -> list[LayoutNode]:
    """Flat 노드 리스트(parent_id 참조) 를 트리 구조 LayoutNode 리스트로 재구성한다.

    - parent_id 가 빈 문자열이거나 노드 dict 에 없는 id 면 root 노드.
    - 같은 parent_id 를 공유하는 노드는 입력 순서대로 children 에 추가.
    """
    by_id: dict[str, LayoutNode] = {}
    children_map: dict[str, list[str]] = {}
    order: list[str] = []
    parent_lookup: dict[str, str] = {}
    for n in flat_nodes:
        node = LayoutNode(
            id=n.id,
            kind=n.kind,
            role=n.role or "",
            description=n.description or "",
            cell_id=n.cell_id or "",
            children=[],
        )
        if n.id in by_id:
            # 중복 id 는 무시 (LLM 출력 결함)
            continue
        by_id[n.id] = node
        order.append(n.id)
        parent_lookup[n.id] = n.parent_id or ""

    # 자식 수집 (입력 순서 유지)
    for child_id in order:
        pid = parent_lookup[child_id]
        if pid and pid in by_id:
            children_map.setdefault(pid, []).append(child_id)

    # 트리 빌드: child node 의 children 을 채움
    for parent_id, child_ids in children_map.items():
        parent_node = by_id[parent_id]
        # dataclass(frozen=True) 라 직접 children 변경 불가 → replace 패턴
        from dataclasses import replace

        children_list = [by_id[cid] for cid in child_ids]
        by_id[parent_id] = replace(parent_node, children=children_list)

    # 부모 변경이 있었던 경우 by_id 가 갱신되었으므로 다시 자식 참조도 갱신 필요
    # 방법: post-order 로 다시 빌드. 실제로 deepest-first 순서로 children 연결.
    # 위 단순 replace 는 root 갱신 시점의 children 이 옛 LayoutNode 가리킴.
    # 정확히 빌드하려면 post-order 필요.

    # post-order: leaf 부터 빌드
    finalized: dict[str, LayoutNode] = {}
    # 자식 id 가 없는 노드부터 처리
    pending = list(order)
    while pending:
        progress = False
        for child_id in list(pending):
            child_ids = children_map.get(child_id, [])
            if all(cid in finalized for cid in child_ids):
                base = by_id[child_id]
                from dataclasses import replace

                finalized[child_id] = replace(
                    base,
                    children=[finalized[cid] for cid in child_ids],
                )
                pending.remove(child_id)
                progress = True
        if not progress:
            # 순환 참조 등 — 남은 노드는 children 비운 채로 finalize
            for child_id in pending:
                finalized[child_id] = by_id[child_id]
            break

    # 최상위 (parent_id 없거나 미존재) 만 root 로 반환, 입력 순서 유지
    roots: list[LayoutNode] = []
    for nid in order:
        pid = parent_lookup[nid]
        if not pid or pid not in by_id:
            roots.append(finalized[nid])
    return roots


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


class _BaseSlideSpecOutput(BaseModel):
    """슬라이드 스펙 LLM 출력의 공통 필드/변환 로직.

    점진적 추상화 하강을 schema 에 박는다.
        Stage 2: grid_layout (regions/columns/rows)
        Stage 3: cell_assignment (cells)
        Stage 3.5: design_doc (sections/components, 의미 단위)
        Stage 4: textboxes/shapes (cell_id + component_id 참조)

    하위 클래스(`ContentSlideSpecOutput`, `SimpleSlideSpecOutput`)가 grid_layout/
    cell_assignment 의 Required/Optional 여부만 분기해서 재선언한다.

    Pydantic 필드 선언 순서가 LLM 출력 순서를 유도하므로 거시 → 중간 → 미시 순으로
    배치한다.
    """

    grid_layout: GridLayoutOutput | None
    cell_assignment: GridCellAssignmentOutput | None
    design_doc: DesignDocOutput | None = None
    background_color: str | None = None
    speaker_notes: str = ""
    textboxes: list[TextBoxOutput] = Field(default_factory=list)
    shapes: list[ShapeOutput] = Field(default_factory=list)
    overflow: list[OverflowContent] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_arrowhead_box_penetration(self) -> "_BaseSlideSpecOutput":
        """화살촉 끝점이 목표 박스 내부로 침투한 생성 결과를 저장 전에 거부한다."""
        boxes: list[tuple[int, tuple[float, float, float, float]]] = []
        for index, shape in enumerate(self.shapes):
            if not _is_arrow_attachable_output_box(shape):
                continue
            boxes.append(
                (
                    index,
                    (
                        shape.left_px,
                        shape.top_px,
                        shape.left_px + abs(shape.width_px),
                        shape.top_px + abs(shape.height_px),
                    ),
                )
            )

        for line_index, shape in enumerate(self.shapes):
            if shape.shape_type != "line":
                continue
            start, end = line_endpoints(
                shape.left_px,
                shape.top_px,
                shape.width_px,
                shape.height_px,
            )
            endpoints: list[tuple[str, tuple[float, float]]] = []
            if shape.start_arrow:
                endpoints.append(("start", start))
            if shape.end_arrow:
                endpoints.append(("end", end))

            for endpoint_name, (x, y) in endpoints:
                containing: list[tuple[float, int]] = []
                for box_index, bounds in boxes:
                    depth = _point_box_penetration_depth(x, y, bounds)
                    if depth is not None:
                        containing.append((depth, box_index))
                if not containing:
                    continue
                penetration, box_index = min(containing)
                if penetration <= ARROW_ENDPOINT_BOUNDARY_TOLERANCE_PX:
                    continue
                raise ValueError(
                    f"Arrowhead {endpoint_name} endpoint of line shape[{line_index}] "
                    f"is {penetration:.1f}px inside shape[{box_index}]. Arrowhead "
                    "endpoints must stop on the target box boundary; shorten the "
                    "line instead of extending it into the box."
                )
        return self

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
                z_index=getattr(tb, "z_index", None),
                grid_cell=tb.grid_cell,
                component_id=tb.component_id,
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
                z_index=getattr(s, "z_index", None),
                grid_cell=s.grid_cell,
                component_id=s.component_id,
            )
            for s in self.shapes
        ]
        grid_plan: GridPlan | None = None
        if self.grid_layout is not None:
            cells_src = (
                self.cell_assignment.cells if self.cell_assignment is not None else []
            )
            grid_plan = GridPlan(
                regions=list(self.grid_layout.regions),
                content_columns=self.grid_layout.content_columns,
                content_rows=self.grid_layout.content_rows,
                cells=[
                    GridCell(
                        id=c.id,
                        region=c.region,
                        row=c.row,
                        col=c.col,
                        row_span=c.row_span,
                        col_span=c.col_span,
                        role=c.role,
                    )
                    for c in cells_src
                ],
            )
        design_doc: DesignDoc | None = None
        if self.design_doc is not None:
            layout = _convert_flat_layout(self.design_doc.layout)
            design_doc = DesignDoc(
                topic=self.design_doc.topic,
                layout_summary=self.design_doc.layout_summary,
                layout=derive_layout_bboxes(layout, textboxes, shapes),
            )
        return PptxSlideSpec(
            background_color=self.background_color,
            textboxes=textboxes,
            shapes=shapes,
            images=[],
            speaker_notes=self.speaker_notes,
            grid_plan=grid_plan,
            design_doc=design_doc,
        )


def _shape_output_has_text(shape: ShapeOutput) -> bool:
    if shape.text and shape.text.strip():
        return True
    return any(run.text.strip() for para in shape.paragraphs for run in para.runs)


def _is_arrow_attachable_output_box(shape: ShapeOutput) -> bool:
    if shape.shape_type == "line":
        return False
    has_text = _shape_output_has_text(shape)
    is_decorative = (
        not has_text and min(abs(shape.width_px), abs(shape.height_px)) <= 10
    )
    if is_decorative:
        return False
    return has_text or shape.fill_color is not None


def _point_box_penetration_depth(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
) -> float | None:
    left, top, right, bottom = bounds
    if x < left or x > right or y < top or y > bottom:
        return None
    return min(x - left, right - x, y - top, bottom - y)


class ContentSlideSpecOutput(_BaseSlideSpecOutput):
    """content 슬라이드용 LLM 응답 모델.

    Stage 2(grid_layout), Stage 3(cell_assignment), Stage 3.5(design_doc) 모두
    Required. LLM 이 거시 → 중간 → 미시 순으로 점진적 추상화 하강을 따르도록
    강제하며, design_doc 의 layout 트리 + bbox 가 채워져야 layout-tree-bbox lint
    가 충돌을 사전 차단할 수 있다.
    """

    grid_layout: GridLayoutOutput
    cell_assignment: GridCellAssignmentOutput
    design_doc: DesignDocOutput

    @model_validator(mode="after")
    def reject_structural_contract_errors(self) -> "ContentSlideSpecOutput":
        """구조 계약의 error lint를 저장 전 검증 오류로 승격한다."""
        from dataclasses import replace

        from ppt_generator.interfaces.spec_utils import lint_slide_spec

        declared_cells = {cell.id for cell in self.cell_assignment.cells}
        leaf_ids = {
            node.id for node in self.design_doc.layout if node.kind == "component"
        }
        refs: list[str] = []
        for index, textbox in enumerate(self.textboxes):
            if not textbox.component_id:
                raise ValueError(f"textbox[{index}] component_id is required")
            if not textbox.grid_cell:
                raise ValueError(f"textbox[{index}] grid_cell is required")
            refs.append(textbox.component_id)
        for index, shape in enumerate(self.shapes):
            has_text = _shape_output_has_text(shape)
            if (
                shape.shape_type == "line"
                or (
                    not has_text
                    and min(abs(shape.width_px), abs(shape.height_px)) <= 10
                )
                or (not has_text and not shape.component_id and not shape.grid_cell)
            ):
                continue
            if not shape.component_id:
                raise ValueError(f"shape[{index}] component_id is required")
            if not shape.grid_cell:
                raise ValueError(f"shape[{index}] grid_cell is required")
            refs.append(shape.component_id)
        missing_leaves = sorted(set(refs) - leaf_ids)
        if missing_leaves:
            raise ValueError(f"component ids must reference leaves: {missing_leaves}")
        counts = Counter(refs)
        unmatched = sorted(leaf_id for leaf_id in leaf_ids if counts[leaf_id] != 1)
        if unmatched:
            raise ValueError(
                f"every component leaf must map to exactly one element: {unmatched}"
            )
        unknown_cells = sorted(
            {
                element.grid_cell
                for element in [*self.textboxes, *self.shapes]
                if element.grid_cell and element.grid_cell not in declared_cells
            }
        )
        if unknown_cells:
            raise ValueError(f"grid cells must be declared: {unknown_cells}")

        spec = replace(self.to_dataclass(), slide_type="content")
        result = lint_slide_spec(
            spec,
            layers=["layout", "section", "cross"],
            stop_on_layer_error=False,
        )
        errors = [
            violation
            for violation in result.violations
            if violation.severity == "error"
        ]
        if errors:
            details = "; ".join(
                f"{violation.rule}: {violation.message}" for violation in errors
            )
            raise ValueError(f"Content slide contract violation: {details}")
        return self


class SimpleSlideSpecOutput(_BaseSlideSpecOutput):
    """title/closing 등 역할 기반 특수 슬라이드용 LLM 응답 모델.

    결정 2: title/closing 슬라이드는 grid/design_doc 단계 omit 가능.
    """

    grid_layout: GridLayoutOutput | None = None
    cell_assignment: GridCellAssignmentOutput | None = None
    design_doc: DesignDocOutput | None = None


def _require_non_empty_text(textbox: TextBoxOutput, *, label: str) -> None:
    runs = [
        run
        for paragraph in textbox.paragraphs
        for run in paragraph.runs
        if run.text.strip()
    ]
    if not runs:
        raise ValueError(f"{label} must contain non-empty text")


def _textbox_for_role(
    textboxes: list[TextBoxOutput],
    role: str,
    *,
    required: bool,
) -> TextBoxOutput | None:
    matches = [textbox for textbox in textboxes if textbox.component_id == role]
    if len(matches) > 1:
        raise ValueError(f"{role} must appear at most once")
    if required and not matches:
        raise ValueError(f"{role} textbox is required")
    return matches[0] if matches else None


def _validate_simple_canvas(
    textboxes: list[TextBoxOutput],
    shapes: list[ShapeOutput],
) -> None:
    """특수 슬라이드의 자유 배치를 허용하되 캔버스 밖 결과는 거부한다."""
    for label, elements in (("textbox", textboxes), ("shape", shapes)):
        for index, element in enumerate(elements):
            left = min(element.left_px, element.left_px + element.width_px)
            right = max(element.left_px, element.left_px + element.width_px)
            top = min(element.top_px, element.top_px + element.height_px)
            bottom = max(element.top_px, element.top_px + element.height_px)
            if left < 0 or top < 0 or right > 1280 or bottom > 720:
                raise ValueError(f"{label}[{index}] must stay inside the canvas")


class TitleSlideSpecOutput(SimpleSlideSpecOutput):
    """title의 의미 역할과 렌더 가능 범위를 검증하는 응답 모델."""

    @model_validator(mode="after")
    def validate_title_layout(self) -> "TitleSlideSpecOutput":
        main_title = _textbox_for_role(self.textboxes, "title.main", required=True)
        assert main_title is not None
        _require_non_empty_text(main_title, label="title.main")
        for role in ("title.subtitle", "title.presenter"):
            textbox = _textbox_for_role(self.textboxes, role, required=False)
            if textbox is not None:
                _require_non_empty_text(textbox, label=role)
        _validate_simple_canvas(self.textboxes, self.shapes)
        return self


class ClosingSlideSpecOutput(SimpleSlideSpecOutput):
    """closing의 의미 역할과 렌더 가능 범위를 검증하는 응답 모델."""

    @model_validator(mode="after")
    def validate_closing_layout(self) -> "ClosingSlideSpecOutput":
        message = _textbox_for_role(self.textboxes, "closing.message", required=True)
        assert message is not None
        _require_non_empty_text(message, label="closing.message")
        for role in ("closing.action", "closing.contact"):
            textbox = _textbox_for_role(self.textboxes, role, required=False)
            if textbox is not None:
                _require_non_empty_text(textbox, label=role)
        _validate_simple_canvas(self.textboxes, self.shapes)
        return self


def slide_spec_output_model(
    slide_type: str | None,
) -> type[_BaseSlideSpecOutput]:
    """prepare/ingest가 공유하는 슬라이드 타입별 응답 모델을 반환한다."""
    normalized = slide_type or "content"
    if normalized == "content":
        return ContentSlideSpecOutput
    if normalized == "title":
        return TitleSlideSpecOutput
    if normalized == "closing":
        return ClosingSlideSpecOutput
    return SimpleSlideSpecOutput


class VisualQATextBoxOutput(TextBoxOutput):
    """Visual QA에서만 렌더 순서 수정을 허용하는 텍스트박스."""

    z_index: int | None = None


class VisualQAShapeOutput(ShapeOutput):
    """Visual QA에서만 렌더 순서 수정을 허용하는 도형."""

    z_index: int | None = None


class VisualQAContentSlideSpecOutput(ContentSlideSpecOutput):
    """Visual QA용 content 응답 모델."""

    textboxes: list[VisualQATextBoxOutput] = Field(default_factory=list)
    shapes: list[VisualQAShapeOutput] = Field(default_factory=list)


class VisualQASimpleSlideSpecOutput(SimpleSlideSpecOutput):
    """Visual QA용 title/closing 응답 모델."""

    textboxes: list[VisualQATextBoxOutput] = Field(default_factory=list)
    shapes: list[VisualQAShapeOutput] = Field(default_factory=list)


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
        "peer_font_consistency",
        "peer_padding_consistency",
    ]
    severity: Literal["high", "medium"]
    description: str

    @model_validator(mode="after")
    def validate_rule_severity(self) -> "DesignReviewIssue":
        allowed: dict[str, set[str]] = {
            "font_size_floor": {"high"},
            "lr_font_consistency": {"high", "medium"},
            "vstack_overlap": {"high"},
            "vstack_height_uniformity": {"medium"},
            "vstack_gap_uniformity": {"medium"},
            "lr_bottom_alignment": {"medium"},
            "same_level_overlap": {"high"},
            "peer_font_consistency": {"high", "medium"},
            "peer_padding_consistency": {"medium"},
        }
        if self.severity not in allowed[self.rule_id]:
            raise ValueError(f"{self.rule_id} does not allow severity {self.severity}")
        return self


class DesignReviewOutput(BaseModel):
    """Design spec 리뷰 결과."""

    has_high_severity: bool
    issues: list[DesignReviewIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_high_severity(self) -> "DesignReviewOutput":
        """검증된 issue 목록에서 high-severity 여부를 계산한다."""
        self.has_high_severity = any(issue.severity == "high" for issue in self.issues)
        return self


class DeckReviewIssue(BaseModel):
    """덱 전체의 근거·서사·반복 문제."""

    issue_type: Literal[
        "unsupported_claim",
        "narrative_gap",
        "duplicate_content",
        "terminology_drift",
        "agenda_mismatch",
        "conclusion_mismatch",
        "time_density",
    ]
    severity: Literal["high", "medium"]
    slide_indices: list[int] = Field(min_length=1)
    description: str
    suggested_action: str

    @model_validator(mode="after")
    def validate_slide_indices(self) -> "DeckReviewIssue":
        if any(index < 1 for index in self.slide_indices):
            raise ValueError("deck review slide_indices must be 1-based")
        if len(set(self.slide_indices)) != len(self.slide_indices):
            raise ValueError("deck review slide_indices must be unique")
        return self


class DeckReviewOutput(BaseModel):
    """덱 전체 read-only review 응답."""

    has_high_severity: bool
    issues: list[DeckReviewIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_high_severity(self) -> "DeckReviewOutput":
        self.has_high_severity = any(issue.severity == "high" for issue in self.issues)
        return self


# --- Component-level partial modification ---


class ComponentModifyOutput(BaseModel):
    """단일 component 부분 수정 응답.

    `element_kind` 가 "textbox" 면 `textbox` 가 채워지고, "shape" 면 `shape` 가
    채워진다. 다른 한쪽은 None. `bbox_changed=True` 면 호출자가 design_doc.layout
    트리의 동일 component_id 노드의 bbox 도 element bbox 와 동기화한다.
    """

    element_kind: Literal["textbox", "shape"]
    textbox: TextBoxOutput | None = None
    shape: ShapeOutput | None = None
    bbox_changed: bool = False

    @model_validator(mode="after")
    def validate_matching_body(self) -> "ComponentModifyOutput":
        """element_kind와 일치하는 본문 하나만 허용한다."""
        if self.element_kind == "textbox":
            if self.textbox is None or self.shape is not None:
                raise ValueError(
                    "element_kind='textbox' requires textbox and forbids shape"
                )
        elif self.shape is None or self.textbox is not None:
            raise ValueError("element_kind='shape' requires shape and forbids textbox")
        return self


class BackfillElementRef(BaseModel):
    """backfill 시 component leaf 가 가리키는 element 의 위치 참조.

    LLM 은 (kind, index) 만 출력하고, 코드는 이를 참고해 textbox/shape 의
    component_id 필드를 채우고 leaf bbox 를 element bbox 로 동기화한다.
    """

    kind: Literal["textbox", "shape"]
    index: int = Field(ge=0)


class BackfillNode(BaseModel):
    """backfill 시 LLM 이 출력하는 LayoutNode (flat, parent_id 참조).

    bbox 좌표는 LLM 이 직접 출력하지 않는다. 코드가 element bbox 합집합으로 계산.
    `element_ref` 는 kind=='component' 일 때만 채워진다.
    """

    id: str
    parent_id: str | None = ""
    kind: Literal["section", "group", "component"] = "component"
    role: str | None = ""
    description: str | None = ""
    element_ref: BackfillElementRef | None = None


class BackfillDesignDocOutput(BaseModel):
    """imported 슬라이드에 design_doc 트리 + grid_plan 을 백필하기 위한 LLM 응답.

    `topic`/`layout_summary` 는 슬라이드 콘텐츠 요약. `nodes` 는 design_doc.layout
    의 flat 트리 (parent_id 참조). 모든 textbox 와 모든 shape 가 정확히 1 개의
    component leaf 와 매칭되어야 한다 (코드가 검증).

    `grid_layout` / `cell_assignment` 는 grid_plan 백필용. None 이면 grid_plan
    은 비어있는 채로 유지된다 (단순 슬라이드용 fallback). content slide 에서는
    lint 의 `grid-plan-required` 를 만족하기 위해 채워져야 한다.
    """

    topic: str = ""
    layout_summary: str = ""
    nodes: list[BackfillNode] = Field(default_factory=list)
    grid_layout: GridLayoutOutput | None = None
    cell_assignment: GridCellAssignmentOutput | None = None


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
