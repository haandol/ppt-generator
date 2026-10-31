"""실제 준비 문맥·스키마·렌더러에서 지침의 적용 범위를 확인한다."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree

import pytest
from pptx.oxml.ns import qn

from ppt_generator.interfaces.constants import (
    EMU_PER_INCH,
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
)
from ppt_generator.interfaces.output_models.elements import (
    ShapeOutput,
    shape_output_to_dataclass,
)
from ppt_generator.interfaces.prompts import DESIGN_SPEC_SYSTEM_PROMPTS
from ppt_generator.interfaces.schemas import SlideOutline
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.pptx.shape_builders import add_connector_from_spec
from ppt_generator.tools.slides.shape_renderer import shape_to_html


@pytest.mark.parametrize("kind", ["title", "closing"])
def test_special_slides_do_not_receive_content_only_hierarchy(kind: str) -> None:
    task = DesignService().prepare_slide(
        SlideOutline("역할", "메시지", slide_type=kind)
    )
    assert "<content_contract>" not in task["system_prompt"]
    assert "<line_geometry_contract>" in task["system_prompt"]
    assert "design_doc" not in task["response_schema"].get("required", [])


@pytest.mark.parametrize("hint", ["bullets", "process_flow", "concept_list", "custom"])
def test_unrelated_two_column_recipe_is_not_injected(hint: str) -> None:
    task = DesignService().prepare_slide(
        SlideOutline(
            "순서",
            "위에서 아래로 읽는다",
            component_hint=hint,
            layout_plan="vertical: preserve the source relationships",
            source_refs=["provided"],
        )
    )
    assert "<layout_example" not in task["system_prompt"]
    assert "vertical: preserve the source relationships" in task["user_prompt"]
    assert "<content_contract>" in task["system_prompt"]


def _line_examples() -> list[dict]:
    match = re.search(
        r"<line_examples>\s*(.*?)\s*</line_examples>",
        DESIGN_SPEC_SYSTEM_PROMPTS["content"],
        re.S,
    )
    assert match
    return json.loads(match[1])


@pytest.mark.parametrize("example", _line_examples())
def test_prepared_line_examples_match_both_renderer_endpoints(
    example: dict, blank_slide
) -> None:
    shape = shape_output_to_dataclass(ShapeOutput.model_validate(example["shape"]))
    svg = ElementTree.fromstring(shape_to_html(shape))
    style = dict(part.split(":", 1) for part in svg.attrib["style"].split(";") if part)
    left, top = (
        float(style["left"].removesuffix("px")),
        float(style["top"].removesuffix("px")),
    )
    line = svg.find("{http://www.w3.org/2000/svg}line")
    assert line is not None
    assert [left + float(line.attrib["x1"]), top + float(line.attrib["y1"])] == example[
        "source"
    ]
    assert [left + float(line.attrib["x2"]), top + float(line.attrib["y2"])] == example[
        "target"
    ]
    assert line.attrib["marker-end"] == "url(#ah-end)"

    add_connector_from_spec(blank_slide, shape)
    connector = blank_slide.shapes[0]
    scale_x = EMU_PER_INCH * EXPORT_PX_TO_INCHES_X
    scale_y = EMU_PER_INCH * EXPORT_PX_TO_INCHES_Y
    assert [connector.begin_x / scale_x, connector.begin_y / scale_y] == pytest.approx(
        example["source"], abs=0.001
    )
    assert [connector.end_x / scale_x, connector.end_y / scale_y] == pytest.approx(
        example["target"], abs=0.001
    )
    assert (
        connector._element.find(f"{qn('p:spPr')}/{qn('a:ln')}/{qn('a:tailEnd')}").get(
            "type"
        )
        == "triangle"
    )


def test_skill_reference_links_resolve_inside_the_plugin() -> None:
    root = Path(__file__).resolve().parents[1]
    files = list((root / "skills").rglob("*.md"))
    checked = []
    for file in files:
        for href in re.findall(r"\[[^\]]*\]\(([^)]+)\)", file.read_text()):
            parsed = urlparse(href)
            if parsed.scheme or not parsed.path:
                continue
            target = (file.parent / unquote(parsed.path.strip("<>"))).resolve()
            assert target.is_relative_to(root) and target.is_file(), (file, href)
            checked.append(target)
    assert root / "skills/_shared/handshake.md" in checked
    assert root / "skills/_shared/quality-and-delivery.md" in checked
