"""Cross-시나리오 회귀 테스트 ( 갭 점검 후속).

여러 도구를 chain 으로 호출했을 때 5단 계층 데이터가 일관되게 보존되는지 검증.
LLM 생성은 클라이언트가 하므로, 테스트는 prepare/ingest 도구 쌍을 호출하고
mock design_service 의 ingest_* 가 실제 결정론 코어(_apply_backfill_output,
DesignService.ingest_modify_component)를 통과하도록 side_effect 를 연결한다.
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
    ComponentModifyOutput,
    ShapeOutput,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.design.service import (
    DesignService,
)
from ppt_generator.tools.project.service import ProjectService


def _imported_slide_with_z_index() -> PptxSlideSpec:
    """z_index 가 부여된 imported 슬라이드 (실제 import 흐름 시뮬레이션)."""
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
                z_index=0,
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
                z_index=1,
            ),
        ],
        slide_type="content",
        grid_plan=None,
        design_doc=None,
    )


def _backfill_output() -> BackfillDesignDocOutput:
    return BackfillDesignDocOutput(
        topic="t",
        layout_summary="ls",
        nodes=[
            BackfillNode(id="header", parent_id="", kind="section"),
            BackfillNode(
                id="header.title",
                parent_id="header",
                kind="component",
                element_ref=BackfillElementRef(kind="textbox", index=0),
            ),
            BackfillNode(id="right", parent_id="", kind="section"),
            BackfillNode(
                id="right.box",
                parent_id="right",
                kind="component",
                element_ref=BackfillElementRef(kind="shape", index=0),
            ),
        ],
    )


def _shape_red() -> ShapeOutput:
    return ShapeOutput(
        left_px=700,
        top_px=300,
        width_px=200,
        height_px=100,
        shape_type="rounded_rectangle",
        fill_color="#EF4444",
        text="LLM",
        text_color="#FFFFFF",
        text_size_pt=24,
        # z_index 없음 (LLM schema 에 없음)
        # grid_cell 없음
        component_id="right.box",
    )


@pytest.fixture()
def imported_project(tmp_path: Path, monkeypatch):
    import ppt_generator.tools.project.service as svc_module

    monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

    project_id = "imported_chain"
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

    project_service = ProjectService()
    project_service.save_design_spec(
        project_dir, DesignSpec(slides=[_imported_slide_with_z_index()])
    )
    return project_id, project_dir, project_service


@pytest.fixture()
def chain_tools(imported_project):
    """prepare/ingest 도구를 mock MCP 에 등록한다.

    mock design_service 의 ingest_backfill / ingest_modify_component 는
    실제 결정론 코어(_apply_backfill_output / DesignService.ingest_modify_component)를
    호출하도록 side_effect 를 연결해, z_index 등 LLM schema 에 없는 필드 보존 코드가
    실제로 실행되게 한다. prepare_* 는 stub 태스크 dict 를 반환한다.
    """
    project_id, project_dir, project_service = imported_project

    mcp = MagicMock()
    tools: dict = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator

    real_svc = DesignService()

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
    # ingest_backfill / ingest_modify_component 은 실제 결정론 코어로 위임.
    design_service.ingest_backfill.side_effect = (
        lambda spec, output_json, slide_index=1: real_svc.ingest_backfill(
            spec, output_json, slide_index=slide_index
        )
    )
    design_service.ingest_modify_component.side_effect = (
        lambda spec, component_id, output_json: real_svc.ingest_modify_component(
            spec=spec, component_id=component_id, output_json=output_json
        )
    )

    register_design_tools(mcp, project_service, design_service=design_service)
    return project_id, project_dir, project_service, design_service, tools


class TestImportBackfillModifyChain:
    """import → backfill → modify_component 체인에서 z_index 보존 보장."""

    def test_z_index_preserved_through_full_chain(self, chain_tools) -> None:
        project_id, project_dir, ps, ds, tools = chain_tools

        # 1) backfill 단계: prepare_modify_component 가 component_id 매칭 실패(design_doc
        #    없음)이면 stage="backfill" 태스크를 반환한다.
        prep1 = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="unknown",
                instruction="x",
            )
        )
        assert prep1["stage"] == "backfill"

        # 클라이언트가 생성한 backfill JSON 을 ingest. mock 은 실제
        # _apply_backfill_output 를 통과하는 ingest_backfill 로 위임한다.
        result1 = json.loads(
            tools["ingest_backfill"](
                project_id=project_id,
                slide_index=1,
                backfill_json=_backfill_output().model_dump_json(),
            )
        )
        assert result1["status"] == "backfilled"

        # 저장된 spec 에서 z_index 보존 확인
        saved = ps.load_design_spec_slide(project_dir, 0)
        assert saved.textboxes[0].z_index == 0
        assert saved.shapes[0].z_index == 1
        assert saved.shapes[0].component_id == "right.box"

        # 2) modify 단계: 이제 design_doc 이 채워졌으므로 prepare 는 stage="modify".
        prep2 = json.loads(
            tools["prepare_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="Make red",
            )
        )
        assert prep2["stage"] == "modify"

        # 클라이언트가 생성한 ComponentModify JSON 을 ingest. mock 은 실제
        # DesignService.ingest_modify_component (z_index/grid_cell 보존 코드)로 위임한다.
        modify_output = ComponentModifyOutput(
            element_kind="shape",
            shape=_shape_red(),
            bbox_changed=False,
        )
        result2 = json.loads(
            tools["ingest_modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                modify_json=modify_output.model_dump_json(),
            )
        )
        assert result2["component_id"] == "right.box"

        # 최종 spec: z_index 보존 + fill_color 변경 + grid_cell 보존
        final = ps.load_design_spec_slide(project_dir, 0)
        assert final.shapes[0].fill_color == "#EF4444"
        assert final.shapes[0].z_index == 1  # ★ 핵심: LLM schema 없는 필드 보존
        # backfill 시 grid_cell 은 None 이었음 → 그대로 유지
        assert final.shapes[0].grid_cell is None
        # textbox 는 변경 안 됐으므로 z_index 그대로
        assert final.textboxes[0].z_index == 0

    def test_lint_runs_on_backfilled_spec_without_link_violations(
        self, chain_tools
    ) -> None:
        """backfill 결과는 component-id-link lint 를 깨끗이 통과해야 한다."""
        from ppt_generator.interfaces.spec_utils import lint_slide_spec

        project_id, project_dir, ps, ds, tools = chain_tools

        # backfill 단계까지 진행 (prepare → ingest_backfill).
        tools["prepare_modify_component"](
            project_id=project_id,
            slide_index=1,
            component_id="unknown",
            instruction="x",
        )
        tools["ingest_backfill"](
            project_id=project_id,
            slide_index=1,
            backfill_json=_backfill_output().model_dump_json(),
        )

        saved = ps.load_design_spec_slide(project_dir, 0)
        result = lint_slide_spec(saved)
        link_violations = [
            v for v in result.violations if v.rule.startswith("component-id-link")
        ]
        assert link_violations == []
