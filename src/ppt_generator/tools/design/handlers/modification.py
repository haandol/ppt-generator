"""modify_design_spec / move_slide 핸들러."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING, NoReturn

from ppt_generator.interfaces.constants import BEDROCK_DESIGN_MODEL_ID
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.interfaces.utils import (
    complexity_to_budget_tokens,
    estimate_cost,
    estimate_slide_complexity,
    format_token_usage,
    parse_outline_json,
)

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


def _raise_validation(tool: str, msg: str, **context) -> NoReturn:
    """입력 검증 실패를 로깅하고 ValueError 를 raise.

    `tool` — MCP 도구 이름 (디버깅용 prefix), `context` — 식별자 dict (project_id,
    slide_index, component_id 등). 모든 검증 실패가 동일 형식으로 로그에 남도록
    한다 (production 추적용).
    """
    ctx_str = " ".join(f"{k}={v!r}" for k, v in context.items() if v is not None)
    logger.error("%s validation failed: %s | %s", tool, msg, ctx_str)
    raise ValueError(msg)


def handle_move(
    deps: DesignDeps,
    *,
    project_id: str,
    from_index: int,
    to_index: int,
) -> str:
    """슬라이드를 from_index → to_index로 이동한다."""
    project_service = deps.project_service
    _, project_dir = project_service.resolve_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)

    if from_index < 1 or from_index > slide_count:
        _raise_validation(
            "move_slide",
            f"Invalid from_index: {from_index} (valid range: 1-{slide_count})",
            project_id=project_id,
            from_index=from_index,
            slide_count=slide_count,
        )
    if to_index < 1 or to_index > slide_count:
        _raise_validation(
            "move_slide",
            f"Invalid to_index: {to_index} (valid range: 1-{slide_count})",
            project_id=project_id,
            to_index=to_index,
            slide_count=slide_count,
        )
    if from_index == to_index:
        return json.dumps(
            {
                "project_id": project_id,
                "slide_count": slide_count,
                "from_index": from_index,
                "to_index": to_index,
                "message": "No move needed (same position)",
            },
            ensure_ascii=False,
        )

    from_idx = from_index - 1
    to_idx = to_index - 1

    project_service.sync_outline_to_design_spec_count(project_dir)
    project_service.move_outline_slide(project_dir, from_idx, to_idx)
    project_service.move_slide_images(project_dir, from_idx, to_idx, slide_count)
    project_service.move_design_spec_slide(project_dir, from_idx, to_idx)
    project_service.move_slide_html(project_dir, from_idx, to_idx)
    project_service.renumber_design_spec_image_srcs(project_dir)
    project_service.update_step(project_dir, "design_spec_modified")

    return json.dumps(
        {
            "project_id": project_id,
            "slide_count": slide_count,
            "from_index": from_index,
            "to_index": to_index,
        },
        ensure_ascii=False,
    )


def handle_modify(
    deps: DesignDeps,
    *,
    project_id: str,
    action: str,
    slide_index: int,
    title: str,
    content_summary: str,
    component_hint: str,
    slide_type: str,
    speaker_notes: str,
    color_theme: str,
) -> str:
    """슬라이드 add/update/delete를 수행한다."""
    if action not in ("add", "update", "delete"):
        _raise_validation(
            "modify_design_spec",
            f"action must be one of 'add', 'update', 'delete': {action}",
            project_id=project_id,
            action=action,
            slide_index=slide_index,
        )

    project_service = deps.project_service
    _, project_dir = project_service.resolve_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)

    design_summary: dict | None = None
    if action in ("add", "update"):
        design_summary = project_service.load_design_summary(project_dir)
        if design_summary and design_summary.get("color_theme"):
            color_theme = design_summary["color_theme"]

    slide_html_path: str | None = None
    token_usage: dict[str, int] = {}

    if action == "add":
        slide_html_path, token_usage = _add_slide(
            deps,
            project_dir=project_dir,
            slide_count=slide_count,
            slide_index=slide_index,
            title=title,
            content_summary=content_summary,
            component_hint=component_hint,
            slide_type=slide_type,
            speaker_notes=speaker_notes,
            color_theme=color_theme,
            design_summary=design_summary,
        )
    elif action == "update":
        slide_html_path, token_usage = _update_slide(
            deps,
            project_dir=project_dir,
            slide_count=slide_count,
            slide_index=slide_index,
            title=title,
            content_summary=content_summary,
            component_hint=component_hint,
            slide_type=slide_type,
            speaker_notes=speaker_notes,
            color_theme=color_theme,
            design_summary=design_summary,
        )
    elif action == "delete":
        _delete_slide(
            deps,
            project_dir=project_dir,
            slide_count=slide_count,
            slide_index=slide_index,
        )

    project_service.update_step(project_dir, "design_spec_modified")
    project_service.sync_num_slides(project_dir)
    new_count = project_service.get_design_spec_slide_count(project_dir)

    result: dict = {
        "design_spec_dir": str(project_dir / "design_spec"),
        "project_id": project_id,
        "slide_count": new_count,
    }
    if slide_html_path:
        result["slide_html_path"] = slide_html_path
    if token_usage:
        result["token_usage"] = format_token_usage(token_usage)
        result["estimated_cost"] = estimate_cost(token_usage, BEDROCK_DESIGN_MODEL_ID)

    if action in ("add", "update"):
        target_idx = (
            (slide_index - 1) if 1 <= slide_index <= new_count else new_count - 1
        )
        spec = project_service.load_design_spec_slide(project_dir, target_idx)
        # 결정 13b — 단계적 lint: 거시 위반 발견 시 다음 layer 스킵.
        slide_lint = lint_slide_spec(
            spec, slide_index=target_idx + 1, stop_on_layer_error=True
        )
        if slide_lint.has_violations:
            result["lint"] = slide_lint.to_dict()
            result["lint_suggestion"] = (
                f"슬라이드 {target_idx + 1}에서 "
                f"{len(slide_lint.violations)}건의 lint 위반이 발견되었습니다. "
                "위반 내용을 확인하고 수정 여부를 결정하세요."
            )

    return json.dumps(result, ensure_ascii=False)


# --- shared helpers ---


def _generate_and_review(
    deps,
    *,
    slide_outline,
    slide_index,
    design_summary,
    color_theme,
    prev_outline=None,
    next_outline=None,
):
    """슬라이드를 생성하고 리뷰 후 필요시 재생성한다."""
    slide_type = slide_outline.slide_type or "content"
    complexity = estimate_slide_complexity(slide_outline)
    budget_tokens = complexity_to_budget_tokens(complexity)
    svc = deps.design_service_factory(slide_type, budget_tokens=budget_tokens)
    spec = svc.generate_single_slide(
        slide_outline,
        design_summary,
        color_theme=color_theme,
        prev_outline=prev_outline,
        next_outline=next_outline,
    )
    token_usage = svc.last_token_usage

    if deps.review_service_factory is not None:
        try:
            from ppt_generator.interfaces.spec_utils import lint_slide_spec
            from ppt_generator.tools.design.review_service import apply_review_and_fix

            # 결정 13b — review LLM 에 layer 별 단계적 lint 결과 전달.
            lint_result = lint_slide_spec(spec, stop_on_layer_error=True)

            def _regenerate(feedback: str) -> tuple:
                svc_regen = deps.design_service_factory(
                    slide_type, budget_tokens=budget_tokens
                )
                new = svc_regen.generate_single_slide(
                    slide_outline,
                    design_summary,
                    color_theme=color_theme,
                    review_feedback=feedback,
                    prev_outline=prev_outline,
                    next_outline=next_outline,
                )
                return new, svc_regen.last_token_usage

            rr = apply_review_and_fix(
                spec=spec,
                slide_index=slide_index,
                gen_usage=token_usage,
                review_service_factory=deps.review_service_factory,
                regenerate=_regenerate,
                lint_result=lint_result,
            )
            return rr.spec, rr.token_usage
        except Exception as exc:
            logger.warning(
                "slide[%d] review failed (proceeding with un-reviewed spec): %s",
                slide_index,
                exc,
                exc_info=True,
            )

    return spec, token_usage


# --- action handlers ---


def _add_slide(
    deps,
    *,
    project_dir,
    slide_count,
    slide_index,
    title,
    content_summary,
    component_hint,
    slide_type,
    speaker_notes,
    color_theme,
    design_summary,
):
    """슬라이드 추가."""
    if not title or not content_summary:
        _raise_validation(
            "modify_design_spec.add",
            "title and content_summary are required for add action",
            slide_index=slide_index,
            title=title,
            content_summary_len=len(content_summary or ""),
        )

    project_service = deps.project_service
    insert_idx = (
        (slide_index - 1) if 1 <= slide_index <= slide_count + 1 else slide_count
    )

    project_service.sync_outline_to_design_spec_count(project_dir)
    outline_json = json.dumps(
        {
            "title": title,
            "content_summary": content_summary,
            "component_hint": component_hint,
            "slide_type": slide_type,
            "speaker_notes": speaker_notes,
        },
        ensure_ascii=False,
    )
    project_service.insert_outline_slide(project_dir, insert_idx, outline_json)
    project_service.shift_slide_images(project_dir, insert_idx, slide_count)
    project_service.shift_slide_htmls(project_dir, insert_idx)

    outline = parse_outline_json(outline_json)
    slide_outline = outline.slides[0]

    # Load adjacent outlines for context (after insert, so indices are shifted)
    prev_outline = None
    next_outline = None
    new_count = slide_count + 1
    if insert_idx > 0:
        try:
            raw = project_service.load_outline_slide(project_dir, insert_idx - 1)
            prev_outline = parse_outline_json(raw).slides[0]
        except Exception:
            logger.warning(
                "modify_design_spec.add: prev adjacent slide load failed "
                "(prev_idx=%d, insert_idx=%d) — continuing without context",
                insert_idx - 1,
                insert_idx,
                exc_info=True,
            )
    if insert_idx + 1 < new_count:
        try:
            raw = project_service.load_outline_slide(project_dir, insert_idx + 1)
            next_outline = parse_outline_json(raw).slides[0]
        except Exception:
            logger.warning(
                "modify_design_spec.add: next adjacent slide load failed "
                "(next_idx=%d, insert_idx=%d) — continuing without context",
                insert_idx + 1,
                insert_idx,
                exc_info=True,
            )

    new_spec, token_usage = _generate_and_review(
        deps,
        slide_outline=slide_outline,
        slide_index=slide_index,
        design_summary=design_summary,
        color_theme=color_theme,
        prev_outline=prev_outline,
        next_outline=next_outline,
    )

    project_service.insert_design_spec_slide(project_dir, insert_idx, new_spec)
    project_service.renumber_design_spec_image_srcs(project_dir)

    slide_html_path: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(
            insert_idx, new_spec, color_theme=color_theme
        )
        html_path = project_service.save_single_slide_html(
            project_dir, insert_idx, html
        )
        slide_html_path = str(html_path)

    return slide_html_path, token_usage


def _update_slide(
    deps,
    *,
    project_dir,
    slide_count,
    slide_index,
    title,
    content_summary,
    component_hint,
    slide_type,
    speaker_notes,
    color_theme,
    design_summary,
):
    """슬라이드 수정."""
    if slide_index < 1 or slide_index > slide_count:
        _raise_validation(
            "modify_design_spec.update",
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})",
            slide_index=slide_index,
            slide_count=slide_count,
        )

    project_service = deps.project_service
    idx = slide_index - 1

    metadata = project_service.load_metadata(project_dir)
    if metadata.source == "imported" and (not title or not content_summary):
        _raise_validation(
            "modify_design_spec.update",
            "title and content_summary are required for update action "
            "on imported projects (no outline available)",
            slide_index=slide_index,
            source=metadata.source,
        )

    project_service.sync_outline_to_design_spec_count(project_dir)

    if title and content_summary:
        outline_json = json.dumps(
            {
                "title": title,
                "content_summary": content_summary,
                "component_hint": component_hint,
                "slide_type": slide_type,
                "speaker_notes": speaker_notes,
            },
            ensure_ascii=False,
        )
        project_service.save_outline_slide(project_dir, idx, outline_json)

    existing_spec = project_service.load_design_spec_slide(project_dir, idx)
    outline_raw = project_service.load_outline_slide(project_dir, idx)
    outline = parse_outline_json(outline_raw)
    slide_outline = outline.slides[0]
    new_spec, token_usage = _generate_and_review(
        deps,
        slide_outline=slide_outline,
        slide_index=slide_index,
        design_summary=design_summary,
        color_theme=color_theme,
    )

    if existing_spec.images:
        new_spec = replace(new_spec, images=existing_spec.images)

    project_service.save_design_spec_slide(project_dir, idx, new_spec)
    project_service.renumber_design_spec_image_srcs(project_dir)

    slide_html_path: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(
            idx, new_spec, color_theme=color_theme
        )
        html_path = project_service.save_single_slide_html(project_dir, idx, html)
        slide_html_path = str(html_path)

    return slide_html_path, token_usage


def handle_modify_component(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    component_id: str,
    instruction: str,
    color_theme: str,
) -> str:
    """단일 component 부분 수정.

    슬라이드 전체 spec 을 LLM 에 컨텍스트로 주고 대상 component_id 의 element 만
    수정한다. 트리 구조 변경, 다른 element/grid_plan/배경/speaker_notes 변경은
    하지 않는다.
    """
    if not project_id:
        _raise_validation("modify_component", "project_id is required")
    if slide_index < 1:
        _raise_validation(
            "modify_component",
            f"slide_index must be >= 1: {slide_index}",
            project_id=project_id,
            slide_index=slide_index,
        )
    if not component_id:
        _raise_validation(
            "modify_component",
            "component_id is required",
            project_id=project_id,
            slide_index=slide_index,
        )
    if not instruction or not instruction.strip():
        _raise_validation(
            "modify_component",
            "instruction is required",
            project_id=project_id,
            slide_index=slide_index,
            component_id=component_id,
        )

    project_service = deps.project_service
    _, project_dir = project_service.resolve_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)
    if slide_index > slide_count:
        _raise_validation(
            "modify_component",
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})",
            project_id=project_id,
            slide_index=slide_index,
            slide_count=slide_count,
        )

    idx = slide_index - 1
    spec = project_service.load_design_spec_slide(project_dir, idx)

    svc = deps.design_service_factory("content", budget_tokens=8192)
    backfill_token_usage: dict[str, int] = {}
    backfilled = False

    if spec.design_doc is None:
        # imported 슬라이드는 lazy backfill
        if spec.slide_type not in ("content", ""):
            _raise_validation(
                "modify_component",
                f"Slide {slide_index} has no design_doc and slide_type="
                f"{spec.slide_type!r}. modify_component supports content slides only. "
                "Use modify_design_spec(action='update') instead.",
                project_id=project_id,
                slide_index=slide_index,
                slide_type=spec.slide_type,
            )
        logger.info(
            "modify_component: starting design_doc backfill | "
            "project_id=%r slide_index=%d component_id=%r",
            project_id,
            slide_index,
            component_id,
        )
        try:
            spec = svc.backfill_design_doc(spec, slide_index=slide_index)
        except Exception as exc:
            logger.error(
                "modify_component backfill failed | "
                "project_id=%r slide_index=%d component_id=%r error=%s",
                project_id,
                slide_index,
                component_id,
                exc,
                exc_info=True,
            )
            raise ValueError(
                f"design_doc backfill failed for slide {slide_index}: {exc}. "
                "Use modify_design_spec(action='update') for this slide instead."
            ) from exc
        backfilled = True
        backfill_token_usage = dict(svc.last_token_usage)
        # backfill 결과 영구 저장 — 다음 호출은 backfill 우회
        project_service.save_design_spec_slide(project_dir, idx, spec)

        if not _has_component(spec, component_id):
            available = _list_available_components(spec)
            project_service.update_step(project_dir, "design_spec_modified")
            response: dict = {
                "project_id": project_id,
                "slide_index": slide_index,
                "status": "backfilled",
                "message": (
                    "design_doc 가 backfill 되었습니다. 요청한 component_id "
                    f"{component_id!r} 를 트리에서 찾지 못했습니다. "
                    "available_components 를 확인하고 다시 호출해주세요."
                ),
                "requested_component_id": component_id,
                "available_components": available,
            }
            if backfill_token_usage:
                response["token_usage"] = format_token_usage(backfill_token_usage)
                response["estimated_cost"] = estimate_cost(
                    backfill_token_usage, BEDROCK_DESIGN_MODEL_ID
                )
            return json.dumps(response, ensure_ascii=False)

    new_spec = svc.modify_component(
        spec=spec,
        component_id=component_id,
        instruction=instruction,
        slide_index=slide_index,
        color_theme=color_theme,
    )
    token_usage = svc.last_token_usage

    if spec.images:
        new_spec = replace(new_spec, images=spec.images)

    project_service.save_design_spec_slide(project_dir, idx, new_spec)
    project_service.renumber_design_spec_image_srcs(project_dir)
    project_service.update_step(project_dir, "design_spec_modified")

    kind, elem_idx, _ = _find_modified_element(new_spec, component_id)

    slide_html_path: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(
            idx, new_spec, color_theme=color_theme
        )
        html_path = project_service.save_single_slide_html(project_dir, idx, html)
        slide_html_path = str(html_path)

    result: dict = {
        "project_id": project_id,
        "slide_index": slide_index,
        "component_id": component_id,
        "modified_element": {"type": kind, "index": elem_idx},
    }
    if slide_html_path:
        result["slide_html_path"] = slide_html_path

    # 결정 13b — modify_component 후에도 단계적 검증.
    slide_lint = lint_slide_spec(
        new_spec, slide_index=slide_index, stop_on_layer_error=True
    )
    if slide_lint.has_violations:
        result["lint"] = slide_lint.to_dict()
        result["lint_suggestion"] = (
            f"슬라이드 {slide_index}에서 "
            f"{len(slide_lint.violations)}건의 lint 위반이 발견되었습니다. "
            "추가 수정이 필요한지 확인하세요."
        )

    combined_usage = _merge_token_usage(backfill_token_usage, token_usage)
    if combined_usage:
        result["token_usage"] = format_token_usage(combined_usage)
        result["estimated_cost"] = estimate_cost(
            combined_usage, BEDROCK_DESIGN_MODEL_ID
        )
    if backfilled:
        result["backfilled"] = True

    return json.dumps(result, ensure_ascii=False)


def _has_component(spec, component_id: str) -> bool:
    for tb in spec.textboxes:
        if tb.component_id == component_id:
            return True
    for s in spec.shapes:
        if s.component_id == component_id:
            return True
    return False


def _list_available_components(spec) -> list[dict]:
    """backfilled spec 의 component leaf 목록을 사용자 응답용으로 평탄화한다."""
    items: list[dict] = []

    def _walk(node, path):
        new_path = path + [node.id] if path else [node.id]
        if not node.children:
            items.append(
                {
                    "id": node.id,
                    "role": node.role,
                    "description": node.description,
                    "path": ".".join(new_path),
                }
            )
            return
        for child in node.children:
            _walk(child, new_path)

    if spec.design_doc is not None:
        for root in spec.design_doc.layout:
            _walk(root, [])
    return items


def _merge_token_usage(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = dict(a)
    for k, v in (b or {}).items():
        out[k] = out.get(k, 0) + v
    return out


def _find_modified_element(spec, component_id: str) -> tuple[str, int, object]:
    """수정된 element 위치를 응답용으로 찾는다."""
    for i, tb in enumerate(spec.textboxes):
        if tb.component_id == component_id:
            return ("textbox", i, tb)
    for i, s in enumerate(spec.shapes):
        if s.component_id == component_id:
            return ("shape", i, s)
    raise ValueError(f"component_id missing after modification: {component_id}")


def _delete_slide(deps, *, project_dir, slide_count, slide_index):
    """슬라이드 삭제."""
    if slide_index < 1 or slide_index > slide_count:
        _raise_validation(
            "modify_design_spec.delete",
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})",
            slide_index=slide_index,
            slide_count=slide_count,
        )

    project_service = deps.project_service
    idx = slide_index - 1

    project_service.sync_outline_to_design_spec_count(project_dir)
    project_service.delete_slide_images(project_dir, idx, slide_count)
    project_service.delete_design_spec_slide(project_dir, idx)
    project_service.delete_slide_html(project_dir, idx)
    project_service.delete_outline_slide(project_dir, idx)
    project_service.renumber_design_spec_image_srcs(project_dir)
