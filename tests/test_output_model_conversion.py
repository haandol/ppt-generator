"""생성·부분 수정·시각 QA가 렌더 필드와 계층 정보를 보존하는지 검사한다."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from ppt_generator.interfaces.llm_output_models import (
    ShapeOutput,
    SimpleSlideSpecOutput,
    TextBoxOutput,
    VisualQASimpleSlideSpecOutput,
    shape_output_to_dataclass,
    textbox_output_to_dataclass,
)
from ppt_generator.interfaces.schemas import GridCell, GridPlan, PptxTextRun


@pytest.mark.parametrize("entry_point", ["slide", "component", "visual_qa"])
def test_element_conversion_preserves_render_fields(entry_point: str) -> None:
    run = {
        "text": "설명 & link",
        "font_size_pt": 19,
        "color": "#123456",
        "bold": True,
        "italic": True,
        "font_family": "monospace",
        "href": "https://example.com/reference?a=1&b=2",
    }
    common = {
        "left_px": 80.5,
        "top_px": 140.5,
        "width_px": 300.5,
        "height_px": 140.5,
        "paragraphs": [{"runs": [run], "bullet_level": 1, "alignment": "right"}],
        "line_spacing_pt": 26.5,
        "vertical_alignment": "bottom",
        "padding_left_px": 3.5,
        "padding_right_px": 4.5,
        "padding_top_px": 5.5,
        "padding_bottom_px": 6.5,
        "grid_cell": "body",
    }
    textbox = {**common, "component_id": "body.caption"}
    shape = {
        **common,
        "left_px": 400.5,
        "component_id": "body.card",
        "shape_type": "rounded_rectangle",
        "fill_color": "#ffffff",
        "border_color": "#abcdef",
        "border_width_pt": 1.5,
        "corner_radius_px": 8.5,
        "text": "보조 설명",
        "text_color": "#101010",
        "text_size_pt": 18,
        "text_bold": True,
        "start_arrow": True,
        "end_arrow": True,
        "dash_style": "dot",
        "svg_path": "M 0 0 L 1 1",
        "autofit_mode": "expand_height",
    }
    if entry_point == "component":
        elements = [
            textbox_output_to_dataclass(TextBoxOutput.model_validate(textbox)),
            shape_output_to_dataclass(ShapeOutput.model_validate(shape)),
        ]
    else:
        model = SimpleSlideSpecOutput
        if entry_point == "visual_qa":
            model = VisualQASimpleSlideSpecOutput
            textbox["z_index"] = 7
            shape["z_index"] = 2
        spec = model.model_validate(
            {
                "textboxes": [textbox],
                "shapes": [shape],
                "speaker_notes": "첫 문단\n\n둘째 문단",
            }
        ).to_dataclass()
        assert spec.speaker_notes == "첫 문단\n\n둘째 문단"
        elements = [spec.textboxes[0], spec.shapes[0]]

    for source, element in zip([textbox, shape], elements, strict=True):
        for name, value in source.items():
            if name != "paragraphs":
                assert getattr(element, name) == value, name
        assert element.paragraphs[0].runs == [PptxTextRun(**run)]
        assert element.paragraphs[0].bullet_level == 1
        assert element.paragraphs[0].alignment == "right"
        if entry_point != "visual_qa":
            assert element.z_index is None


def test_grid_conversion_copies_cells_without_sharing_mutable_regions() -> None:
    payload = {
        "grid_layout": {
            "regions": ["header", "content"],
            "content_columns": 3,
            "content_rows": 2,
        },
        "cell_assignment": {
            "cells": [
                {
                    "id": "main",
                    "region": "content",
                    "row": 2,
                    "col": 2,
                    "row_span": 1,
                    "col_span": 2,
                    "role": "evidence",
                }
            ]
        },
    }
    output = SimpleSlideSpecOutput.model_validate(payload)
    spec = output.to_dataclass()
    assert spec.grid_plan == GridPlan(
        regions=["header", "content"],
        content_columns=3,
        content_rows=2,
        cells=[
            GridCell(
                id="main",
                region="content",
                row=2,
                col=2,
                row_span=1,
                col_span=2,
                role="evidence",
            )
        ],
    )
    output.grid_layout.regions.clear()
    output.cell_assignment.cells[0].role = "changed"
    assert spec.grid_plan.regions == ["header", "content"]
    assert asdict(spec.grid_plan.cells[0])["role"] == "evidence"


@pytest.mark.parametrize("grid", [None, {"content_columns": 2}])
def test_optional_grid_without_cell_assignment(grid: dict | None) -> None:
    spec = SimpleSlideSpecOutput.model_validate({"grid_layout": grid}).to_dataclass()
    if grid is None:
        assert spec.grid_plan is None
    else:
        assert spec.grid_plan == GridPlan(
            regions=[], content_columns=2, content_rows=1, cells=[]
        )
