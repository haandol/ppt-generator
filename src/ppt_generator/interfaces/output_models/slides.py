"""슬라이드 유형별 응답 검증과 DesignSpec 변환."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field, model_validator

from ppt_generator.interfaces.layout_derivation import derive_layout_bboxes
from ppt_generator.interfaces.line_geometry import (
    ARROW_ENDPOINT_BOUNDARY_TOLERANCE_PX,
    line_endpoints,
)
from ppt_generator.interfaces.schemas import DesignDoc, PptxSlideSpec

from .elements import (
    ShapeOutput,
    TextBoxOutput,
    shape_output_to_dataclass,
    textbox_output_to_dataclass,
)
from .layout import (
    DesignDocOutput,
    GridCellAssignmentOutput,
    GridLayoutOutput,
    _convert_flat_layout,
    grid_plan_from_output,
)


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
        textboxes = [textbox_output_to_dataclass(tb) for tb in self.textboxes]
        shapes = [shape_output_to_dataclass(shape) for shape in self.shapes]
        grid_plan = grid_plan_from_output(self.grid_layout, self.cell_assignment)
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
