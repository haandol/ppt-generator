"""사용자가 선택한 디자인 의도의 생성·매칭·저장 계약."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ppt_generator.interfaces.llm_output_models import DesignDocDraftOutput
from ppt_generator.interfaces.schemas import SlideOutline
from ppt_generator.tools.design.design_doc_md import (
    PageRequest,
    match_page_request,
    parse_design_doc_md,
    render_design_doc_md,
    remap_page_request_numbers,
)
from ppt_generator.tools.design.handlers.deps import DesignDeps
from ppt_generator.tools.design.handlers.generation import (
    handle_ingest_design_doc_draft,
)
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService


def _draft() -> dict:
    return {
        "theme": {
            "background_color": "#FFFFFF",
            "text_colors": ["#17261F"],
            "title_font_pt": 32,
            "body_font_pt": 20,
            "card_fills": [],
            "card_borders": [],
            "header_region": {"top_px": 64, "height_px": 64},
            "content_region": {"top_px": 148, "height_px": 508},
            "footer_region": {"top_px": 664, "height_px": 24},
        },
        "tone": "측정 결과를 설명하고 다음 실험을 제안한다.",
        "anti_slop": {
            "subject_specificity": "실측 지연 분포를 사용한다.",
            "visual_hierarchy": "분포를 강조하고 측정 조건은 보조한다.",
            "layout_rhythm": "분포 비교 뒤 한 문장으로 실험을 제안한다.",
            "decoration_policy": "측정 구간 표시 외 장식은 생략한다.",
            "content_grounding": "표본의 수치만 사용하고 추정은 표시한다.",
        },
        "page_requests": [
            {"number": 1, "title": "실험 제안", "request": "한 문장 강조"}
        ],
    }


@pytest.mark.parametrize(
    "field",
    [
        "subject_specificity",
        "visual_hierarchy",
        "layout_rhythm",
        "decoration_policy",
        "content_grounding",
    ],
)
def test_generated_guardrails_reject_whitespace(field: str) -> None:
    draft = _draft()
    draft["anti_slop"][field] = " \n\t "
    with pytest.raises(ValueError):
        DesignService().ingest_design_doc_draft(json.dumps(draft))


@pytest.mark.parametrize("policy", ["gradient", "none"])
def test_draft_background_choice_round_trips_to_design_md(policy: str) -> None:
    draft = _draft()
    draft["theme"]["background_image"] = policy
    service = DesignService()
    theme, tone, anti_slop, requests = service.ingest_design_doc_draft(
        json.dumps(draft)
    )
    doc = parse_design_doc_md(
        render_design_doc_md(
            theme, tone=tone, anti_slop=anti_slop, page_requests=requests
        )
    )
    assert doc.design_summary["background_image"] == policy


def test_legacy_draft_keeps_gradient_default() -> None:
    draft = DesignDocDraftOutput.model_validate(_draft())
    assert draft.theme.model_dump()["background_image"] == "gradient"


def test_conflicting_number_does_not_apply_to_other_title(caplog) -> None:
    request = PageRequest(3, "実験 提案", "このページだけ")
    assert match_page_request([request], 3, "別の話題") is None
    assert caplog.records


def test_moved_request_uses_unique_normalized_title() -> None:
    request = PageRequest(3, "実験 提案", "このページだけ")
    assert match_page_request([request], 4, "実験、提案！") is request


def test_number_only_handwritten_request_still_matches() -> None:
    request = PageRequest(3, "", "この番号だけ")
    assert match_page_request([request], 3, "別の話題") is request


def test_ambiguous_requests_are_reported_and_not_applied(caplog) -> None:
    requests = [PageRequest(3, "실험 제안", "A"), PageRequest(3, "실험 제안", "B")]
    assert match_page_request(requests, 3, "실험 제안") is None
    assert caplog.records


def test_title_fallback_does_not_guess_among_duplicate_deck_titles(caplog) -> None:
    request = PageRequest(3, "실험", "A")
    assert (
        match_page_request(
            [request], 4, "실험", slide_titles=["표지", "실험", "목차", "실험"]
        )
        is None
    )
    assert caplog.records


def test_exact_number_and_title_take_precedence_over_title_fallback() -> None:
    first = PageRequest(2, "실험", "첫 번째")
    exact = PageRequest(4, "실험", "두 번째")
    assert match_page_request([first, exact], 4, "실험") is exact


def test_missing_manual_request_is_reported_even_outside_current_slide_numbers(
    caplog,
) -> None:
    from ppt_generator.tools.design.design_doc_md import DesignDocMd

    doc = DesignDocMd(page_requests=[PageRequest(99, "사라진 슬라이드", "특별 요청")])
    doc.warn_unbound_requests(["표지", "실험"])
    assert "unbound" in caplog.text


def test_page_number_remap_preserves_prose_and_code_fences() -> None:
    text = (
        "## 톤 & 방향\n### 3. This is not a page request\n"
        "## Per-slide Requests\n### 03. Body\nKeep this paragraph.\n"
        "```markdown\n### 3. Code example\n```\n"
        "## Other\n### 3. Leave this alone\n"
    )
    changed = remap_page_request_numbers(text, {3: 4})
    assert changed == text.replace("### 03. Body", "### 04. Body")


@pytest.mark.parametrize("field", ["title", "request"])
def test_page_request_rejects_blank_fields_without_stripping_valid_titles(
    field: str,
) -> None:
    payload = _draft()
    payload["page_requests"][0][field] = " \t\n "
    with pytest.raises(ValueError, match="blank"):
        DesignService().ingest_design_doc_draft(json.dumps(payload))


@pytest.mark.parametrize(
    "requests",
    [
        [{"number": 2, "title": "실험 제안", "request": "번호 초과"}],
        [{"number": 1, "title": "없는 제목", "request": "제목 불일치"}],
        [
            {"number": 1, "title": "실험 제안", "request": "A"},
            {"number": 1, "title": "실험 제안", "request": "B"},
        ],
    ],
)
def test_invalid_generated_page_requests_do_not_write_design_md(
    tmp_path: Path, monkeypatch, requests: list[dict]
) -> None:
    monkeypatch.setattr(
        "ppt_generator.tools.project.service.PPT_GENERATOR_HOME", tmp_path
    )
    projects = ProjectService()
    project_id, directory = projects.resolve_project_dir("draft-test")
    projects.save_outline(
        directory,
        json.dumps({"slides": [{"title": "실험 제안", "content_summary": "한 문장"}]}),
    )
    draft = _draft()
    draft["page_requests"] = requests
    with pytest.raises(ValueError):
        handle_ingest_design_doc_draft(
            DesignDeps(projects, DesignService()),
            project_id=project_id,
            draft_json=json.dumps(draft),
            color_theme="light",
        )
    assert not (directory / "DESIGN.md").exists()


def test_draft_system_prompt_only_requests_deck_intent() -> None:
    from ppt_generator.interfaces.schemas import OutlineResponse

    task = DesignService().prepare_design_doc_draft(
        OutlineResponse([SlideOutline("실험 제안", "한 문장")])
    )
    assert "PptxSlideSpec" not in task["system_prompt"]
    assert "grid_layout" not in task["system_prompt"]
