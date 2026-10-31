"""그리드·의미 트리 응답과 계층 변환."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ppt_generator.interfaces.schemas import GridCell, GridPlan, LayoutNode


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


def grid_plan_from_output(
    layout: GridLayoutOutput | None,
    assignment: GridCellAssignmentOutput | None,
) -> GridPlan | None:
    """생성과 backfill의 동일한 그리드 응답을 독립적인 저장 모델로 변환한다."""
    if layout is None:
        return None
    cells = assignment.cells if assignment is not None else []
    return GridPlan(
        regions=list(layout.regions),
        content_columns=layout.content_columns,
        content_rows=layout.content_rows,
        cells=[
            GridCell(
                id=cell.id,
                region=cell.region,
                row=cell.row,
                col=cell.col,
                row_span=cell.row_span,
                col_span=cell.col_span,
                role=cell.role,
            )
            for cell in cells
        ],
    )


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
