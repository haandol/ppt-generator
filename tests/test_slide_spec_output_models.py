"""ADR-0045 / ADR-0046: 점진적 추상화 하강 응답 모델 테스트.

ContentSlideSpecOutput 은 grid_layout (Stage 2) 와 cell_assignment (Stage 3) 모두
Pydantic Required 로 강제한다. SimpleSlideSpecOutput 은 title/closing 슬라이드용으로
두 필드 모두 Optional.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ppt_generator.interfaces.llm_output_models import (
    ContentSlideSpecOutput,
    DesignDocOutput,
    GridCellAssignmentOutput,
    GridCellOutput,
    GridLayoutOutput,
    LayoutNodeOutput,
    SimpleSlideSpecOutput,
)


def _grid_layout() -> GridLayoutOutput:
    return GridLayoutOutput(
        regions=["header", "content"],
        content_columns=2,
        content_rows=1,
    )


def _cell_assignment() -> GridCellAssignmentOutput:
    return GridCellAssignmentOutput(
        cells=[
            GridCellOutput(id="c1", region="header", row=1, col=1),
            GridCellOutput(id="c2", region="content", row=1, col=1),
        ],
    )


def _design_doc() -> DesignDocOutput:
    return DesignDocOutput(
        topic="t",
        layout_summary="ls",
        layout=[
            LayoutNodeOutput(
                id="root",
                kind="section",
                left_px=64,
                top_px=148,
                width_px=1152,
                height_px=510,
            )
        ],
    )


class TestContentSlideSpecOutput:
    def test_validation_fails_when_both_missing(self) -> None:
        with pytest.raises(ValidationError):
            ContentSlideSpecOutput(textboxes=[], shapes=[])

    def test_validation_fails_when_grid_layout_missing(self) -> None:
        with pytest.raises(ValidationError):
            ContentSlideSpecOutput(
                cell_assignment=_cell_assignment(),
                textboxes=[],
                shapes=[],
            )

    def test_validation_fails_when_cell_assignment_missing(self) -> None:
        with pytest.raises(ValidationError):
            ContentSlideSpecOutput(
                grid_layout=_grid_layout(),
                textboxes=[],
                shapes=[],
            )

    def test_validation_fails_when_design_doc_missing(self) -> None:
        """ContentSlideSpec 은 design_doc 도 Required."""
        with pytest.raises(ValidationError):
            ContentSlideSpecOutput(
                grid_layout=_grid_layout(),
                cell_assignment=_cell_assignment(),
                textboxes=[],
                shapes=[],
            )

    def test_validation_fails_when_either_null(self) -> None:
        with pytest.raises(ValidationError):
            ContentSlideSpecOutput(
                grid_layout=None,
                cell_assignment=_cell_assignment(),
                textboxes=[],
                shapes=[],
            )
        with pytest.raises(ValidationError):
            ContentSlideSpecOutput(
                grid_layout=_grid_layout(),
                cell_assignment=None,
                textboxes=[],
                shapes=[],
            )

    def test_accepts_both_stages(self) -> None:
        output = ContentSlideSpecOutput(
            grid_layout=_grid_layout(),
            cell_assignment=_cell_assignment(),
            design_doc=_design_doc(),
            textboxes=[],
            shapes=[],
        )
        assert output.grid_layout.content_columns == 2
        assert len(output.cell_assignment.cells) == 2

    def test_to_dataclass_merges_into_grid_plan(self) -> None:
        output = ContentSlideSpecOutput(
            grid_layout=_grid_layout(),
            cell_assignment=_cell_assignment(),
            design_doc=_design_doc(),
            textboxes=[],
            shapes=[],
        )
        spec = output.to_dataclass()
        assert spec.grid_plan is not None
        assert spec.grid_plan.regions == ["header", "content"]
        assert spec.grid_plan.content_columns == 2
        assert spec.grid_plan.content_rows == 1
        assert [c.id for c in spec.grid_plan.cells] == ["c1", "c2"]


class TestSimpleSlideSpecOutput:
    def test_both_stages_default_none(self) -> None:
        output = SimpleSlideSpecOutput(textboxes=[], shapes=[])
        assert output.grid_layout is None
        assert output.cell_assignment is None

    def test_to_dataclass_grid_plan_none(self) -> None:
        output = SimpleSlideSpecOutput(textboxes=[], shapes=[])
        spec = output.to_dataclass()
        assert spec.grid_plan is None

    def test_accepts_both_stages_when_provided(self) -> None:
        output = SimpleSlideSpecOutput(
            grid_layout=_grid_layout(),
            cell_assignment=_cell_assignment(),
            textboxes=[],
            shapes=[],
        )
        spec = output.to_dataclass()
        assert spec.grid_plan is not None
        assert len(spec.grid_plan.cells) == 2

    def test_to_dataclass_layout_only_yields_grid_plan_with_empty_cells(self) -> None:
        output = SimpleSlideSpecOutput(
            grid_layout=_grid_layout(),
            cell_assignment=None,
            textboxes=[],
            shapes=[],
        )
        spec = output.to_dataclass()
        assert spec.grid_plan is not None
        assert spec.grid_plan.cells == []
