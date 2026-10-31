"""단일 요소 수정과 임포트 슬라이드 의미 트리 보완 응답."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .elements import ShapeOutput, TextBoxOutput
from .layout import GridCellAssignmentOutput, GridLayoutOutput


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
