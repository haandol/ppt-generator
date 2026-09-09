"""리뷰가 원래 힌트와 실제 구성을 구분하고 디자인 의도를 보존하는지 검사한다."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    OutlineResponse,
    PptxShape,
    PptxSlideSpec,
    ProjectMetadata,
    SlideOutline,
)
from ppt_generator.tools.design.handlers.deps import DesignDeps
from ppt_generator.tools.design.handlers.review import (
    handle_ingest_deck_review,
    handle_prepare_deck_review,
)
from ppt_generator.tools.design.review_service import DesignReviewService
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.visual_qa.service import VisualQAService


def _spec(*, stacked: bool = False) -> PptxSlideSpec:
    return PptxSlideSpec(
        speaker_notes="NOTES_MARKER: 공개된 측정이 없어 가정이라고 설명",
        shapes=[
            PptxShape(
                left_px=64 if stacked else 64 + i * 380,
                top_px=160 + i * 150 if stacked else 200,
                width_px=320,
                height_px=120,
                shape_type="rectangle",
                fill_color="#112233",
                text=f"업무 {i + 1}",
            )
            for i in range(3)
        ],
    )


def test_actual_geometry_changes_deck_review_input_even_when_hint_and_text_match() -> (
    None
):
    service = DesignReviewService()
    outline = OutlineResponse(
        [SlideOutline("비교", "동일 내용", component_hint="info_cards")]
    )
    row = service.prepare_deck(outline, DesignSpec([_spec()]), presentation_minutes=10)
    stack = service.prepare_deck(
        outline, DesignSpec([_spec(stacked=True)]), presentation_minutes=10
    )
    assert row["user_prompt"] != stack["user_prompt"]
    assert "NOTES_MARKER" in row["user_prompt"]


def test_actual_typography_changes_deck_review_input_without_changing_text() -> None:
    """같은 배치라도 강조 크기가 다르면 검토자가 차이를 볼 수 있어야 한다."""
    service = DesignReviewService()
    first = _spec()
    second = replace(
        first,
        shapes=[
            replace(first.shapes[0], text_size_pt=40, text_bold=True),
            *first.shapes[1:],
        ],
    )
    outline = OutlineResponse([SlideOutline("비교", "동일 내용")])
    a = service.prepare_deck(outline, DesignSpec([first]), presentation_minutes=10)
    b = service.prepare_deck(outline, DesignSpec([second]), presentation_minutes=10)
    assert a["user_prompt"] != b["user_prompt"]


def test_deck_review_keeps_design_intent_and_presentation_context() -> None:
    task = DesignReviewService().prepare_deck(
        OutlineResponse([SlideOutline("전환", "가정", layout_plan="PLAN_MARKER")]),
        DesignSpec([_spec()]),
        presentation_minutes=10,
        design_intent="INTENT_MARKER: 본문은 여백을 둔 전환점",
        presentation_context={
            "purpose": "PURPOSE_MARKER",
            "audience_type": "technical",
        },
    )
    for marker in ("INTENT_MARKER", "PURPOSE_MARKER", "PLAN_MARKER", "NOTES_MARKER"):
        assert marker in task["user_prompt"]


@pytest.mark.parametrize("phase", ["analysis", "fix"])
def test_visual_qa_passes_the_same_intent_to_analysis_and_fix(phase: str) -> None:
    service = VisualQAService()
    if phase == "analysis":
        task = service.prepare_analysis(
            Path("screen.png"), 0, _spec(), design_directives="INTENT_MARKER"
        )
    else:
        task = service.prepare_fix(
            Path("screen.png"), _spec(), [], design_directives="INTENT_MARKER"
        )
    assert "INTENT_MARKER" in task["user_prompt"]


@pytest.mark.parametrize("changed_input", ["intent", "purpose", "duration"])
def test_deck_review_rejects_results_after_reviewed_context_changes(
    tmp_path: Path, monkeypatch, changed_input: str
) -> None:
    monkeypatch.setattr(
        "ppt_generator.tools.project.service.PPT_GENERATOR_HOME", tmp_path
    )
    projects = ProjectService()
    project_id, directory = projects.resolve_project_dir("review-intent")
    projects.save_outline(
        directory,
        json.dumps({"slides": [{"title": "비교", "content_summary": "근거 검토"}]}),
    )
    projects.save_design_spec(directory, DesignSpec([_spec()]))
    metadata = ProjectMetadata(purpose="교육", presentation_minutes=10)
    projects.save_metadata(directory, metadata)
    projects.save_design_doc_md(directory, "## 톤 & 방향\n차분한 교육")
    deps = DesignDeps(projects, DesignService(), review_service=DesignReviewService())
    prepared = json.loads(handle_prepare_deck_review(deps, project_id=project_id))
    if changed_input == "intent":
        projects.save_design_doc_md(directory, "## 톤 & 방향\n핵심 의사결정 강조")
    else:
        projects.save_metadata(
            directory,
            replace(
                metadata,
                **(
                    {"purpose": "투자 결정"}
                    if changed_input == "purpose"
                    else {"presentation_minutes": 3}
                ),
            ),
        )
    with pytest.raises(ValueError, match="Stale"):
        handle_ingest_deck_review(
            deps,
            project_id=project_id,
            review_json='{"has_high_severity":false,"issues":[]}',
            review_context=prepared["review_context"],
        )
