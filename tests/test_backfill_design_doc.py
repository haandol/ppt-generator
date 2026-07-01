"""imported 슬라이드 design_doc lazy backfill 테스트.

DesignService.ingest_backfill + _apply_backfill_output + prepare/ingest
backfill 오프로딩 분기를 검증.

LLM 생성은 클라이언트가 수행하므로, 서버 도구는 prepare_modify_component 로 backfill
태스크(stage="backfill")를 반환하고, ingest_backfill 로 검증·저장한다. mock
design_service.ingest_backfill 이 backfilled spec 을 반환하므로 전달하는 JSON 문자열은
무의미하다 — 여기선 서버의 파일 저장/검증 오케스트레이션만 검증한다.
"""

from __future__ import annotations

import json
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
        """이미 design_doc 있으면 ingest_backfill 은 그대로 반환 (재검증 없음)."""
        svc = DesignService()
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
        # design_doc 이 이미 있으면 output_json 을 파싱하지 않고 spec 을 그대로 돌려준다.
        out = svc.ingest_backfill(spec, "{}")
        assert out is spec


# ---------------------------------------------------------------------------
# DesignService.ingest_backfill (클라이언트 생성 JSON 검증 → design_doc 채움)
# ---------------------------------------------------------------------------


class TestIngestBackfillService:
    def test_full_flow(self) -> None:
        """imported spec + 유효한 backfill JSON → design_doc/component_id 채워짐."""
        spec = _imported_slide()
        svc = DesignService()
        output_json = _backfill_output_for_imported().model_dump_json()
        new_spec = svc.ingest_backfill(spec, output_json)
        assert new_spec.design_doc is not None
        assert new_spec.textboxes[0].component_id == "header.title"


# ---------------------------------------------------------------------------
# prepare_modify_component / ingest_backfill lazy backfill 통합
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

    # prepare/ingest 를 노출하는 mock DesignService.
    design_service = MagicMock()
    design_service.prepare_backfill.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }
    design_service.prepare_modify_component.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }

    register_design_tools(mcp, project_service, design_service=design_service)
    return project_id, project_dir, project_service, design_service, tools


class TestModifyComponentBackfillIntegration:
    def test_prepare_returns_backfill_stage_for_imported(
        self, mcp_tools_with_imported
    ) -> None:
        """imported 슬라이드(design_doc=None)면 prepare 는 stage='backfill' 태스크를 반환한다."""
        project_id, project_dir, project_service, ds, tools = mcp_tools_with_imported

        result = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="unknown.id",
                instruction="x",
            )
        )
        # design_doc 이 없으므로 backfill 태스크
        assert result["stage"] == "backfill"
        assert result["component_id"] == "unknown.id"
        # prepare_backfill 이 호출되고, modify 프롬프트는 조립되지 않음
        assert ds.prepare_backfill.call_count == 1
        assert ds.prepare_modify_component.call_count == 0

    def test_ingest_backfill_saves_design_doc_and_returns_components(
        self, mcp_tools_with_imported
    ) -> None:
        """ingest_backfill 은 backfilled spec 을 저장하고 available_components 를 반환한다."""
        project_id, project_dir, project_service, ds, tools = mcp_tools_with_imported

        # mock design_service.ingest_backfill 가 backfilled spec 을 반환하도록 설정.
        def _fake_ingest_backfill(spec, output_json, slide_index=1):
            return _apply_backfill_output(spec, _backfill_output_for_imported())

        ds.ingest_backfill.side_effect = _fake_ingest_backfill

        result = json.loads(
            tools["ingest_backfill"](
                project_id=project_id,
                slide_index=1,
                backfill_json="{}",  # mock 이 고정 spec 을 반환하므로 내용 무의미
            )
        )
        assert result["status"] == "backfilled"
        assert any(c["id"] == "right.box" for c in result["available_components"])
        # spec 에 design_doc 영구 저장 확인
        saved = project_service.load_design_spec_slide(project_dir, 0)
        assert saved.design_doc is not None
        assert saved.textboxes[0].component_id == "header.title"

    def test_second_prepare_uses_saved_design_doc(
        self, mcp_tools_with_imported
    ) -> None:
        """backfill 저장 후 다시 prepare 하면 stage='modify' 태스크를 반환한다."""
        project_id, project_dir, project_service, ds, tools = mcp_tools_with_imported

        # 1st: backfill ingest 로 design_doc 저장
        def _fake_ingest_backfill(spec, output_json, slide_index=1):
            return _apply_backfill_output(spec, _backfill_output_for_imported())

        ds.ingest_backfill.side_effect = _fake_ingest_backfill
        tools["ingest_backfill"](
            project_id=project_id,
            slide_index=1,
            backfill_json="{}",
        )

        # 2nd: 유효한 component_id 로 prepare → modify 태스크
        result = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="Make it red",
            )
        )
        assert result["stage"] == "modify"
        assert result["component_id"] == "right.box"
        # design_doc 이 이미 저장돼 backfill 은 다시 호출되지 않음
        assert ds.prepare_backfill.call_count == 0
        assert ds.prepare_modify_component.call_count == 1

    def test_backfill_failure_keeps_spec_unchanged(
        self, mcp_tools_with_imported
    ) -> None:
        """ingest_backfill 검증 실패 시 ValueError, spec 은 보존된다."""
        project_id, project_dir, project_service, ds, tools = mcp_tools_with_imported
        ds.ingest_backfill.side_effect = RuntimeError("bad backfill json")

        with pytest.raises(ValueError, match="design_doc backfill failed"):
            tools["ingest_backfill"](
                project_id=project_id,
                slide_index=1,
                backfill_json="{}",
            )
        # spec 보존
        saved = project_service.load_design_spec_slide(project_dir, 0)
        assert saved.design_doc is None
        assert saved.textboxes[0].component_id is None
