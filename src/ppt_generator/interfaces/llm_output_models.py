"""LLM structured_output용 Pydantic 모델.

strands Agent의 structured_output_model로 사용되며,
to_dataclass() 메서드로 내부 dataclass(PptxSlideSpec)로 변환한다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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

    left_px: float
    top_px: float
    width_px: float
    height_px: float
    shape_type: Literal["rectangle", "rounded_rectangle", "ellipse", "line"] = (
        "rectangle"
    )
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
    svg_path: str | None = None
    autofit_mode: Literal["expand_height", "shrink_text"] = "expand_height"
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
    """Stage 2: 슬라이드의 거시 레이아웃 결정 (ADR-0046).

    어떤 region 을 쓸지, content 를 몇 행/열로 나눌지의 최상위 결정.
    이 결정 후 cell_assignment 단계에서 cell 정의로 내려간다.
    """

    regions: list[Literal["header", "content", "footer"]] = Field(default_factory=list)
    content_columns: int = Field(default=1, ge=1, le=4)
    content_rows: int = Field(default=1, ge=1)


class GridCellAssignmentOutput(BaseModel):
    """Stage 3: grid_layout 위에서 각 cell 의 위치/span/region/role 할당 (ADR-0046).

    Stage 2 의 layout 을 받아 실제 cell 목록을 정의한다. 이 단계 후 element 단계에서
    각 textbox/shape 가 cell id 를 참조해 좌표·스타일을 채운다.
    """

    cells: list[GridCellOutput] = Field(default_factory=list)


# --- DesignDoc (의미 단위 레이아웃 트리) ---


class LayoutNodeOutput(BaseModel):
    """슬라이드 레이아웃 트리 노드. 임의 깊이의 의미 단위 묶음 + bounding box.

    kind:
      - "section": 큰 의미 영역 (보통 grid cell 과 매핑)
      - "group":   section 안의 중간 묶음 (옵션, 깊이 2 이상)
      - "component": 리프. textbox/shape 가 component_id 로 참조

    id 는 path 형태 (lower_snake_case + dot 구분):
      "right_diagram", "right_diagram.llm_box",
      "right_diagram.functions.web_search"

    좌표 필드는 이 노드의 점유 영역 (bounding box). section/group 은 자식 전체
    bbox, component 는 해당 textbox/shape 와 동일. 점진적 하강의 핵심 메커니즘:
    부모 bbox 가 먼저 결정되면 자식은 그 안에서만 좌표를 잡으므로 시각적 충돌
    이 구조적으로 차단된다. 다이어그램 그룹에서 특히 효과적.
    """

    id: str
    kind: Literal["section", "group", "component"] = "component"
    role: str = ""  # "llm_box" | "context_bus" | "function_card" | "card_title" | ...
    description: str = ""  # 1-2 문장 의미 설명
    cell_id: str = ""  # GridPlan.cells[].id (없으면 "")
    left_px: float | None = None
    top_px: float | None = None
    width_px: float | None = None
    height_px: float | None = None
    children: list["LayoutNodeOutput"] = Field(default_factory=list)


# Pydantic v2 forward reference resolve
LayoutNodeOutput.model_rebuild()


class DesignDocOutput(BaseModel):
    """슬라이드의 구조/의도 메타데이터.

    `speaker_notes` 와 분리해 *디자인 의도* 만 담는다. LLM 부분 수정 요청 시
    트리 path 로 요소를 지칭하기 위한 인덱스 역할.
    """

    topic: str = ""  # 슬라이드 한 줄 주제
    layout_summary: str = ""  # "좌 c1=설명 카드 3개, 우 c2=다이어그램" 식의 한 문단
    layout: list[LayoutNodeOutput] = Field(default_factory=list)


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
    ]
    severity: Literal["high", "medium", "low"]
    element_type: Literal["textbox", "shape"]
    element_index: int = Field(ge=0)
    description: str
    suggested_fix: str


class VisualQAOutput(BaseModel):
    """Visual QA 스크린샷 분석 결과."""

    has_issues: bool
    issues: list[VisualQAIssue] = Field(default_factory=list)
    overall_quality: Literal["good", "needs_improvement", "poor"]


def _convert_layout_node(node: "LayoutNodeOutput") -> LayoutNode:
    """LayoutNodeOutput 을 LayoutNode dataclass 로 재귀 변환."""
    return LayoutNode(
        id=node.id,
        kind=node.kind,
        role=node.role,
        description=node.description,
        cell_id=node.cell_id,
        left_px=node.left_px,
        top_px=node.top_px,
        width_px=node.width_px,
        height_px=node.height_px,
        children=[_convert_layout_node(c) for c in node.children],
    )


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

    ADR-0046: 점진적 추상화 하강을 schema 에 박는다.
        Stage 2: grid_layout       (regions/columns/rows)
        Stage 3: cell_assignment   (cells)
        Stage 3.5: design_doc      (sections/components, 의미 단위)
        Stage 4: textboxes/shapes  (cell_id + component_id 참조)

    하위 클래스(`ContentSlideSpecOutput`, `SimpleSlideSpecOutput`)가 grid_layout/
    cell_assignment 의 Required/Optional 여부만 분기해서 재선언한다 (ADR-0045).

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
            design_doc = DesignDoc(
                topic=self.design_doc.topic,
                layout_summary=self.design_doc.layout_summary,
                layout=[_convert_layout_node(n) for n in self.design_doc.layout],
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


class ContentSlideSpecOutput(_BaseSlideSpecOutput):
    """content 슬라이드용 LLM 응답 모델 (ADR-0045 / ADR-0046).

    Stage 2(grid_layout) 와 Stage 3(cell_assignment) 모두 Required.
    LLM 이 거시 → 중간 → 미시 순으로 점진적 추상화 하강을 따르도록 강제한다.
    """

    grid_layout: GridLayoutOutput
    cell_assignment: GridCellAssignmentOutput


class SimpleSlideSpecOutput(_BaseSlideSpecOutput):
    """title/closing 등 fixed special layout 슬라이드용 LLM 응답 모델.

    ADR-0044 결정 2: title/closing 슬라이드는 grid 단계 omit 가능.
    """

    grid_layout: GridLayoutOutput | None = None
    cell_assignment: GridCellAssignmentOutput | None = None


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
    ]
    severity: Literal["high", "medium"]
    description: str


class DesignReviewOutput(BaseModel):
    """Design spec 리뷰 결과."""

    has_high_severity: bool
    issues: list[DesignReviewIssue] = Field(default_factory=list)
