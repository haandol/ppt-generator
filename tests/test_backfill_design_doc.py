"""imported 슬라이드 design_doc lazy backfill 테스트.

DesignService.backfill_design_doc + _apply_backfill_output + handle_modify_component
의 backfill 분기를 검증.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.llm_output_models import (
    BackfillDesignDocOutput,
    BackfillElementRef,
    BackfillNode,
    GridCellAssignmentOutput,
    GridCellOutput,
    GridLayoutOutput,
)
from ppt_generator.interfaces.schemas import (
    DesignDoc,
    DesignSpec,
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
    _apply_backfill_output,
    _is_decorative,
    _serialize_elements_for_backfill,
)
from ppt_generator.tools.project.service import ProjectService


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _imported_slide() -> PptxSlideSpec:
    """imported PPTX 처럼 design_doc=None / grid_plan=None / component_id=None."""
    return PptxSlideSpec(
        background_color="#0F172A",
        textboxes=[
            PptxTextBox(
                left_px=64,
                top_px=72,
                width_px=1152,
                height_px=48,
                paragraphs=[
                    PptxParagraph(
                        runs=[PptxTextRun(text="제목", font_size_pt=32, bold=True)]
                    )
                ],
            ),
            PptxTextBox(
                left_px=64,
                top_px=148,
                width_px=560,
                height_px=80,
                paragraphs=[
                    PptxParagraph(runs=[PptxTextRun(text="본문", font_size_pt=18)])
                ],
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
            ),
            # 장식 라인 (텍스트 없음, 두께 2px)
            PptxShape(
                left_px=64,
                top_px=130,
                width_px=1152,
                height_px=2,
                shape_type="line",
                border_color="#3B82F6",
            ),
        ],
        speaker_notes="",
        slide_type="content",
        grid_plan=None,
        design_doc=None,
    )


def _backfill_output_for_imported() -> BackfillDesignDocOutput:
    """LLM 이 _imported_slide 를 보고 출력했을 법한 응답."""
    return BackfillDesignDocOutput(
        topic="LLM 소개",
        layout_summary="상단에 제목, 좌측에 설명 텍스트, 우측에 LLM 박스.",
        nodes=[
            BackfillNode(id="header", parent_id="", kind="section", role="title_bar"),
            BackfillNode(
                id="header.title",
                parent_id="header",
                kind="component",
                role="slide_title",
                element_ref=BackfillElementRef(kind="textbox", index=0),
            ),
            BackfillNode(id="left", parent_id="", kind="section", role="explanation"),
            BackfillNode(
                id="left.body",
                parent_id="left",
                kind="component",
                role="card_body",
                element_ref=BackfillElementRef(kind="textbox", index=1),
            ),
            BackfillNode(id="right", parent_id="", kind="section", role="diagram"),
            BackfillNode(
                id="right.box",
                parent_id="right",
                kind="component",
                role="llm_box",
                element_ref=BackfillElementRef(kind="shape", index=0),
            ),
            # shape index 1 (장식 라인) 은 의도적으로 생략
        ],
    )


# ---------------------------------------------------------------------------
# helper unit tests
# ---------------------------------------------------------------------------


class TestSerializeElements:
    def test_serializes_text_and_bbox(self) -> None:
        spec = _imported_slide()
        out = json.loads(_serialize_elements_for_backfill(spec))
        elements = out["elements"]
        assert len(elements) == 4  # 2 textbox + 2 shape
        # textbox 0
        assert elements[0]["kind"] == "textbox"
        assert elements[0]["text"] == "제목"
        assert elements[0]["bbox"] == [64, 72, 1152, 48]
        # shape 1 = decorative line
        line = [e for e in elements if e["kind"] == "shape" and e["index"] == 1][0]
        assert line["decorative"] is True

    def test_decorative_detection(self) -> None:
        spec = _imported_slide()
        assert _is_decorative(spec.shapes[1]) is True
        assert _is_decorative(spec.shapes[0]) is False


class TestApplyBackfillOutput:
    def test_basic_apply(self) -> None:
        spec = _imported_slide()
        output = _backfill_output_for_imported()
        new_spec = _apply_backfill_output(spec, output)

        # design_doc 채워짐
        assert new_spec.design_doc is not None
        assert new_spec.design_doc.topic == "LLM 소개"
        # 트리 구조: 3 root section
        roots = new_spec.design_doc.layout
        assert {r.id for r in roots} == {"header", "left", "right"}

        # textbox/shape 의 component_id 채워짐 (장식 라인 제외)
        assert new_spec.textboxes[0].component_id == "header.title"
        assert new_spec.textboxes[1].component_id == "left.body"
        assert new_spec.shapes[0].component_id == "right.box"
        assert new_spec.shapes[1].component_id is None  # decorative

        # 텍스트/스타일/위치는 변경 없음 (원본 보존)
        assert new_spec.textboxes[0].left_px == 64
        assert new_spec.shapes[0].fill_color == "#3B82F6"
        # grid_plan 은 그대로 None
        assert new_spec.grid_plan is None

    def test_section_bbox_is_union_of_children(self) -> None:
        spec = _imported_slide()
        output = _backfill_output_for_imported()
        new_spec = _apply_backfill_output(spec, output)

        right = [r for r in new_spec.design_doc.layout if r.id == "right"][0]
        # right 만 box(700,300,200,100) 1개 자식 → bbox 동일
        assert right.left_px == 700
        assert right.top_px == 300
        assert right.width_px == 200
        assert right.height_px == 100
        # leaf component bbox == element bbox
        leaf = right.children[0]
        assert (
            leaf.left_px,
            leaf.top_px,
            leaf.width_px,
            leaf.height_px,
        ) == (700, 300, 200, 100)

    def test_section_bbox_with_multiple_children(self) -> None:
        """자식 2 개 이상이면 합집합."""
        spec = PptxSlideSpec(
            slide_type="content",
            textboxes=[
                PptxTextBox(left_px=10, top_px=10, width_px=50, height_px=50),
                PptxTextBox(left_px=100, top_px=100, width_px=50, height_px=50),
            ],
            shapes=[],
            design_doc=None,
        )
        output = BackfillDesignDocOutput(
            topic="t",
            layout_summary="ls",
            nodes=[
                BackfillNode(id="sec", parent_id="", kind="section"),
                BackfillNode(
                    id="sec.a",
                    parent_id="sec",
                    kind="component",
                    element_ref=BackfillElementRef(kind="textbox", index=0),
                ),
                BackfillNode(
                    id="sec.b",
                    parent_id="sec",
                    kind="component",
                    element_ref=BackfillElementRef(kind="textbox", index=1),
                ),
            ],
        )
        new_spec = _apply_backfill_output(spec, output)
        sec = new_spec.design_doc.layout[0]
        # union: left=10, top=10, right=150, bottom=150
        assert sec.left_px == 10
        assert sec.top_px == 10
        assert sec.width_px == 140
        assert sec.height_px == 140

    def test_missing_textbox_raises(self) -> None:
        spec = _imported_slide()
        output = _backfill_output_for_imported()
        # textbox 1 매핑 제거
        output.nodes = [n for n in output.nodes if n.id != "left.body"]
        # left section 도 비게 되니 에러는 어딘가에서 발생
        with pytest.raises(ValueError):
            _apply_backfill_output(spec, output)

    def test_duplicate_element_ref_raises(self) -> None:
        spec = _imported_slide()
        output = BackfillDesignDocOutput(
            topic="t",
            layout_summary="ls",
            nodes=[
                BackfillNode(id="s", parent_id="", kind="section"),
                BackfillNode(
                    id="s.a",
                    parent_id="s",
                    kind="component",
                    element_ref=BackfillElementRef(kind="textbox", index=0),
                ),
                BackfillNode(
                    id="s.b",
                    parent_id="s",
                    kind="component",
                    element_ref=BackfillElementRef(kind="textbox", index=0),
                ),
            ],
        )
        with pytest.raises(ValueError, match="referenced by multiple"):
            _apply_backfill_output(spec, output)

    def test_unknown_parent_id_raises(self) -> None:
        spec = _imported_slide()
        output = BackfillDesignDocOutput(
            topic="t",
            layout_summary="ls",
            nodes=[
                BackfillNode(
                    id="orphan",
                    parent_id="ghost",
                    kind="component",
                    element_ref=BackfillElementRef(kind="textbox", index=0),
                ),
            ],
        )
        with pytest.raises(ValueError, match="unknown parent_id"):
            _apply_backfill_output(spec, output)

    def test_duplicate_node_id_raises(self) -> None:
        spec = _imported_slide()
        output = BackfillDesignDocOutput(
            topic="t",
            layout_summary="ls",
            nodes=[
                BackfillNode(id="dup", parent_id="", kind="section"),
                BackfillNode(id="dup", parent_id="", kind="section"),
            ],
        )
        with pytest.raises(ValueError, match="duplicate node id"):
            _apply_backfill_output(spec, output)

    def test_grid_plan_backfilled(self) -> None:
        """LLM 이 grid_layout/cell_assignment 를 출력하면 grid_plan 이 채워진다."""
        spec = _imported_slide()
        output = _backfill_output_for_imported()
        output.grid_layout = GridLayoutOutput(
            regions=["header", "content"],
            content_columns=2,
            content_rows=1,
        )
        output.cell_assignment = GridCellAssignmentOutput(
            cells=[
                GridCellOutput(
                    id="header_main",
                    region="header",
                    row=1,
                    col=1,
                    role="title_bar",
                ),
                GridCellOutput(
                    id="left_col",
                    region="content",
                    row=1,
                    col=1,
                    role="explanation",
                ),
                GridCellOutput(
                    id="right_col",
                    region="content",
                    row=1,
                    col=2,
                    role="diagram",
                ),
            ],
        )
        new_spec = _apply_backfill_output(spec, output)
        assert new_spec.grid_plan is not None
        gp = new_spec.grid_plan
        assert gp.regions == ["header", "content"]
        assert gp.content_columns == 2
        assert gp.content_rows == 1
        assert {c.id for c in gp.cells} == {"header_main", "left_col", "right_col"}

    def test_grid_plan_omitted_keeps_none(self) -> None:
        """grid_layout 이 없으면 grid_plan 은 기존 값(None) 유지."""
        spec = _imported_slide()
        output = _backfill_output_for_imported()
        # grid_layout / cell_assignment 모두 None
        new_spec = _apply_backfill_output(spec, output)
        assert new_spec.grid_plan is None

    def test_already_has_design_doc_skipped(self) -> None:
        """이미 design_doc 있으면 backfill_design_doc 은 그대로 반환."""
        agent = MagicMock()
        backfill_agent = MagicMock()
        svc = DesignService(agent=agent, backfill_agent=backfill_agent)
        layout = [
            LayoutNode(
                id="x",
                kind="section",
                left_px=0,
                top_px=0,
                width_px=10,
                height_px=10,
            )
        ]
        spec = PptxSlideSpec(
            slide_type="content",
            design_doc=DesignDoc(topic="t", layout_summary="ls", layout=layout),
        )
        out = svc.backfill_design_doc(spec)
        assert out is spec
        assert backfill_agent.call_count == 0


# ---------------------------------------------------------------------------
# DesignService.backfill_design_doc (LLM mocked)
# ---------------------------------------------------------------------------


class TestBackfillDesignDocService:
    def _service_with_mock(self, output: BackfillDesignDocOutput) -> DesignService:
        backfill_agent = MagicMock()
        result = MagicMock()
        result.structured_output = output
        result.metrics = None
        backfill_agent.return_value = result
        return DesignService(agent=MagicMock(), backfill_agent=backfill_agent)

    def test_full_flow(self) -> None:
        spec = _imported_slide()
        svc = self._service_with_mock(_backfill_output_for_imported())
        new_spec = svc.backfill_design_doc(spec)
        assert new_spec.design_doc is not None
        assert new_spec.textboxes[0].component_id == "header.title"

    def test_missing_backfill_agent_raises(self) -> None:
        svc = DesignService(agent=MagicMock(), backfill_agent=None)
        with pytest.raises(RuntimeError, match="backfill_agent is not configured"):
            svc.backfill_design_doc(_imported_slide())


# ---------------------------------------------------------------------------
# handle_modify_component lazy backfill 분기
# ---------------------------------------------------------------------------


@pytest.fixture()
def mcp_tools_with_imported(tmp_path: Path, monkeypatch):
    import ppt_generator.tools.project.service as svc_module

    monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

    project_id = "imported_proj"
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(
            {
                "topic": "imported",
                "num_slides": 1,
                "steps_completed": {},
                "source": "imported",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    project_service = ProjectService()
    project_service.save_design_spec(
        project_dir, DesignSpec(slides=[_imported_slide()])
    )

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
    return project_id, project_dir, project_service, design_service, tools


class TestModifyComponentBackfillIntegration:
    def test_first_call_triggers_backfill_and_returns_available_components(
        self, mcp_tools_with_imported
    ) -> None:
        project_id, project_dir, project_service, ds, tools = mcp_tools_with_imported

        # design_service.backfill_design_doc 가 backfilled spec 을 반환하도록 설정
        def _fake_backfill(spec, slide_index=1):
            return _apply_backfill_output(spec, _backfill_output_for_imported())

        ds.backfill_design_doc.side_effect = _fake_backfill
        ds.last_token_usage = {"input_tokens": 100, "output_tokens": 50}

        result = json.loads(
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="unknown.id",
                instruction="x",
            )
        )
        # backfill 실행되고 unknown id → available_components 응답
        assert result["status"] == "backfilled"
        assert result["requested_component_id"] == "unknown.id"
        assert any(c["id"] == "right.box" for c in result["available_components"])
        # design_service.modify_component 는 호출되지 않음 (id 매칭 실패)
        assert ds.modify_component.call_count == 0
        # spec 에 design_doc 영구 저장 확인
        saved = project_service.load_design_spec_slide(project_dir, 0)
        assert saved.design_doc is not None
        assert saved.textboxes[0].component_id == "header.title"

    def test_second_call_uses_saved_design_doc(self, mcp_tools_with_imported) -> None:
        project_id, project_dir, project_service, ds, tools = mcp_tools_with_imported

        # 1st call: backfill
        def _fake_backfill(spec, slide_index=1):
            return _apply_backfill_output(spec, _backfill_output_for_imported())

        ds.backfill_design_doc.side_effect = _fake_backfill
        tools["modify_component"](
            project_id=project_id,
            slide_index=1,
            component_id="unknown",
            instruction="x",
        )
        # 2nd call: 정확한 id, modify_component 호출됨
        # ds.modify_component 가 spec 그대로 반환하도록 설정
        ds.modify_component.side_effect = lambda **kw: kw["spec"]
        ds.last_token_usage = {"input_tokens": 50, "output_tokens": 20}

        result = json.loads(
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="Make it red",
            )
        )
        # modify_component 가 정확히 1 회 호출 (1차에서는 호출 안 함)
        assert ds.modify_component.call_count == 1
        # backfill 은 1 회만 (2nd call 에서는 안 함)
        assert ds.backfill_design_doc.call_count == 1
        assert result["component_id"] == "right.box"
        assert "modified_element" in result

    def test_backfill_failure_keeps_spec_unchanged(
        self, mcp_tools_with_imported
    ) -> None:
        project_id, project_dir, project_service, ds, tools = mcp_tools_with_imported
        ds.backfill_design_doc.side_effect = RuntimeError("LLM failure")

        with pytest.raises(ValueError, match="design_doc backfill failed"):
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="x",
                instruction="y",
            )
        # spec 보존
        saved = project_service.load_design_spec_slide(project_dir, 0)
        assert saved.design_doc is None
        assert saved.textboxes[0].component_id is None
