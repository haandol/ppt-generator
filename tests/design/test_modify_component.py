"""modify_component 테스트 (prepare/ingest 오프로딩).

LLM 생성은 클라이언트가 수행하므로, 서버의 결정론적 후처리만 검증한다:
- DesignService.ingest_modify_component: element_kind 검증, 대상 element 만 교체,
  z_index/grid_cell 보존, bbox_changed 시 design_doc.layout 동기화.
- prepare_modify_component + ingest_modify_component 도구: 파일 로드/저장/lint 오케스트레이션.

DesignService 는 더 이상 agent 를 갖지 않는다. ingest_modify_component 에 넘기는 JSON 은
클라이언트가 생성한 ComponentModifyOutput 을 시뮬레이션한다 (여기서 직렬화해서 전달).
도구 레벨 테스트에서는 mock design_service 가 고정된 spec 을 반환하므로 modify_json 은
"{}" 로 넘겨도 무방하다.
"""

from __future__ import annotations

import json
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


def _ingest(spec: PptxSlideSpec, component_id: str, output: ComponentModifyOutput):
    """클라이언트가 생성한 ComponentModifyOutput 을 JSON 으로 직렬화해 ingest 한다.

    LLM 호출이 클라이언트로 오프로딩되었으므로, 서버 서비스는 JSON 을 검증·적용만 한다.
    """
    svc = DesignService()
    return svc.ingest_modify_component(
        spec=spec,
        component_id=component_id,
        output_json=output.model_dump_json(),
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
# DesignService.ingest_modify_component (LLM 후처리 검증)
# ---------------------------------------------------------------------------


class TestModifyComponentPromptInvariance:
    """동작 불변: prepare_modify_component 이 조립하는 프롬프트/스키마 회귀 가드.

    오프로딩 이전 modify_component 는 design_service_factory("content") 로 만든
    agent 를 재사용했으므로 시스템 프롬프트가 content 디자인 시스템 프롬프트였다
    (COMPONENT_MODIFY_SYSTEM_PROMPT 는 어떤 agent 에도 연결되지 않은 미사용 상수).
    prepare 가 그 프롬프트를 그대로 재현하는지 잠근다.
    """

    def test_system_prompt_matches_content_design_prompt(self) -> None:
        from ppt_generator.interfaces.constants import DESIGN_SPEC_SYSTEM_PROMPTS

        spec = _full_content_slide()
        task = DesignService().prepare_modify_component(
            spec=spec,
            component_id="right.box",
            instruction="빨갛게",
            slide_index=1,
            color_theme="dark",
        )
        assert task["system_prompt"] == DESIGN_SPEC_SYSTEM_PROMPTS["content"]

    def test_user_prompt_contains_instruction_and_target(self) -> None:
        spec = _full_content_slide()
        task = DesignService().prepare_modify_component(
            spec=spec,
            component_id="right.box",
            instruction="LLM 박스를 빨갛게",
            slide_index=1,
            color_theme="dark",
        )
        assert "LLM 박스를 빨갛게" in task["user_prompt"]
        assert "right.box" in task["user_prompt"]
        assert "response_schema" in task

    def test_response_schema_is_component_modify(self) -> None:
        spec = _full_content_slide()
        task = DesignService().prepare_modify_component(
            spec=spec,
            component_id="right.box",
            instruction="빨갛게",
            slide_index=1,
        )
        assert task["response_schema"] == ComponentModifyOutput.model_json_schema()


class TestDesignServiceModifyComponent:
    def test_modifies_only_target_shape(self) -> None:
        spec = _full_content_slide()
        new_spec = _ingest(
            spec,
            "right.box",
            ComponentModifyOutput(
                element_kind="shape",
                shape=_shape_output_red(),
                bbox_changed=False,
            ),
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
        new_spec = _ingest(
            spec,
            "left.title",
            ComponentModifyOutput(
                element_kind="textbox",
                textbox=_textbox_output_renamed(),
                bbox_changed=False,
            ),
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
        new_spec = _ingest(
            spec,
            "right.box",
            ComponentModifyOutput(
                element_kind="shape",
                shape=moved,
                bbox_changed=True,
            ),
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
        with pytest.raises(ValueError, match="modify_component requires"):
            _ingest(
                spec,
                "x",
                ComponentModifyOutput(element_kind="shape", shape=_shape_output_red()),
            )

    def test_unknown_component_id_raises(self) -> None:
        spec = _full_content_slide()
        with pytest.raises(ValueError, match="component_id not found"):
            _ingest(
                spec,
                "no.such",
                ComponentModifyOutput(element_kind="shape", shape=_shape_output_red()),
            )

    def test_kind_mismatch_rejected(self) -> None:
        """LLM 이 textbox 인데 shape 으로 응답하면 ValueError."""
        spec = _full_content_slide()
        with pytest.raises(ValueError, match="element_kind=shape"):
            _ingest(
                spec,
                "left.title",  # left.title 은 textbox
                ComponentModifyOutput(
                    element_kind="shape",  # 잘못된 kind
                    shape=_shape_output_red(),
                ),
            )


# ---------------------------------------------------------------------------
# prepare_modify_component + ingest_modify_component 도구 통합
# (mcp_tools 를 거치지 않고 등록된 도구 함수를 직접 호출)
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


def _register(project_service: ProjectService) -> tuple[dict, MagicMock]:
    """register_design_tools 를 mock MCP 에 적용해 (도구 dict, mock design_service) 반환.

    conftest 의 mock 패턴을 그대로 따른다: prepare_* 는 stub 태스크 dict 를,
    ingest_modify_component / ingest_backfill 은 새 spec 을 반환한다.
    """
    mcp = MagicMock()
    tools: dict = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator

    design_service = MagicMock()
    design_service.prepare_modify_component.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }
    design_service.prepare_backfill.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }

    register_design_tools(mcp, project_service, design_service=design_service)
    tools["_design_service"] = design_service
    return tools, design_service


@pytest.fixture()
def mcp_tools_for_modify(project_with_full_slide):
    """register_design_tools 가 등록한 MCP 도구 dict 반환."""
    project_id, _ = project_with_full_slide
    project_service = ProjectService()
    tools, _ = _register(project_service)
    return project_id, tools


class TestModifyComponentTool:
    def test_prepare_returns_modify_stage(self, mcp_tools_for_modify) -> None:
        """design_doc 이 있는 content 슬라이드는 stage='modify' 를 반환."""
        project_id, tools = mcp_tools_for_modify
        result = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="Make the LLM box red",
            )
        )
        assert result["stage"] == "modify"
        assert result["project_id"] == project_id
        assert result["slide_index"] == 1
        assert result["component_id"] == "right.box"
        # design_service.prepare_modify_component 가 호출됨
        ds = tools["_design_service"]
        assert ds.prepare_modify_component.called
        call_kwargs = ds.prepare_modify_component.call_args.kwargs
        assert call_kwargs["component_id"] == "right.box"
        assert call_kwargs["instruction"] == "Make the LLM box red"

    def test_ingest_modify_shape_via_tool(self, mcp_tools_for_modify) -> None:
        project_id, tools = mcp_tools_for_modify
        ds = tools["_design_service"]
        # design_service.ingest_modify_component 가 fill_color 만 바꾼 spec 반환하도록 설정
        spec = _full_content_slide()
        from dataclasses import replace as _replace

        new_shapes = list(spec.shapes)
        new_shapes[0] = _replace(new_shapes[0], fill_color="#EF4444")
        ds.ingest_modify_component.return_value = _replace(spec, shapes=new_shapes)

        result = json.loads(
            tools["ingest_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                modify_json="{}",
            )
        )
        assert result["project_id"] == project_id
        assert result["component_id"] == "right.box"
        assert result["modified_element"] == {"type": "shape", "index": 0}
        # design_service.ingest_modify_component 가 호출됨
        assert ds.ingest_modify_component.called
        call_kwargs = ds.ingest_modify_component.call_args.kwargs
        assert call_kwargs["component_id"] == "right.box"

    def test_invalid_slide_index_raises(self, mcp_tools_for_modify) -> None:
        project_id, tools = mcp_tools_for_modify
        with pytest.raises(ValueError, match="valid range"):
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=99,
                component_id="x",
                instruction="y",
            )

    def test_empty_instruction_raises(self, mcp_tools_for_modify) -> None:
        project_id, tools = mcp_tools_for_modify
        with pytest.raises(ValueError, match="instruction is required"):
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction=" ",
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

        tools, _ = _register(ps)

        # title 슬라이드는 backfill 불가 → content 전용 에러
        with pytest.raises(ValueError, match="no design_doc"):
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="anything",
                instruction="x",
            )


