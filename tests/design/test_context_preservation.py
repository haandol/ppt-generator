"""실제 준비·수신 경로의 아웃라인 계획과 근거 보존 회귀 검사."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    OutlineResponse,
    ProjectMetadata,
    SlideOutline,
)
from ppt_generator.tools.design.handlers.deps import DesignDeps
from ppt_generator.tools.design.handlers.generation import (
    handle_ingest_design_slide,
    handle_prepare_design_slide,
    handle_prepare_design_doc_draft,
)
from ppt_generator.tools.design.handlers.modification import (
    handle_ingest_slide_edit,
    handle_prepare_slide_edit,
)
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService


def _outline() -> SlideOutline:
    return SlideOutline(
        title="처리 지연",
        content_summary="검증 전 처리 지연 개선 가정",
        component_hint="custom",
        layout_plan="LAYOUT_MARKER: 위아래 비교, 원인에서 결과로 연결",
        source_refs=["SOURCE_MARKER: supplied-measurements"],
        assumptions=["ASSUMPTION_MARKER: 개선율은 측정 전 가정"],
        speaker_notes="검증되지 않은 가정임을 명시한다.",
    )


def _payload() -> dict:
    return {
        "grid_layout": {
            "regions": ["content"],
            "content_columns": 1,
            "content_rows": 1,
        },
        "cell_assignment": {
            "cells": [{"id": "c1", "region": "content", "row": 1, "col": 1}]
        },
        "design_doc": {
            "topic": "처리 지연",
            "layout_summary": "한 문장으로 가정을 표시한다.",
            "layout": [
                {"id": "body", "kind": "section", "cell_id": "c1"},
                {
                    "id": "body.claim",
                    "parent_id": "body",
                    "kind": "component",
                    "cell_id": "c1",
                },
            ],
        },
        "textboxes": [
            {
                "left_px": 64,
                "top_px": 200,
                "width_px": 1000,
                "height_px": 120,
                "component_id": "body.claim",
                "grid_cell": "c1",
                "paragraphs": [
                    {
                        "runs": [
                            {"text": "측정 전 가정: 처리 지연 개선", "font_size_pt": 24}
                        ]
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize("summary", [None, {"background_color": "#FFFFFF"}])
def test_slide_prepare_keeps_plan_sources_and_assumptions(summary: dict | None) -> None:
    task = DesignService().prepare_slide(_outline(), design_summary=summary)
    data = json.loads(task["user_prompt"].split("<input>")[1].split("</input>")[0])
    expected = asdict(_outline())
    for key in ("layout_plan", "source_refs", "assumptions", "speaker_notes"):
        assert data[key] == expected[key]


def test_draft_prepare_keeps_plan_and_evidence() -> None:
    task = DesignService().prepare_design_doc_draft(OutlineResponse([_outline()]))
    for marker in ("LAYOUT_MARKER", "SOURCE_MARKER", "ASSUMPTION_MARKER"):
        assert marker in task["user_prompt"]


def test_adjacent_context_keeps_structure_and_evidence_but_omits_notes() -> None:
    task = DesignService().prepare_slide(_outline(), prev_outline=_outline())
    data = json.loads(
        task["user_prompt"].split("<previous_slide>")[1].split("</previous_slide>")[0]
    )
    for key in ("layout_plan", "source_refs", "assumptions"):
        assert data[key] == asdict(_outline())[key]
    assert "speaker_notes" not in data


@pytest.fixture
def real_project(tmp_path: Path, monkeypatch) -> tuple[DesignDeps, str, Path]:
    monkeypatch.setattr(
        "ppt_generator.tools.project.service.PPT_GENERATOR_HOME", tmp_path
    )
    projects = ProjectService()
    project_id, directory = projects.resolve_project_dir("context-test")
    projects.save_metadata(
        directory,
        ProjectMetadata(
            topic="처리 지연",
            num_slides=1,
            purpose="PURPOSE_MARKER: 투자 여부 결정",
            audience_type="executive",
            presentation_minutes=17,
        ),
    )
    projects.save_outline(
        directory, json.dumps({"slides": [asdict(_outline())]}, ensure_ascii=False)
    )
    service = DesignService()
    spec, _ = service.ingest_slide(_payload())
    projects.save_design_spec(directory, DesignSpec([spec]))
    return DesignDeps(projects, service), project_id, directory


def test_draft_handler_passes_stored_presentation_conditions(real_project) -> None:
    deps, project_id, _ = real_project
    task = json.loads(
        handle_prepare_design_doc_draft(
            deps, project_id=project_id, outline_json="", color_theme="dark"
        )
    )
    assert "PURPOSE_MARKER" in task["user_prompt"]
    assert '"audience_type": "executive"' in task["user_prompt"]
    assert '"presentation_minutes": 17' in task["user_prompt"]


@pytest.mark.parametrize("inline_content", [False, True])
def test_unchanged_content_update_keeps_all_outline_metadata(
    real_project, inline_content: bool
) -> None:
    deps, project_id, directory = real_project
    before = json.loads(deps.project_service.load_outline_slide(directory, 0))
    prepared = json.loads(
        handle_prepare_slide_edit(
            deps,
            project_id=project_id,
            action="update",
            slide_index=1,
            title=_outline().title if inline_content else "",
            content_summary=_outline().content_summary if inline_content else "",
            component_hint="custom",
            slide_type="content",
            speaker_notes=_outline().speaker_notes,
            color_theme="dark",
        )
    )
    handle_ingest_slide_edit(
        deps,
        project_id=project_id,
        action="update",
        slide_index=1,
        spec_json=json.dumps(_payload(), ensure_ascii=False),
        edit_context=prepared["edit_context"],
        color_theme="dark",
    )
    after = json.loads(deps.project_service.load_outline_slide(directory, 0))
    for key in ("layout_plan", "source_refs", "assumptions"):
        assert after[key] == before[key]


@pytest.mark.parametrize("stage", ["generation", "edit"])
def test_design_generation_does_not_rewrite_supplied_notes(
    real_project, stage: str
) -> None:
    deps, project_id, directory = real_project
    payload = {**_payload(), "speaker_notes": "Unrequested generated narration"}
    if stage == "generation":
        prepared = json.loads(
            handle_prepare_design_slide(
                deps,
                project_id=project_id,
                slide_index=1,
                outline_json="",
                total_slides=1,
                color_theme="dark",
            )
        )
        handle_ingest_design_slide(
            deps,
            project_id=project_id,
            slide_index=1,
            spec_json=json.dumps(payload),
            generation_context=prepared["generation_context"],
            color_theme="dark",
        )
    else:
        prepared = json.loads(
            handle_prepare_slide_edit(
                deps,
                project_id=project_id,
                action="update",
                slide_index=1,
                title="",
                content_summary="",
                component_hint="custom",
                slide_type="content",
                speaker_notes="",
                color_theme="dark",
            )
        )
        handle_ingest_slide_edit(
            deps,
            project_id=project_id,
            action="update",
            slide_index=1,
            spec_json=json.dumps(payload),
            edit_context=prepared["edit_context"],
            color_theme="dark",
        )
    assert (
        deps.project_service.load_design_spec_slide(directory, 0).speaker_notes
        == _outline().speaker_notes
    )
