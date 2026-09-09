"""실제 입력·저장·편집 경로의 호환성 반례를 고정한다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ppt_generator.interfaces.schemas import DesignSpec, ProjectMetadata
from ppt_generator.tools.design.handlers.deps import DesignDeps
from ppt_generator.tools.design.handlers.generation import (
    handle_ingest_design_doc_draft,
    handle_prepare_design_doc_draft,
)
from ppt_generator.tools.design.handlers.modification import (
    handle_ingest_slide_edit,
    handle_move,
    handle_prepare_slide_edit,
)
from ppt_generator.tools.design.handlers.review import (
    handle_ingest_review,
    handle_prepare_review,
)
from ppt_generator.tools.design.review_service import DesignReviewService
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService

from .test_context_preservation import _payload
from .test_design_intent_contracts import _draft


def outline(title: str = "Body") -> dict:
    """필수 발표 구조를 갖춘 아웃라인을 만든다."""
    return {
        "slides": [
            {
                "title": name,
                "content_summary": f"Content {index}",
                "component_hint": hint,
                "slide_type": kind,
                "layout_plan": "One statement",
                "speaker_notes": "",
                "source_refs": [],
                "assumptions": [],
            }
            for index, (name, hint, kind) in enumerate(
                [
                    ("Title", "bullets", "title"),
                    ("Agenda", "agenda", "content"),
                    (title, "custom", "content"),
                    ("Close", "cta", "closing"),
                ]
            )
        ]
    }


def draft(title: str = "Body") -> dict:
    """본문 슬라이드에 유효한 특별 요청을 넣는다."""
    value = _draft()
    value["page_requests"] = [{"number": 3, "title": title, "request": "큰 주장"}]
    return value


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> tuple[DesignDeps, str, Path]:
    monkeypatch.setattr(
        "ppt_generator.tools.project.service.PPT_GENERATOR_HOME", tmp_path
    )
    projects = ProjectService()
    pid, directory = projects.resolve_project_dir("release-test")
    service = DesignService()
    spec, _ = service.ingest_slide({**_payload(), "background_color": "#CCDDEE"})
    projects.save_design_spec(directory, DesignSpec([spec] * 4))
    projects.save_design_summary(directory, {"background_color": "#112233"})
    projects.save_metadata(directory, ProjectMetadata(num_slides=4))
    projects.save_outline(directory, json.dumps(outline()))
    return (
        DesignDeps(projects, service, review_service=DesignReviewService()),
        pid,
        directory,
    )


def test_inline_draft_uses_prepared_outline_without_overwriting_saved_outline(
    project,
) -> None:
    deps, pid, directory = project
    before = deps.project_service.load_outline(directory)
    handle_prepare_design_doc_draft(
        deps,
        project_id=pid,
        outline_json=json.dumps(outline("Inline")),
        color_theme="dark",
    )
    handle_ingest_design_doc_draft(
        deps, project_id=pid, draft_json=json.dumps(draft("Inline")), color_theme="dark"
    )
    assert "Inline" in (directory / "DESIGN.md").read_text()
    assert deps.project_service.load_outline(directory) == before


def test_inline_draft_can_create_project_without_a_saved_outline(project) -> None:
    deps, _, _ = project
    prepared = json.loads(
        handle_prepare_design_doc_draft(
            deps, project_id="", outline_json=json.dumps(outline()), color_theme="dark"
        )
    )
    result = json.loads(
        handle_ingest_design_doc_draft(
            deps,
            project_id=prepared["project_id"],
            draft_json=json.dumps(draft()),
            color_theme="dark",
        )
    )
    assert Path(result["design_doc_path"]).exists()


def test_exact_title_with_surrounding_whitespace_is_accepted(project) -> None:
    deps, pid, directory = project
    deps.project_service.save_outline(directory, json.dumps(outline("  Body  ")))
    handle_prepare_design_doc_draft(
        deps, project_id=pid, outline_json="", color_theme="dark"
    )
    handle_ingest_design_doc_draft(
        deps,
        project_id=pid,
        draft_json=json.dumps(draft("  Body  ")),
        color_theme="dark",
    )
    assert (directory / "DESIGN.md").exists()


def test_saved_outline_changed_after_draft_prepare_is_rejected(project) -> None:
    deps, pid, directory = project
    handle_prepare_design_doc_draft(
        deps, project_id=pid, outline_json="", color_theme="dark"
    )
    deps.project_service.save_outline(directory, json.dumps(outline("Changed")))
    with pytest.raises(ValueError, match="Stale"):
        handle_ingest_design_doc_draft(
            deps, project_id=pid, draft_json=json.dumps(draft()), color_theme="dark"
        )
    assert not (directory / "DESIGN.md").exists()


@pytest.mark.parametrize("source", ["generated", "imported"])
def test_edit_preserves_explicit_slide_color(project, source: str) -> None:
    deps, pid, directory = project
    deps.project_service.save_metadata(
        directory, ProjectMetadata(num_slides=4, source=source)
    )
    prepared = json.loads(
        handle_prepare_slide_edit(
            deps,
            project_id=pid,
            action="update",
            slide_index=3,
            title="Body",
            content_summary="Content 2",
            component_hint="custom",
            slide_type="content",
            speaker_notes="",
            color_theme="dark",
        )
    )
    handle_ingest_slide_edit(
        deps,
        project_id=pid,
        action="update",
        slide_index=3,
        spec_json=json.dumps({**_payload(), "background_color": "#CCDDEE"}),
        edit_context=prepared["edit_context"],
        color_theme="dark",
    )
    assert (
        deps.project_service.load_design_spec_slide(directory, 2).background_color
        == "#CCDDEE"
    )


def test_single_slide_review_rejects_changed_design_intent(project) -> None:
    deps, pid, directory = project
    deps.project_service.save_design_doc_md(directory, "## 톤 & 방향\nBefore")
    prepared = json.loads(handle_prepare_review(deps, project_id=pid, slide_index=3))
    deps.project_service.save_design_doc_md(directory, "## 톤 & 방향\nAfter")
    with pytest.raises(ValueError, match="Stale"):
        handle_ingest_review(
            deps,
            project_id=pid,
            slide_index=3,
            review_json='{"has_high_severity": false, "issues":[]}',
            review_context=prepared["review_context"],
        )


def test_move_keeps_numbered_request_attached_when_titles_are_duplicated(
    project,
) -> None:
    deps, pid, directory = project
    planned = outline()
    planned["slides"].insert(3, {**planned["slides"][2], "content_summary": "Other"})
    deps.project_service.save_outline(directory, json.dumps(planned))
    spec = deps.project_service.load_design_spec_slide(directory, 2)
    deps.project_service.save_design_spec(directory, DesignSpec([spec] * 5))
    deps.project_service.save_design_doc_md(
        directory, "## 페이지별 요청\n### 3. Body\nONLY_ORIGINAL\n"
    )
    handle_move(deps, project_id=pid, from_index=3, to_index=4)
    assert "ONLY_ORIGINAL" not in deps.project_service.load_design_directives(
        directory, 3
    )
    assert "ONLY_ORIGINAL" in deps.project_service.load_design_directives(directory, 4)


def test_move_rolls_back_design_intent_with_other_project_files(
    project, monkeypatch
) -> None:
    deps, pid, directory = project
    deps.project_service.save_design_doc_md(
        directory, "## 페이지별 요청\n### 3. Body\nKeep me\n"
    )
    before = (directory / "DESIGN.md").read_bytes()

    def fail(*args, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(deps.project_service, "update_step", fail)
    with pytest.raises(RuntimeError, match="injected"):
        handle_move(deps, project_id=pid, from_index=3, to_index=2)
    assert (directory / "DESIGN.md").read_bytes() == before
