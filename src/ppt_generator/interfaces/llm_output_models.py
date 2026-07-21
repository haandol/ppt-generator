"""LLM 출력용 Pydantic 모델.

두 역할을 한다:
- ``prepare_*`` 도구가 ``model_json_schema()`` 로 출력 스키마를 만들어 클라이언트에
  넘긴다 (클라이언트가 따라야 할 형식).
- ``ingest_*`` 도구가 ``model_validate()`` 로 클라이언트 JSON 을 검증한 뒤
  ``to_dataclass()`` 로 내부 dataclass(PptxSlideSpec)로 변환한다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class SlideOutlineOutput(BaseModel):
    """클라이언트가 생성하는 단일 슬라이드 아웃라인."""

    model_config = ConfigDict(extra="forbid")

    title: str
    content_summary: str
    component_hint: str
    slide_type: Literal["title", "closing", "content"]
    layout_plan: str
    speaker_notes: str
    slide_index: int | None = None


class OutlineOutput(BaseModel):
    """클라이언트가 생성하는 전체 아웃라인."""

    model_config = ConfigDict(extra="forbid")

    slides: list[SlideOutlineOutput]


class DesignRegionOutput(BaseModel):
    """덱 전체가 공유하는 세로 영역."""

    model_config = ConfigDict(extra="forbid")

    top_px: float = Field(ge=0)
    height_px: float = Field(gt=0)


class DesignThemeOutput(BaseModel):
    """DESIGN.md 초안의 수치 디자인 시스템."""

    model_config = ConfigDict(extra="forbid")

    background_color: str
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


class DesignDocDraftOutput(BaseModel):
    """DESIGN.md 초안 생성 단계의 전체 출력."""

    model_config = ConfigDict(extra="forbid")

    theme: DesignThemeOutput
    tone: str
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
    z_index: int | None = None
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
    # 결정 14: 기본 shrink_text (높이 고정, 폰트 자동 축소)
    autofit_mode: Literal["expand_height", "shrink_text"] = "shrink_text"
    z_index: int | None = None
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

    좌표 필드는 노드의 점유 영역 (bounding box). 부모 bbox 안에 자식 bbox 가
    포함되어야 하며, 같은 부모 아래 형제 bbox 는 겹치면 안 된다 (lint 검증).
    """

    id: str
    parent_id: str | None = ""  # 부모 노드 id (빈 문자열 또는 null 이면 root section)
    kind: Literal["section", "group", "component"] = "component"
    role: str | None = (
        ""  # "llm_box" | "context_bus" | "function_card" | "card_title" |...
    )
    description: str | None = ""  # 1-2 문장 의미 설명
    cell_id: str | None = ""  # GridPlan.cells[].id (없거나 null 가능)
    left_px: float | None = None
    top_px: float | None = None
    width_px: float | None = None
    height_px: float | None = None


class DesignDocOutput(BaseModel):
    """슬라이드의 구조/의도 메타데이터.

    `speaker_notes` 와 분리해 *디자인 의도* 만 담는다. LLM 부분 수정 요청 시
    트리 path 로 요소를 지칭하기 위한 인덱스 역할.
    `layout` 은 flat 노드 리스트. 변환 시 parent_id 로 트리 재구성.
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
    description: str
    suggested_fix: str


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
            left_px=n.left_px,
            top_px=n.top_px,
            width_px=n.width_px,
            height_px=n.height_px,
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
                z_index=tb.z_index,
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
                z_index=s.z_index,
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
                layout=_convert_flat_layout(self.design_doc.layout),
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
    """content 슬라이드용 LLM 응답 모델.

    Stage 2(grid_layout), Stage 3(cell_assignment), Stage 3.5(design_doc) 모두
    Required. LLM 이 거시 → 중간 → 미시 순으로 점진적 추상화 하강을 따르도록
    강제하며, design_doc 의 layout 트리 + bbox 가 채워져야 layout-tree-bbox lint
    가 충돌을 사전 차단할 수 있다.
    """

    grid_layout: GridLayoutOutput
    cell_assignment: GridCellAssignmentOutput
    design_doc: DesignDocOutput


class SimpleSlideSpecOutput(_BaseSlideSpecOutput):
    """title/closing 등 fixed special layout 슬라이드용 LLM 응답 모델.

    결정 2: title/closing 슬라이드는 grid/design_doc 단계 omit 가능.
    """

    grid_layout: GridLayoutOutput | None = None
    cell_assignment: GridCellAssignmentOutput | None = None
    design_doc: DesignDocOutput | None = None


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


class DesignReviewOutput(BaseModel):
    """Design spec 리뷰 결과."""

    has_high_severity: bool
    issues: list[DesignReviewIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_high_severity(self) -> "DesignReviewOutput":
        """검증된 issue 목록에서 high-severity 여부를 계산한다."""
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
        z_index=tb.z_index,
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
        z_index=s.z_index,
        grid_cell=s.grid_cell,
        component_id=s.component_id,
    )