# ---------------------------------------------------------------------------
# imported 슬라이드 lazy backfill: prepare(stage="backfill") → ingest_backfill → retry
# ---------------------------------------------------------------------------


@pytest.fixture()
def imported_project_with_content_slide(
    tmp_path: Path, monkeypatch
) -> tuple[str, Path]:
    """design_doc=None content 슬라이드 1 개를 갖는 imported 프로젝트 fixture."""
    import ppt_generator.tools.project.service as svc_module

    monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

    project_id = "imported_proj"
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(
            {
                "topic": "t",
                "num_slides": 1,
                "steps_completed": {},
                "source": "imported",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    from ppt_generator.interfaces.schemas import DesignSpec

    ps = ProjectService()
    # design_doc=None, slide_type="content" — backfill 가능한 imported 슬라이드
    imported_spec = PptxSlideSpec(
        background_color="#0F172A",
        textboxes=[
            PptxTextBox(
                left_px=64,
                top_px=148,
                width_px=560,
                height_px=80,
                paragraphs=[
                    PptxParagraph(runs=[PptxTextRun(text="제목", font_size_pt=22)])
                ],
            )
        ],
        shapes=[],
        slide_type="content",
        design_doc=None,
    )
    ps.save_design_spec(project_dir, DesignSpec(slides=[imported_spec]))
    return project_id, project_dir


class TestModifyComponentLazyBackfill:
    def test_prepare_returns_backfill_stage(
        self, imported_project_with_content_slide
    ) -> None:
        """design_doc=None content 슬라이드는 stage='backfill' 태스크를 먼저 반환."""
        project_id, _ = imported_project_with_content_slide
        ps = ProjectService()
        tools, ds = _register(ps)

        result = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="whatever",
                instruction="make it red",
            )
        )
        assert result["stage"] == "backfill"
        assert result["project_id"] == project_id
        assert result["slide_index"] == 1
        # instruction/component_id 를 태스크에 실어 재호출 컨텍스트 보존
        assert result["component_id"] == "whatever"
        assert result["instruction"] == "make it red"
        # design_service.prepare_backfill 가 호출됨
        assert ds.prepare_backfill.called

    def test_ingest_backfill_returns_available_components(
        self, imported_project_with_content_slide
    ) -> None:
        """ingest_backfill 은 backfilled spec 을 저장하고 available_components 를 반환한다."""
        project_id, _ = imported_project_with_content_slide
        ps = ProjectService()
        tools, ds = _register(ps)

        # design_service.ingest_backfill 가 design_doc 이 채워진 spec 을 반환하도록 설정
        backfilled = _full_content_slide()
        ds.ingest_backfill.return_value = backfilled

        result = json.loads(
            tools["ingest_backfill"](
                project_id=project_id,
                slide_index=1,
                backfill_json="{}",
            )
        )
        assert result["status"] == "backfilled"
        assert result["project_id"] == project_id
        assert result["slide_index"] == 1
        # backfilled spec 의 component leaf 목록이 노출됨
        ids = {c["id"] for c in result["available_components"]}
        assert "left.title" in ids
        assert "left.body" in ids
        assert "right.box" in ids
        assert ds.ingest_backfill.called

    def test_backfill_then_retry_prepare_returns_modify(
        self, imported_project_with_content_slide
    ) -> None:
        """backfill ingest 후 재호출하면 stage='modify' 로 전환된다."""
        project_id, _ = imported_project_with_content_slide
        ps = ProjectService()
        tools, ds = _register(ps)

        # 1) 첫 prepare → backfill
        first = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="make it red",
            )
        )
        assert first["stage"] == "backfill"

        # 2) ingest_backfill 로 design_doc 채운 spec 저장
        ds.ingest_backfill.return_value = _full_content_slide()
        tools["ingest_backfill"](
            project_id=project_id,
            slide_index=1,
            backfill_json="{}",
        )

        # 3) 재호출 → 이제 design_doc 이 있으므로 stage='modify'
        second = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="make it red",
            )
        )
        assert second["stage"] == "modify"
        assert ds.prepare_modify_component.called

    def test_ingest_backfill_failure_raises(
        self, imported_project_with_content_slide
    ) -> None:
        """design_service.ingest_backfill 가 실패하면 안내 메시지와 함께 ValueError."""
        project_id, _ = imported_project_with_content_slide
        ps = ProjectService()
        tools, ds = _register(ps)

        ds.ingest_backfill.side_effect = ValueError("bad backfill output")

        with pytest.raises(ValueError, match="design_doc backfill failed"):
            tools["ingest_backfill"](
                project_id=project_id,
                slide_index=1,
                backfill_json="{}",
            )


