"""디자인 스펙 생성 핸들러 (prepare/ingest).

LLM 생성은 클라이언트가 수행한다. 서버는 프롬프트 조립(prepare)과 출력 검증·정합화·
저장·렌더·lint(ingest/finalize)를 담당한다. 슬라이드 단위로 stateless 하므로
클라이언트가 여러 슬라이드를 병렬로 prepare→생성→ingest 할 수 있다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from ppt_generator.interfaces.spec_utils import lint_design_spec, lint_slide_spec
from ppt_generator.interfaces.utils import (
    complexity_to_budget_tokens,
    estimate_slide_complexity,
    parse_outline_json,
)
from ppt_generator.tools.slides.service import SlidesService

if TYPE_CHECKING:
    from ppt_generator.interfaces.schemas import OutlineResponse
    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DESIGN.md 초안 (theme + tone + page_requests)
# ---------------------------------------------------------------------------


def handle_prepare_design_doc_draft(
    deps: DesignDeps,
    *,
    project_id: str,
    outline_json: str,
    color_theme: str,
) -> str:
    """DESIGN.md 초안 생성 태스크를 조립한다. 이미 DESIGN.md 가 있으면 skip."""
    project_service = deps.project_service
    project_id, project_dir = project_service.resolve_project_dir(project_id)

    # 배경 이미지 선택을 프로젝트 단위로 고정 (미리보기/내보내기 일관성).
    from ppt_generator.interfaces import bg_image_utils

    bg_image_utils.set_project_seed(project_id)

    if project_service.design_doc_md_exists(project_dir):
        return json.dumps(
            {"skip": True, "project_id": project_id, "reason": "DESIGN.md exists"},
            ensure_ascii=False,
        )

    outline = _load_outline(deps, project_id=project_id, outline_json=outline_json)
    task = deps.design_service.prepare_design_doc_draft(outline, color_theme)
    task["project_id"] = project_id
    task["color_theme"] = color_theme
    return json.dumps(task, ensure_ascii=False)


def handle_ingest_design_doc_draft(
    deps: DesignDeps,
    *,
    project_id: str,
    draft_json: str,
    color_theme: str,
) -> str:
    """클라이언트가 생성한 DESIGN.md 초안을 파싱해 DESIGN.md 로 저장한다."""
    from ppt_generator.tools.design.design_doc_md import render_design_doc_md

    project_service = deps.project_service
    _, project_dir = project_service.resolve_project_dir(project_id)

    summary, tone, page_requests = deps.design_service.ingest_design_doc_draft(
        draft_json
    )
    summary["color_theme"] = color_theme
    project_service.save_design_doc_md(
        project_dir,
        render_design_doc_md(summary, tone=tone, page_requests=page_requests),
    )
    logger.info("DESIGN.md draft ingested and saved")
    return json.dumps(
        {
            "project_id": project_id,
            "design_doc_path": str(project_dir / "DESIGN.md"),
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# 단일 슬라이드 design spec
# ---------------------------------------------------------------------------


def handle_prepare_design_slide(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    outline_json: str,
    total_slides: int,
    color_theme: str,
) -> str:
    """단일 슬라이드 design spec 생성 태스크를 조립한다.

    slide_index 는 1-based. outline 은 project 에 저장된 것 또는 전달된 것을 쓴다.
    """
    project_service = deps.project_service
    project_id, project_dir = project_service.resolve_project_dir(project_id)

    outline = _load_outline(deps, project_id=project_id, outline_json=outline_json)
    if total_slides <= 0:
        total_slides = len(outline.slides)

    if slide_index < 1 or slide_index > len(outline.slides):
        raise ValueError(
            f"Invalid slide_index: {slide_index} (valid range: 1-{len(outline.slides)})"
        )
    idx = slide_index - 1
    slide_outline = outline.slides[idx]

    design_summary = project_service.load_design_summary(project_dir)
    directives = _directives_for(
        project_service, project_dir, slide_index, slide_outline.title
    )
    prev_outline = outline.slides[idx - 1] if idx > 0 else None
    next_outline = outline.slides[idx + 1] if idx + 1 < len(outline.slides) else None
    budget_tokens = complexity_to_budget_tokens(
        estimate_slide_complexity(slide_outline)
    )

    task = deps.design_service.prepare_slide(
        slide_outline,
        design_summary=design_summary,
        slide_index=slide_index,
        total_slides=total_slides,
        color_theme=color_theme,
        prev_outline=prev_outline,
        next_outline=next_outline,
        design_directives=directives,
        budget_tokens=budget_tokens,
    )
    task["project_id"] = project_id
    task["slide_index"] = slide_index
    return json.dumps(task, ensure_ascii=False)


def handle_ingest_design_slide(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    spec_json: str,
    color_theme: str,
) -> str:
    """클라이언트가 생성한 슬라이드 spec 을 검증·정합화·저장·렌더·lint 한다.

    기존 병렬 생성 러너의 슬라이드별 후처리와 동일 (배경색 보정 포함).
    """
    project_service = deps.project_service
    project_id, project_dir = project_service.resolve_project_dir(project_id)

    from ppt_generator.interfaces import bg_image_utils

    bg_image_utils.set_project_seed(project_id)

    idx = slide_index - 1
    outline = _load_outline(deps, project_id=project_id, outline_json="")
    # 동작 불변: 저장되는 slide_type 은 outline 의 원본 값 그대로 (None/"" 포함).
    # 응답 모델 선택만 ingest_slide 내부에서 `or "content"` 로 정규화한다.
    raw_slide_type = (
        outline.slides[idx].slide_type if 0 <= idx < len(outline.slides) else "content"
    )

    spec, overflow = deps.design_service.ingest_slide(
        spec_json, slide_type=raw_slide_type
    )

    design_summary = project_service.load_design_summary(project_dir)
    bg_image_policy = project_service.load_bg_image_policy(project_dir)
    spec = _enforce_background_color(spec, design_summary, bg_image_policy, idx)

    project_service.create_design_spec_slide(project_dir, idx, spec)

    slide_html_path: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(
            idx, spec, color_theme=color_theme, bg_image_policy=bg_image_policy
        )
        hp = project_service.save_single_slide_html(project_dir, idx, html)
        slide_html_path = str(hp)

    project_service.renumber_design_spec_image_srcs(project_dir)

    result: dict = {
        "project_id": project_id,
        "slide_index": slide_index,
        "status": "success",
        "slide_file": f"slide_{slide_index:02d}.json",
    }
    if slide_html_path:
        result["slide_html_path"] = slide_html_path
    if overflow:
        result["overflow"] = overflow

    # 결정 13b — 단계적 lint.
    slide_lint = lint_slide_spec(
        spec, slide_index=slide_index, stop_on_layer_error=True
    )
    if slide_lint.has_violations:
        result["lint"] = slide_lint.to_dict()

    return json.dumps(result, ensure_ascii=False)


def handle_finalize_design_spec(
    deps: DesignDeps,
    *,
    project_id: str,
    overflow_json: str,
) -> str:
    """모든 슬라이드 ingest 후 호출 — 컨테이너 HTML + 덱 전체 lint + overflow 저장.

    LLM 없음. 클라이언트가 각 ingest 에서 모은 overflow 를 overflow_json 으로 넘긴다.
    """
    project_service = deps.project_service
    _, project_dir = project_service.resolve_project_dir(project_id)

    project_service.renumber_design_spec_image_srcs(project_dir)
    project_service.update_step(project_dir, "design_spec")
    slide_count = project_service.get_design_spec_slide_count(project_dir)

    slides_html_path: str | None = None
    if deps.slides_service is not None and slide_count > 0:
        container_html = SlidesService._build_container_html(slide_count)
        path = project_dir / "slides.html"
        path.write_text(container_html, encoding="utf-8")
        slides_html_path = str(path)
        logger.info("slides.html container generated: %s", path)

    # overflow 저장 (클라이언트가 집계해 전달)
    all_overflow: list[dict] = []
    if overflow_json:
        try:
            parsed = json.loads(overflow_json)
            if isinstance(parsed, list):
                all_overflow = parsed
        except json.JSONDecodeError:
            logger.warning("finalize: overflow_json parse 실패, 무시")
    if all_overflow:
        overflow_path = project_dir / "overflow.json"
        overflow_path.write_text(
            json.dumps(all_overflow, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # 덱 전체 lint (결정 13b/13e)
    lint_result_dict: dict | None = None
    cross_layer_errors: list[dict] = []
    if slide_count > 0:
        design_spec = project_service.load_design_spec(project_dir)
        lint_result = lint_design_spec(design_spec.slides, stop_on_layer_error=True)
        if lint_result.has_violations:
            lint_result_dict = lint_result.to_dict()
        for slide_result in lint_result.slides:
            for v in slide_result.violations:
                if v.severity == "error" and v.layer == "cross":
                    cross_layer_errors.append(
                        {
                            "slide_index": slide_result.slide_index,
                            "rule": v.rule,
                            "message": v.message,
                        }
                    )

    resp: dict = {
        "design_spec_dir": str(project_dir / "design_spec"),
        "design_doc_path": str(project_dir / "DESIGN.md"),
        "slide_count": slide_count,
        "project_id": project_id,
        "visual_qa_suggestion": (
            "Visual QA를 실행하면 시각적 결함(줄바꿈, 겹침, 잘림 등)을 자동 감지하고 수정합니다. "
            f"실행하려면 capture_slides(project_id='{project_id}') 를 호출하세요."
        ),
        "design_doc_suggestion": (
            "디자인 의도(전역 톤, 페이지별 특별 요청)는 DESIGN.md 에서 관리합니다. "
            "DESIGN.md 를 편집한 뒤 다시 생성하면 변경된 의도가 반영됩니다."
        ),
    }
    if lint_result_dict:
        resp["lint"] = lint_result_dict
        resp["lint_suggestion"] = (
            f"디자인 lint에서 {lint_result_dict['total_violations']}건의 위반이 발견되었습니다. "
            "위반 내용을 확인하고, 수정이 필요하면 해당 슬라이드를 "
            "prepare_slide_edit(action='update')/ingest_slide_edit 로 수정하세요."
        )
    if cross_layer_errors:
        resp["cross_layer_errors"] = cross_layer_errors
    if all_overflow:
        resp["overflow"] = all_overflow
    if slides_html_path:
        resp["slides_html_path"] = slides_html_path

    return json.dumps(resp, ensure_ascii=False)


# --- helpers ---


def _enforce_background_color(spec, design_summary, bg_image_policy, idx):
    """content 슬라이드(및 bg 정책 none)의 배경색을 deck 배경색으로 보정한다.

    parallel_runner 의 배경 보정과 동일 (design/0016).
    """
    _enforce_bg = spec.slide_type == "content" or bg_image_policy == "none"
    if (
        design_summary
        and _enforce_bg
        and design_summary.get("background_color")
        and spec.background_color != design_summary["background_color"]
    ):
        logger.info(
            "slide[%d] 배경색 보정: %s → %s",
            idx,
            spec.background_color,
            design_summary["background_color"],
        )
        spec = replace(spec, background_color=design_summary["background_color"])
    return spec


def _directives_for(project_service, project_dir, slide_index: int, title: str) -> str:
    """DESIGN.md 에서 해당 슬라이드의 디자인 지시(톤+페이지 요청)를 만든다."""
    design_doc = project_service.load_design_doc_md(project_dir)
    if design_doc is None:
        return ""
    return design_doc.directives_for(slide_index, title)


def _load_outline(
    deps: DesignDeps, *, project_id: str, outline_json: str
) -> OutlineResponse:
    """아웃라인을 JSON 문자열 또는 프로젝트 디렉토리에서 로드한다."""
    if outline_json:
        return parse_outline_json(outline_json)
    if project_id:
        _, proj_dir = deps.project_service.resolve_project_dir(project_id)
        raw = deps.project_service.load_outline(proj_dir)
        return parse_outline_json(raw)
    logger.error(
        "design slide prepare validation failed: "
        "Either outline_json or project_id must be provided."
    )
    raise ValueError("Either outline_json or project_id must be provided.")
