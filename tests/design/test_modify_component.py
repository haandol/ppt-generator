"""modify_component (ADR-0050) 테스트.

DesignService.modify_component 와 handle_modify_component 핸들러를
검증한다. LLM 호출은 MagicMock 으로 대체.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.llm_output_models import (
    ComponentModifyOutput,
    ParagraphOutput,
    ShapeOutput,
    TextBoxOutput,
    TextRunOutput,
)
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
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.design.service import (
    DesignService,
    _find_element_by_component_id,
    _replace_node_bbox,
)
from ppt_generator.tools.project.service import ProjectService


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _full_content_slide() -> PptxSlideSpec:
    """5단 계층이 모두 채워진 content 슬라이드 fixture."""
    layout = [
        LayoutNode(
            id="left",
            kind="section",
            role="left",
            cell_id="c1",
            left_px=64,
            top_px=148,
            width_px=560,
            height_px=400,
            children=[
                LayoutNode(
                    id="left.title",
                    kind="component",
                    role="card_title",
                    left_px=64,
                    top_px=148,
                    width_px=560,
                    height_px=80,
                ),
                LayoutNode(
                    id="left.body",
                    kind="component",
                    role="card_body",
                    left_px=64,
                    top_px=240,
                    width_px=560,
                    height_px=308,
                ),
            ],
        ),
        LayoutNode(
            id="right",
            kind="section",
            role="right",
            cell_id="c2",
            left_px=656,
            top_px=148,
            width_px=560,
            height_px=400,
            children=[
                LayoutNode(
                    id="right.box",
                    kind="component",
                    role="llm_box",
                    left_px=700,
                    top_px=300,
                    width_px=200,
                    height_px=100,
                ),
            ],
        ),
    ]
    return PptxSlideSpec(
        background_color="#0F172A",
        textboxes=[
            PptxTextBox(
                left_px=64,
                top_px=148,
                width_px=560,
                height_px=80,
                paragraphs=[
                    PptxParagraph(
                        runs=[PptxTextRun(text="제목", font_size_pt=22, bold=True)]
                    )
                ],
                grid_cell="c1",
                component_id="left.title",
            ),
            PptxTextBox(
                left_px=64,
                top_px=240,
                width_px=560,
                height_px=308,
                paragraphs=[
                    PptxParagraph(runs=[PptxTextRun(text="본문", font_size_pt=18)])
                ],
                grid_cell="c1",
                component_id="left.body",
            ),
        ],
        shapes=[
            PptxShape(
                left_px=700,
                top_px=300,
                width_px=200,
                height_px=100,
                shape_type="rounded_rectangle",
                fill_color="#3B82F6",
                text="LLM",
                text_color="#FFFFFF",
                text_size_pt=24,
                text_bold=True,
                grid_cell="c2",
                component_id="right.box",
            ),
        ],
        speaker_notes="narrative",
        slide_type="content",
        grid_plan=GridPlan(
            regions=["header", "content"],
            content_columns=2,
            content_rows=1,
            cells=[
                GridCell(id="c1", region="content", row=1, col=1, role="left"),
                GridCell(id="c2", region="content", row=1, col=2, role="right"),
            ],
        ),
        design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
    )


def _shape_output_red() -> ShapeOutput:
    """LLM 가 right.box 의 fill_color 만 빨강으로 바꿨다는 응답을 시뮬레이션."""
    return ShapeOutput(
        left_px=700,
        top_px=300,
        width_px=200,
        height_px=100,
        shape_type="rounded_rectangle",
        fill_color="#EF4444",  # 빨강으로 변경
        text="LLM",
        text_color="#FFFFFF",
        text_size_pt=24,
        text_bold=True,
        grid_cell="c2",
        component_id="right.box",
    )


def _textbox_output_renamed() -> TextBoxOutput:
    return TextBoxOutput(
        left_px=64,
        top_px=148,
        width_px=560,
        height_px=80,
        paragraphs=[
            ParagraphOutput(
                runs=[TextRunOutput(text="새 제목", font_size_pt=22, bold=True)]
            )
        ],
        grid_cell="c1",
        component_id="left.title",
    )


# ---------------------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------------------


class TestFindElementHelpers:
    def test_find_textbox(self) -> None:
        spec = _full_content_slide()
        kind, idx, elem = _find_element_by_component_id(spec, "left.title")
        assert kind == "textbox"
        assert idx == 0
        assert elem.component_id == "left.title"

    def test_find_shape(self) -> None:
        spec = _full_content_slide()
        kind, idx, elem = _find_element_by_component_id(spec, "right.box")
        assert kind == "shape"
        assert idx == 0
        assert elem.component_id == "right.box"

    def test_missing_raises(self) -> None:
        spec = _full_content_slide()
        with pytest.raises(ValueError, match="component_id not found"):
            _find_element_by_component_id(spec, "no.such.id")

    def test_replace_node_bbox_root(self) -> None:
        spec = _full_content_slide()
        new_layout = _replace_node_bbox(
            spec.design_doc.layout, "right", (700.0, 200.0, 500.0, 400.0)
        )
        right = [n for n in new_layout if n.id == "right"][0]
        assert (right.left_px, right.top_px, right.width_px, right.height_px) == (
            700.0,
            200.0,
            500.0,
            400.0,
        )
        # 형제 left 는 변경 없음
        left = [n for n in new_layout if n.id == "left"][0]
        assert left.left_px == 64

    def test_replace_node_bbox_child(self) -> None:
        spec = _full_content_slide()
        new_layout = _replace_node_bbox(
            spec.design_doc.layout, "right.box", (720.0, 320.0, 160.0, 80.0)
        )
        right = [n for n in new_layout if n.id == "right"][0]
        assert right.children[0].id == "right.box"
        assert right.children[0].left_px == 720.0
        assert right.children[0].width_px == 160.0
        # 부모 right 자체 bbox 는 변경 없음
        assert right.left_px == 656

    def test_replace_node_bbox_no_match_returns_unchanged(self) -> None:
        spec = _full_content_slide()
        new_layout = _replace_node_bbox(
            spec.design_doc.layout, "missing.id", (0.0, 0.0, 1.0, 1.0)
        )
        # 동일 트리 (변경 없음)
        right = [n for n in new_layout if n.id == "right"][0]
        assert right.left_px == 656


# ---------------------------------------------------------------------------
# DesignService.modify_component
# ---------------------------------------------------------------------------


class TestDesignServiceModifyComponent:
    def _make_service(self, structured: ComponentModifyOutput) -> DesignService:
        agent = MagicMock()
        result = MagicMock()
        result.structured_output = structured
        # log_token_usage 가 result.metrics.accumulated_usage 를 보지 않도록 빈 dict
        result.metrics = None
        agent.return_value = result
        svc = DesignService(agent=agent)
        return svc

    def test_modifies_only_target_shape(self) -> None:
        spec = _full_content_slide()
        svc = self._make_service(
            ComponentModifyOutput(
                element_kind="shape",
                shape=_shape_output_red(),
                bbox_changed=False,
            )
        )
        new_spec = svc.modify_component(
            spec=spec,
            component_id="right.box",
            instruction="Make the LLM box red",
        )
        # 대상 shape 만 색 변경
        assert new_spec.shapes[0].fill_color == "#EF4444"
        assert new_spec.shapes[0].component_id == "right.box"
        # 다른 element 보존
        assert new_spec.textboxes == spec.textboxes
        assert new_spec.background_color == spec.background_color
        assert new_spec.grid_plan == spec.grid_plan
        assert new_spec.speaker_notes == spec.speaker_notes
        # design_doc 트리 구조 보존 (bbox_changed=False)
        assert new_spec.design_doc == spec.design_doc

    def test_modifies_only_target_textbox(self) -> None:
        spec = _full_content_slide()
        svc = self._make_service(
            ComponentModifyOutput(
                element_kind="textbox",
                textbox=_textbox_output_renamed(),
                bbox_changed=False,
            )
        )
        new_spec = svc.modify_component(
            spec=spec,
            component_id="left.title",
            instruction="Rename the title",
        )
        # 대상 textbox 만 변경
        assert new_spec.textboxes[0].paragraphs[0].runs[0].text == "새 제목"
        # 두 번째 textbox(left.body) 보존
        assert new_spec.textboxes[1] == spec.textboxes[1]
        # shape 보존
        assert new_spec.shapes == spec.shapes

    def test_bbox_changed_syncs_design_doc(self) -> None:
        spec = _full_content_slide()
        moved = _shape_output_red().model_copy(
            update={"left_px": 720, "top_px": 320, "width_px": 160, "height_px": 80}
        )
        svc = self._make_service(
            ComponentModifyOutput(
                element_kind="shape",
                shape=moved,
                bbox_changed=True,
            )
        )
        new_spec = svc.modify_component(
            spec=spec,
            component_id="right.box",
            instruction="Shift smaller",
        )
        # element bbox
        assert new_spec.shapes[0].left_px == 720
        assert new_spec.shapes[0].width_px == 160
        # design_doc 의 동일 id 노드 bbox 와 동기화
        right = [n for n in new_spec.design_doc.layout if n.id == "right"][0]
        right_box = [c for c in right.children if c.id == "right.box"][0]
        assert right_box.left_px == 720
        assert right_box.width_px == 160
        # 부모/형제 노드는 그대로
        assert right.left_px == 656
        left = [n for n in new_spec.design_doc.layout if n.id == "left"][0]
        assert left.left_px == 64

    def test_design_doc_none_raises(self) -> None:
        spec = PptxSlideSpec(
            background_color="#000",
            slide_type="title",
            design_doc=None,
        )
        svc = self._make_service(
            ComponentModifyOutput(element_kind="shape", shape=_shape_output_red())
        )
        with pytest.raises(ValueError, match="modify_component requires"):
            svc.modify_component(spec=spec, component_id="x", instruction="anything")

    def test_unknown_component_id_raises(self) -> None:
        spec = _full_content_slide()
        svc = self._make_service(
            ComponentModifyOutput(element_kind="shape", shape=_shape_output_red())
        )
        with pytest.raises(ValueError, match="component_id not found"):
            svc.modify_component(spec=spec, component_id="no.such", instruction="x")

    def test_kind_mismatch_rejected(self) -> None:
        """LLM 이 textbox 인데 shape 으로 응답하면 ValueError."""
        spec = _full_content_slide()
        svc = self._make_service(
            ComponentModifyOutput(
                element_kind="shape",  # 잘못된 kind (left.title 은 textbox)
                shape=_shape_output_red(),
            )
        )
        with pytest.raises(ValueError, match="element_kind=shape"):
            svc.modify_component(spec=spec, component_id="left.title", instruction="x")


# ---------------------------------------------------------------------------
# handle_modify_component 통합 (mcp_tools 를 거치지 않고 직접 호출)
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_with_full_slide(tmp_path: Path, monkeypatch) -> tuple[str, Path]:
    """5단 계층이 채워진 슬라이드 1 개를 갖는 프로젝트 fixture."""
    import ppt_generator.tools.project.service as svc_module

    monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

    project_id = "test_proj"
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(
            {"topic": "t", "num_slides": 1, "steps_completed": {}}, ensure_ascii=False
        ),
        encoding="utf-8",
    )

    project_service = ProjectService()
    spec = _full_content_slide()
    from ppt_generator.interfaces.schemas import DesignSpec

    project_service.save_design_spec(project_dir, DesignSpec(slides=[spec]))
    project_service.save_outline(
        project_dir,
        json.dumps(
            {
                "slides": [
                    {
                        "title": "t",
                        "content_summary": "c",
                        "component_hint": "bullets",
                        "speaker_notes": "",
                        "slide_type": "content",
                    }
                ]
            },
            ensure_ascii=False,
        ),
    )
    return project_id, project_dir


@pytest.fixture()
def mcp_tools_for_modify(project_with_full_slide):
    """register_design_tools 가 등록한 MCP 도구 dict 반환."""
    project_id, _ = project_with_full_slide
    project_service = ProjectService()

    mcp = MagicMock()
    tools: dict = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator

    design_service = MagicMock()
    design_service.last_token_usage = {}

    def factory(slide_type="content", budget_tokens=8192):
        return design_service

    register_design_tools(mcp, project_service, design_service_factory=factory)
    tools["_design_service"] = design_service
    return project_id, tools


class TestModifyComponentTool:
    def test_modify_shape_via_tool(self, mcp_tools_for_modify) -> None:
        project_id, tools = mcp_tools_for_modify
        ds = tools["_design_service"]
        # design_service.modify_component 가 fill_color 만 바꾼 spec 반환하도록 설정
        spec = _full_content_slide()
        from dataclasses import replace as _replace

        new_shapes = list(spec.shapes)
        new_shapes[0] = _replace(new_shapes[0], fill_color="#EF4444")
        ds.modify_component.return_value = _replace(spec, shapes=new_shapes)

        result = json.loads(
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="Make the LLM box red",
            )
        )
        assert result["project_id"] == project_id
        assert result["component_id"] == "right.box"
        assert result["modified_element"] == {"type": "shape", "index": 0}
        # design_service.modify_component 가 호출됨
        assert ds.modify_component.called
        call_kwargs = ds.modify_component.call_args.kwargs
        assert call_kwargs["component_id"] == "right.box"
        assert call_kwargs["instruction"] == "Make the LLM box red"

    def test_invalid_slide_index_raises(self, mcp_tools_for_modify) -> None:
        project_id, tools = mcp_tools_for_modify
        with pytest.raises(ValueError, match="valid range"):
            tools["modify_component"](
                project_id=project_id,
                slide_index=99,
                component_id="x",
                instruction="y",
            )

    def test_empty_instruction_raises(self, mcp_tools_for_modify) -> None:
        project_id, tools = mcp_tools_for_modify
        with pytest.raises(ValueError, match="instruction is required"):
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="   ",
            )

    def test_design_doc_none_slide_raises(self, tmp_path: Path, monkeypatch) -> None:
        """design_doc=None 슬라이드(title slide) 에서는 명확한 에러."""
        import ppt_generator.tools.project.service as svc_module
        from ppt_generator.interfaces.schemas import DesignSpec

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        project_id = "title_proj"
        project_dir = tmp_path / project_id
        project_dir.mkdir()
        (project_dir / "project.json").write_text(
            json.dumps(
                {"topic": "t", "num_slides": 1, "steps_completed": {}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        ps = ProjectService()
        title_spec = PptxSlideSpec(
            background_color=None, slide_type="title", design_doc=None
        )
        ps.save_design_spec(project_dir, DesignSpec(slides=[title_spec]))

        mcp = MagicMock()
        tools: dict = {}

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func

            return decorator

        mcp.tool = tool_decorator
        ds_mock = MagicMock()
        ds_mock.last_token_usage = {}

        def factory(slide_type="content", budget_tokens=8192):
            return ds_mock

        register_design_tools(mcp, ps, design_service_factory=factory)

        with pytest.raises(ValueError, match="has no design_doc"):
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="anything",
                instruction="x",
            )


# ---------------------------------------------------------------------------
# ADR-0049 결정 11: z_index / grid_cell 보존
# ---------------------------------------------------------------------------


class TestModifyComponentMetaPreservation:
    def _make_service(self, structured: ComponentModifyOutput) -> DesignService:
        agent = MagicMock()
        result = MagicMock()
        result.structured_output = structured
        result.metrics = None
        agent.return_value = result
        return DesignService(agent=agent)

    def test_z_index_preserved_on_shape_modify(self) -> None:
        from dataclasses import replace as _r

        spec = _full_content_slide()
        # 기존 shape 에 z_index 부여 (imported PPTX 처럼)
        new_shape0 = _r(spec.shapes[0], z_index=42)
        spec = _r(spec, shapes=[new_shape0])

        # LLM 응답은 색만 바꾼 ShapeOutput (z_index schema 자체에 없음)
        svc = self._make_service(
            ComponentModifyOutput(
                element_kind="shape",
                shape=_shape_output_red(),
                bbox_changed=False,
            )
        )
        new_spec = svc.modify_component(
            spec=spec, component_id="right.box", instruction="red"
        )
        assert new_spec.shapes[0].fill_color == "#EF4444"
        # z_index 가 LLM schema 에 없어도 코드가 기존값 보존
        assert new_spec.shapes[0].z_index == 42

    def test_z_index_preserved_on_textbox_modify(self) -> None:
        from dataclasses import replace as _r

        spec = _full_content_slide()
        new_tb0 = _r(spec.textboxes[0], z_index=7)
        spec = _r(spec, textboxes=[new_tb0, spec.textboxes[1]])

        svc = self._make_service(
            ComponentModifyOutput(
                element_kind="textbox",
                textbox=_textbox_output_renamed(),
                bbox_changed=False,
            )
        )
        new_spec = svc.modify_component(
            spec=spec, component_id="left.title", instruction="rename"
        )
        assert new_spec.textboxes[0].z_index == 7

    def test_grid_cell_preserved_when_llm_omits(self) -> None:
        """LLM 이 grid_cell 을 빠뜨려도 (None 으로) 기존값 유지."""
        spec = _full_content_slide()
        # LLM 이 grid_cell 누락 (None) 한 응답
        from copy import deepcopy

        out = ComponentModifyOutput(
            element_kind="shape",
            shape=_shape_output_red().model_copy(update={"grid_cell": None}),
            bbox_changed=False,
        )
        svc = self._make_service(out)
        new_spec = svc.modify_component(
            spec=spec, component_id="right.box", instruction="red"
        )
        # 원래 grid_cell="c2" 보존
        assert new_spec.shapes[0].grid_cell == "c2"


# ---------------------------------------------------------------------------
# 갭 3: ambiguous component_id (textbox/shape 양쪽 매칭) 차단
# ---------------------------------------------------------------------------


class TestAmbiguousComponentId:
    def test_ambiguous_raises(self) -> None:
        from dataclasses import replace as _r

        spec = _full_content_slide()
        # textbox 와 shape 가 같은 component_id 를 가짐 (불량 LLM 출력 시뮬레이션)
        spec = _r(
            spec,
            textboxes=[
                _r(spec.textboxes[0], component_id="dup"),
                spec.textboxes[1],
            ],
            shapes=[_r(spec.shapes[0], component_id="dup")],
        )
        with pytest.raises(ValueError, match="ambiguous"):
            _find_element_by_component_id(spec, "dup")
