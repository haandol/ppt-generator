"""/ 점진적 추상화 하강 응답 모델 테스트.

ContentSlideSpecOutput 은 grid_layout (Stage 2) 와 cell_assignment (Stage 3) 모두
Pydantic Required 로 강제한다. SimpleSlideSpecOutput 은 title/closing 슬라이드용으로
두 필드 모두 Optional.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ppt_generator.interfaces.llm_output_models import (
    ClosingSlideSpecOutput,
    ContentSlideSpecOutput,
    DesignDocOutput,
    GridCellAssignmentOutput,
    GridCellOutput,
    GridLayoutOutput,
    LayoutNodeOutput,
    ShapeOutput,
    SimpleSlideSpecOutput,
    TitleSlideSpecOutput,
    slide_spec_output_model,
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


def _paragraph(text: str, font_size_pt: int, *, bold: bool = False) -> dict:
    return {
        "runs": [
            {
                "text": text,
                "font_size_pt": font_size_pt,
                "bold": bold,
            }
        ],
        "bullet_level": -1,
        "alignment": "left",
    }


def _textbox(
    left: float,
    top: float,
    width: float,
    height: float,
    paragraphs: list[dict],
    *,
    vertical_alignment: str,
) -> dict:
    return {
        "left_px": left,
        "top_px": top,
        "width_px": width,
        "height_px": height,
        "paragraphs": paragraphs,
        "vertical_alignment": vertical_alignment,
    }


def _divider(top: float) -> dict:
    return {
        "left_px": 64,
        "top_px": top,
        "width_px": 80,
        "height_px": 4,
        "shape_type": "rectangle",
    }


def _title_payload(*, two_line: bool = False) -> dict:
    title_height = 160 if two_line else 80
    return {
        "background_color": None,
        "textboxes": [
            _textbox(
                64,
                260,
                1152,
                title_height,
                [_paragraph("Main title", 40, bold=True)],
                vertical_alignment="middle",
            ),
            _textbox(
                64,
                450 if two_line else 370,
                1152,
                100,
                [_paragraph("Subtitle", 16)],
                vertical_alignment="top",
            ),
            _textbox(
                64,
                560,
                400,
                96,
                [
                    _paragraph("Name", 18),
                    _paragraph("Role", 18),
                    _paragraph("Organization", 18),
                ],
                vertical_alignment="bottom",
            ),
        ],
        "shapes": [_divider(430 if two_line else 350)],
    }


def _closing_payload(*, include_contact: bool = True) -> dict:
    textboxes = [
        _textbox(
            64,
            260,
            1152,
            80,
            [_paragraph("Thank You", 40, bold=True)],
            vertical_alignment="middle",
        ),
        _textbox(
            64,
            370,
            1152,
            60,
            [_paragraph("Questions & Feedback", 20)],
            vertical_alignment="top",
        ),
    ]
    if include_contact:
        textboxes.append(
            _textbox(
                64,
                450,
                1000,
                120,
                [_paragraph("Contact", 14)],
                vertical_alignment="top",
            )
        )
    return {
        "background_color": None,
        "textboxes": textboxes,
        "shapes": [_divider(350)],
    }


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

    def test_rejects_duplicate_grid_cell_ids(self) -> None:
        with pytest.raises(ValidationError, match="grid cell ids must be unique"):
            GridCellAssignmentOutput(
                cells=[
                    GridCellOutput(id="c1"),
                    GridCellOutput(id="c1"),
                ]
            )

    def test_rejects_layout_node_with_missing_parent(self) -> None:
        with pytest.raises(ValidationError, match="missing or later parent"):
            DesignDocOutput(
                topic="t",
                layout_summary="s",
                layout=[
                    LayoutNodeOutput(
                        id="child",
                        parent_id="missing",
                        kind="component",
                        left_px=64,
                        top_px=148,
                        width_px=100,
                        height_px=100,
                    )
                ],
            )

    def test_rejects_unknown_grid_cell_reference_before_ingest(self) -> None:
        with pytest.raises(ValidationError, match="grid-cell-coverage"):
            ContentSlideSpecOutput.model_validate(
                {
                    "grid_layout": {
                        "regions": ["header", "content"],
                        "content_columns": 1,
                        "content_rows": 1,
                    },
                    "cell_assignment": {
                        "cells": [
                            {
                                "id": "c1",
                                "region": "content",
                                "row": 1,
                                "col": 1,
                            }
                        ]
                    },
                    "design_doc": {
                        "topic": "t",
                        "layout_summary": "s",
                        "layout": [
                            {
                                "id": "root",
                                "kind": "section",
                                "cell_id": "c1",
                                "left_px": 64,
                                "top_px": 148,
                                "width_px": 1152,
                                "height_px": 510,
                            }
                        ],
                    },
                    "textboxes": [
                        {
                            "left_px": 64,
                            "top_px": 148,
                            "width_px": 200,
                            "height_px": 80,
                            "grid_cell": "missing",
                            "paragraphs": [_paragraph("Body", 18)],
                        }
                    ],
                    "shapes": [],
                }
            )


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


class TestFixedLayoutSlideSpecOutput:
    @pytest.mark.parametrize("two_line", [False, True])
    def test_title_accepts_fixed_layout_variants(self, two_line: bool) -> None:
        output = TitleSlideSpecOutput.model_validate(_title_payload(two_line=two_line))
        assert output.textboxes[0].height_px == (160 if two_line else 80)

    def test_title_rejects_missing_required_elements(self) -> None:
        with pytest.raises(ValidationError, match="title requires"):
            TitleSlideSpecOutput(textboxes=[], shapes=[])

    def test_title_rejects_coordinate_drift(self) -> None:
        payload = _title_payload()
        payload["textboxes"][0]["top_px"] = 261
        with pytest.raises(ValidationError, match="title main title bbox"):
            TitleSlideSpecOutput.model_validate(payload)

    def test_title_rejects_wrong_two_line_followup_positions(self) -> None:
        payload = _title_payload(two_line=True)
        payload["textboxes"][1]["top_px"] = 370
        with pytest.raises(ValidationError, match="title subtitle bbox"):
            TitleSlideSpecOutput.model_validate(payload)

    def test_title_rejects_presenter_without_three_paragraphs(self) -> None:
        payload = _title_payload()
        payload["textboxes"][2]["paragraphs"].pop()
        with pytest.raises(ValidationError, match="exactly 3 non-empty paragraphs"):
            TitleSlideSpecOutput.model_validate(payload)

    def test_title_allows_other_rectangles_before_the_required_divider(self) -> None:
        payload = _title_payload()
        payload["shapes"].insert(
            0,
            {
                "left_px": 64,
                "top_px": 120,
                "width_px": 80,
                "height_px": 4,
                "shape_type": "rectangle",
            },
        )
        output = TitleSlideSpecOutput.model_validate(payload)
        assert len(output.shapes) == 2

    @pytest.mark.parametrize("include_contact", [False, True])
    def test_closing_accepts_fixed_layout(self, include_contact: bool) -> None:
        output = ClosingSlideSpecOutput.model_validate(
            _closing_payload(include_contact=include_contact)
        )
        assert len(output.textboxes) == (3 if include_contact else 2)

    def test_closing_rejects_coordinate_drift(self) -> None:
        payload = _closing_payload()
        payload["textboxes"][0]["left_px"] = 65
        with pytest.raises(ValidationError, match="closing thank-you message bbox"):
            ClosingSlideSpecOutput.model_validate(payload)

    def test_closing_rejects_contact_font_outside_contract(self) -> None:
        payload = _closing_payload()
        payload["textboxes"][2]["paragraphs"][0]["runs"][0]["font_size_pt"] = 18
        with pytest.raises(ValidationError, match="14~16pt"):
            ClosingSlideSpecOutput.model_validate(payload)

    def test_slide_type_selects_the_same_prepare_ingest_model(self) -> None:
        assert slide_spec_output_model("content") is ContentSlideSpecOutput
        assert slide_spec_output_model("title") is TitleSlideSpecOutput
        assert slide_spec_output_model("closing") is ClosingSlideSpecOutput
        assert slide_spec_output_model(None) is ContentSlideSpecOutput


class TestLineGeometryContract:
    @pytest.mark.parametrize(
        ("width_px", "height_px"),
        [
            (32, 2),
            (2, 70),
            (-40, 2),
            (2, -40),
        ],
    )
    def test_accepts_near_axis_line_as_valid_endpoint_geometry(
        self, width_px: float, height_px: float
    ) -> None:
        shape = ShapeOutput(
            left_px=100,
            top_px=100,
            width_px=width_px,
            height_px=height_px,
            shape_type="line",
            border_width_pt=2,
        )
        assert shape.width_px == width_px
        assert shape.height_px == height_px

    @pytest.mark.parametrize(
        ("width_px", "height_px"),
        [
            (32, 0),
            (0, 70),
            (84, 48),
            (-84, 48),
        ],
    )
    def test_accepts_exact_axis_or_meaningful_diagonal_line(
        self, width_px: float, height_px: float
    ) -> None:
        shape = ShapeOutput(
            left_px=100,
            top_px=100,
            width_px=width_px,
            height_px=height_px,
            shape_type="line",
            border_width_pt=2,
        )
        assert shape.width_px == width_px
        assert shape.height_px == height_px

    def test_json_schema_explains_line_axis_and_stroke_contract(self) -> None:
        properties = ShapeOutput.model_json_schema()["properties"]
        assert (
            "signed horizontal endpoint delta" in properties["width_px"]["description"]
        )
        assert (
            "signed vertical endpoint delta" in properties["height_px"]["description"]
        )
        assert "stroke thickness" in properties["border_width_pt"]["description"]


class TestArrowEndpointBoundaryContract:
    def test_rejects_arrowhead_deep_inside_target_box(self) -> None:
        with pytest.raises(ValidationError, match="target box boundary"):
            SimpleSlideSpecOutput(
                textboxes=[],
                shapes=[
                    ShapeOutput(
                        left_px=100,
                        top_px=100,
                        width_px=100,
                        height_px=60,
                        shape_type="rounded_rectangle",
                        fill_color="#FFFFFF",
                    ),
                    ShapeOutput(
                        left_px=50,
                        top_px=130,
                        width_px=70,
                        height_px=0,
                        shape_type="line",
                        end_arrow=True,
                    ),
                ],
            )

    def test_rejects_eight_pixel_vertical_penetration(self) -> None:
        with pytest.raises(ValidationError, match="8.0px inside"):
            SimpleSlideSpecOutput(
                textboxes=[],
                shapes=[
                    ShapeOutput(
                        left_px=88,
                        top_px=250,
                        width_px=312,
                        height_px=130,
                        shape_type="rounded_rectangle",
                        fill_color="#FFFFFF",
                    ),
                    ShapeOutput(
                        left_px=245,
                        top_px=234,
                        width_px=0,
                        height_px=24,
                        shape_type="line",
                        end_arrow=True,
                    ),
                ],
            )

    def test_accepts_arrowhead_exactly_on_target_boundary(self) -> None:
        output = SimpleSlideSpecOutput(
            textboxes=[],
            shapes=[
                ShapeOutput(
                    left_px=100,
                    top_px=100,
                    width_px=100,
                    height_px=60,
                    shape_type="rounded_rectangle",
                    fill_color="#FFFFFF",
                ),
                ShapeOutput(
                    left_px=50,
                    top_px=130,
                    width_px=50,
                    height_px=0,
                    shape_type="line",
                    end_arrow=True,
                ),
            ],
        )
        assert len(output.shapes) == 2

    def test_allows_floating_endpoint_for_lint_to_report(self) -> None:
        output = SimpleSlideSpecOutput(
            textboxes=[],
            shapes=[
                ShapeOutput(
                    left_px=100,
                    top_px=100,
                    width_px=100,
                    height_px=60,
                    shape_type="rounded_rectangle",
                    fill_color="#FFFFFF",
                ),
                ShapeOutput(
                    left_px=20,
                    top_px=50,
                    width_px=30,
                    height_px=0,
                    shape_type="line",
                    end_arrow=True,
                ),
            ],
        )
        assert len(output.shapes) == 2
