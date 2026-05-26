"""에러 로깅 회귀 테스트.

production 디버깅을 위해 검증 실패·LLM 실패·파이프라인 실패 시 적절한 logger
호출이 일어나는지 확인한다. 메시지에 핵심 식별자(project_id, slide_index,
component_id, node_id) 가 포함되어야 한다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.llm_output_models import (
    BackfillDesignDocOutput,
    BackfillElementRef,
    BackfillNode,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.design.service import _apply_backfill_output
from ppt_generator.tools.project.service import ProjectService


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _imported_slide() -> PptxSlideSpec:
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
            ),
        ],
        slide_type="content",
        design_doc=None,
    )


@pytest.fixture()
def mcp_tools(tmp_path: Path, monkeypatch):
    import ppt_generator.tools.project.service as svc_module

    monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

    project_id = "log_test"
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        json.dumps(
            {"topic": "t", "num_slides": 1, "steps_completed": {}},
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


# ---------------------------------------------------------------------------
# modify_component 검증 실패 로깅
# ---------------------------------------------------------------------------


class TestModifyComponentValidationLogging:
    def test_empty_project_id_logged(self, mcp_tools, caplog) -> None:
        _, _, _, _, tools = mcp_tools
        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            tools["modify_component"](
                project_id="",
                slide_index=1,
                component_id="x",
                instruction="y",
            )
        assert any(
            "modify_component validation failed" in r.message
            and "project_id is required" in r.message
            for r in caplog.records
        )

    def test_invalid_slide_index_logged_with_context(self, mcp_tools, caplog) -> None:
        project_id, _, _, _, tools = mcp_tools
        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            tools["modify_component"](
                project_id=project_id,
                slide_index=99,
                component_id="x",
                instruction="y",
            )
        # 식별자가 메시지에 포함되어야 함
        recs = [
            r
            for r in caplog.records
            if "modify_component validation failed" in r.message
        ]
        assert recs
        joined = " ".join(r.message for r in recs)
        assert "slide_index=99" in joined
        assert f"project_id={project_id!r}" in joined

    def test_empty_instruction_logged(self, mcp_tools, caplog) -> None:
        project_id, _, _, _, tools = mcp_tools
        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="x",
                instruction="   ",
            )
        assert any("instruction is required" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# backfill 실패 로깅
# ---------------------------------------------------------------------------


class TestBackfillFailureLogging:
    def test_backfill_exception_logs_with_identifiers(self, mcp_tools, caplog) -> None:
        project_id, _, _, ds, tools = mcp_tools
        ds.backfill_design_doc.side_effect = RuntimeError("LLM 5xx")

        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            tools["modify_component"](
                project_id=project_id,
                slide_index=1,
                component_id="x",
                instruction="y",
            )
        # error 로그에 stack trace 포함 + 식별자 포함
        backfill_errs = [
            r for r in caplog.records if "modify_component backfill failed" in r.message
        ]
        assert backfill_errs
        rec = backfill_errs[0]
        assert rec.exc_info is not None
        assert f"project_id={project_id!r}" in rec.message
        assert "slide_index=1" in rec.message


# ---------------------------------------------------------------------------
# _apply_backfill_output 검증 실패 로깅
# ---------------------------------------------------------------------------


class TestApplyBackfillLogging:
    def test_unknown_parent_logged_with_node_id(self, caplog) -> None:
        spec = _imported_slide()
        bad = BackfillDesignDocOutput(
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
        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            _apply_backfill_output(spec, bad)
        msgs = [r.message for r in caplog.records]
        joined = " ".join(msgs)
        assert "backfill validation failed" in joined
        assert "node_id='orphan'" in joined
        assert "parent_id='ghost'" in joined

    def test_duplicate_id_logged_with_position(self, caplog) -> None:
        spec = _imported_slide()
        bad = BackfillDesignDocOutput(
            topic="t",
            layout_summary="ls",
            nodes=[
                BackfillNode(id="dup", parent_id="", kind="section"),
                BackfillNode(id="dup", parent_id="", kind="section"),
            ],
        )
        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            _apply_backfill_output(spec, bad)
        joined = " ".join(r.message for r in caplog.records)
        assert "duplicate node id: dup" in joined
        assert "node_id='dup'" in joined


# ---------------------------------------------------------------------------
# lint rule 예외 격리
# ---------------------------------------------------------------------------


class TestLintRuleExceptionIsolation:
    def test_failing_rule_does_not_block_others(self, monkeypatch, caplog) -> None:
        """한 lint rule 이 예외를 던져도 나머지 rule 결과는 보존."""
        from ppt_generator.interfaces.spec_utils import lint as lint_mod

        def _bad_rule(spec, result):
            raise RuntimeError("buggy rule")

        # ALL_RULES 에 잘못된 rule 추가 (테스트 격리)
        original = list(lint_mod.ALL_RULES)
        monkeypatch.setattr(lint_mod, "ALL_RULES", original + [_bad_rule])

        spec = PptxSlideSpec(slide_type="content")
        with caplog.at_level(logging.ERROR):
            result = lint_slide_spec(spec, slide_index=3)
        # 결과 객체는 정상 반환
        assert result.slide_index == 3
        # 어느 rule 이 실패했는지 식별 가능한 로그
        msgs = [r.message for r in caplog.records]
        joined = " ".join(msgs)
        assert "_bad_rule" in joined
        assert "slide[3]" in joined


# ---------------------------------------------------------------------------
# generation 검증 로깅
# ---------------------------------------------------------------------------


class TestGenerationValidationLogging:
    def test_missing_outline_and_project_id_logged(self, caplog) -> None:
        from ppt_generator.tools.design.handlers.generation import _load_outline

        deps = MagicMock()
        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            _load_outline(deps, project_id="", outline_json="")
        assert any(
            "Either outline_json or project_id must be provided" in r.message
            for r in caplog.records
        )

    def test_invalid_slide_indices_logged(self, caplog) -> None:
        from ppt_generator.tools.design.handlers.generation import (
            _parse_slide_indices,
        )

        outline = MagicMock()
        outline.slides = [MagicMock()] * 3

        with caplog.at_level(logging.ERROR), pytest.raises(ValueError):
            _parse_slide_indices(outline, total_slides=3, slide_indices="not-numbers")
        joined = " ".join(r.message for r in caplog.records)
        assert "slide_indices parse failed" in joined
        assert "not-numbers" in joined