# ---------------------------------------------------------------------------
# 결정 11: z_index / grid_cell 보존
# ---------------------------------------------------------------------------


class TestModifyComponentMetaPreservation:
    def test_z_index_preserved_on_shape_modify(self) -> None:
        from dataclasses import replace as _r

        spec = _full_content_slide()
        # 기존 shape 에 z_index 부여 (imported PPTX 처럼)
        new_shape0 = _r(spec.shapes[0], z_index=42)
        spec = _r(spec, shapes=[new_shape0])

        # LLM 응답은 색만 바꾼 ShapeOutput (z_index schema 자체에 없음)
        new_spec = _ingest(
            spec,
            "right.box",
            ComponentModifyOutput(
                element_kind="shape",
                shape=_shape_output_red(),
                bbox_changed=False,
            ),
        )
        assert new_spec.shapes[0].fill_color == "#EF4444"
        # z_index 가 LLM schema 에 없어도 코드가 기존값 보존
        assert new_spec.shapes[0].z_index == 42

    def test_z_index_preserved_on_textbox_modify(self) -> None:
        from dataclasses import replace as _r

        spec = _full_content_slide()
        new_tb0 = _r(spec.textboxes[0], z_index=7)
        spec = _r(spec, textboxes=[new_tb0, spec.textboxes[1]])

        new_spec = _ingest(
            spec,
            "left.title",
            ComponentModifyOutput(
                element_kind="textbox",
                textbox=_textbox_output_renamed(),
                bbox_changed=False,
            ),
        )
        assert new_spec.textboxes[0].z_index == 7

    def test_grid_cell_preserved_when_llm_omits(self) -> None:
        """LLM 이 grid_cell 을 빠뜨려도 (None 으로) 기존값 유지."""
        spec = _full_content_slide()
        # LLM 이 grid_cell 누락 (None) 한 응답
        out = ComponentModifyOutput(
            element_kind="shape",
            shape=_shape_output_red().model_copy(update={"grid_cell": None}),
            bbox_changed=False,
        )
        new_spec = _ingest(spec, "right.box", out)
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
