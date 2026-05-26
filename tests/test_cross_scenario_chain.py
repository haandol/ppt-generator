"""Cross-시나리오 회귀 테스트 ( 갭 점검 후속).

여러 도구를 chain 으로 호출했을 때 5단 계층 데이터가 일관되게 보존되는지 검증.
LLM 호출은 MagicMock 으로 대체.
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
    ComponentModifyOutput,
    ShapeOutput,
)
from ppt_generator.interfaces.schemas import (
    DesignDoc,
    DesignSpec,
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
    _apply_backfill_output,
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
    project_id, project_dir, project_service = imported_project

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


class TestImportBackfillModifyChain:
    """import → backfill → modify_component 체인에서 z_index 보존 보장."""

    def test_z_index_preserved_through_full_chain(self, chain_tools) -> None:
        from ppt_generator.tools.design.service import DesignService

        project_id, project_dir, ps, ds, tools = chain_tools

        # 1) backfill 결과는 _apply_backfill_output 으로 시뮬레이션
        ds.backfill_design_doc.side_effect = lambda spec, slide_index=1: (
            _apply_backfill_output(spec, _backfill_output())
        )

        # 1차 호출: backfill 만 (component_id 매칭 실패)
        result1 = json.loads(
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="unknown",
                instruction="x",
            )
        )
        assert result1["status"] == "backfilled"

        # 저장된 spec 에서 z_index 보존 확인
        saved = ps.load_design_spec_slide(project_dir, 0)
        assert saved.textboxes[0].z_index == 0
        assert saved.shapes[0].z_index == 1
        assert saved.shapes[0].component_id == "right.box"

        # 2차 호출: modify_component 호출. 실제 DesignService.modify_component
        # 사용 (mock 아님) — z_index 보존 코드를 통과하는지 검증
        real_svc = DesignService(agent=MagicMock(), backfill_agent=MagicMock())
        agent_mock = real_svc._agent
        result_obj = MagicMock()
        result_obj.structured_output = ComponentModifyOutput(
            element_kind="shape",
            shape=_shape_red(),
            bbox_changed=False,
        )
        result_obj.metrics = None
        agent_mock.return_value = result_obj

        # design_service mock 의 modify_component 가 실제 메서드를 호출하도록 설정
        ds.modify_component.side_effect = lambda **kw: real_svc.modify_component(
            spec=kw["spec"],
            component_id=kw["component_id"],
            instruction=kw["instruction"],
            slide_index=kw.get("slide_index", 1),
            color_theme=kw.get("color_theme", "dark"),
        )

        result2 = json.loads(
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="right.box",
                instruction="Make red",
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
        ds.backfill_design_doc.side_effect = lambda spec, slide_index=1: (
            _apply_backfill_output(spec, _backfill_output())
        )
        tools["modify_component"](
            project_id=project_id,
            slide_index=1,
            component_id="unknown",
            instruction="x",
        )
        saved = ps.load_design_spec_slide(project_dir, 0)
        result = lint_slide_spec(saved)
        link_violations = [
            v for v in result.violations if v.rule.startswith("component-id-link")
        ]
        assert link_violations == []
