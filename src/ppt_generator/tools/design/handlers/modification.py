"""modify_design_spec / move_slide 핸들러."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from ppt_generator.interfaces.constants import BEDROCK_DESIGN_MODEL_ID
from ppt_generator.interfaces.utils import (
    complexity_to_thinking_effort,
    estimate_cost,
    estimate_slide_complexity,
    format_token_usage,
    parse_outline_json,
)

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


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
        raise ValueError(f"Invalid from_index: {from_index} (valid range: 1-{slide_count})")
    if to_index < 1 or to_index > slide_count:
        raise ValueError(f"Invalid to_index: {to_index} (valid range: 1-{slide_count})")
    if from_index == to_index:
        return json.dumps({
            "project_id": project_id,
            "slide_count": slide_count,
            "from_index": from_index,
            "to_index": to_index,
            "message": "No move needed (same position)",
        }, ensure_ascii=False)

    from_idx = from_index - 1
    to_idx = to_index - 1

    project_service.sync_outline_to_design_spec_count(project_dir)
    project_service.move_outline_slide(project_dir, from_idx, to_idx)
    project_service.move_design_spec_slide(project_dir, from_idx, to_idx)
    project_service.move_slide_html(project_dir, from_idx, to_idx)
    project_service.update_step(project_dir, "design_spec_modified")

    return json.dumps({
        "project_id": project_id,
        "slide_count": slide_count,
        "from_index": from_index,
        "to_index": to_index,
    }, ensure_ascii=False)


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
        raise ValueError(f"action must be one of 'add', 'update', 'delete': {action}")

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
            deps, project_dir=project_dir, slide_count=slide_count,
            slide_index=slide_index, title=title, content_summary=content_summary,
            component_hint=component_hint, slide_type=slide_type,
            speaker_notes=speaker_notes, color_theme=color_theme,
            design_summary=design_summary,
        )
    elif action == "update":
        slide_html_path, token_usage = _update_slide(
            deps, project_dir=project_dir, slide_count=slide_count,
            slide_index=slide_index, title=title, content_summary=content_summary,
            component_hint=component_hint, slide_type=slide_type,
            speaker_notes=speaker_notes, color_theme=color_theme,
            design_summary=design_summary,
        )
    elif action == "delete":
        _delete_slide(deps, project_dir=project_dir, slide_count=slide_count, slide_index=slide_index)

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

    return json.dumps(result, ensure_ascii=False)


# --- shared helpers ---


def _generate_and_review(deps, *, slide_outline, slide_index, design_summary, color_theme):
    """슬라이드를 생성하고 리뷰 후 필요시 재생성한다."""
    complexity = estimate_slide_complexity(slide_outline)
    effort = complexity_to_thinking_effort(complexity)
    slide_type = slide_outline.slide_type or "content"
    svc = deps.design_service_factory(effort, slide_type)
    spec = svc.generate_single_slide(slide_outline, design_summary, color_theme=color_theme)
    token_usage = svc.last_token_usage

    if deps.review_service_factory is not None:
        try:
            from ppt_generator.tools.design.review_service import apply_review_and_fix

            def _regenerate(feedback: str) -> tuple:
                svc_regen = deps.design_service_factory(effort, slide_type)
                new = svc_regen.generate_single_slide(
                    slide_outline, design_summary, color_theme=color_theme,
                    review_feedback=feedback,
                )
                return new, svc_regen.last_token_usage

            rr = apply_review_and_fix(
                spec=spec, slide_index=slide_index, gen_usage=token_usage,
                review_service_factory=deps.review_service_factory,
                regenerate=_regenerate,
            )
            return rr.spec, rr.token_usage
        except Exception as exc:
            logger.warning("slide[%d] review failed: %s", slide_index, exc)

    return spec, token_usage


# --- action handlers ---


def _add_slide(deps, *, project_dir, slide_count, slide_index, title, content_summary,
               component_hint, slide_type, speaker_notes, color_theme, design_summary):
    """슬라이드 추가."""
    if not title or not content_summary:
        raise ValueError("title and content_summary are required for add action")

    project_service = deps.project_service
    insert_idx = (slide_index - 1) if 1 <= slide_index <= slide_count + 1 else slide_count

    project_service.sync_outline_to_design_spec_count(project_dir)
    outline_json = json.dumps({
        "title": title, "content_summary": content_summary,
        "component_hint": component_hint, "slide_type": slide_type,
        "speaker_notes": speaker_notes,
    }, ensure_ascii=False)
    project_service.insert_outline_slide(project_dir, insert_idx, outline_json)
    project_service.shift_slide_htmls(project_dir, insert_idx)

    outline = parse_outline_json(outline_json)
    slide_outline = outline.slides[0]
    new_spec, token_usage = _generate_and_review(
        deps, slide_outline=slide_outline, slide_index=slide_index,
        design_summary=design_summary, color_theme=color_theme,
    )

    project_service.insert_design_spec_slide(project_dir, insert_idx, new_spec)

    slide_html_path: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(insert_idx, new_spec, color_theme=color_theme)
        html_path = project_service.save_single_slide_html(project_dir, insert_idx, html)
        slide_html_path = str(html_path)

    return slide_html_path, token_usage


def _update_slide(deps, *, project_dir, slide_count, slide_index, title, content_summary,
                  component_hint, slide_type, speaker_notes, color_theme, design_summary):
    """슬라이드 수정."""
    if slide_index < 1 or slide_index > slide_count:
        raise ValueError(f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})")

    project_service = deps.project_service
    idx = slide_index - 1

    metadata = project_service.load_metadata(project_dir)
    if metadata.source == "imported" and (not title or not content_summary):
        raise ValueError(
            "title and content_summary are required for update action "
            "on imported projects (no outline available)"
        )

    project_service.sync_outline_to_design_spec_count(project_dir)

    if title and content_summary:
        outline_json = json.dumps({
            "title": title, "content_summary": content_summary,
            "component_hint": component_hint, "slide_type": slide_type,
            "speaker_notes": speaker_notes,
        }, ensure_ascii=False)
        project_service.save_outline_slide(project_dir, idx, outline_json)

    existing_spec = project_service.load_design_spec_slide(project_dir, idx)
    outline_raw = project_service.load_script_or_outline_slide(project_dir, idx)
    outline = parse_outline_json(outline_raw)
    slide_outline = outline.slides[0]
    new_spec, token_usage = _generate_and_review(
        deps, slide_outline=slide_outline, slide_index=slide_index,
        design_summary=design_summary, color_theme=color_theme,
    )

    if existing_spec.images:
        new_spec = replace(new_spec, images=existing_spec.images)

    project_service.save_design_spec_slide(project_dir, idx, new_spec)

    slide_html_path: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(idx, new_spec, color_theme=color_theme)
        html_path = project_service.save_single_slide_html(project_dir, idx, html)
        slide_html_path = str(html_path)

    return slide_html_path, token_usage


def _delete_slide(deps, *, project_dir, slide_count, slide_index):
    """슬라이드 삭제."""
    if slide_index < 1 or slide_index > slide_count:
        raise ValueError(f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})")

    project_service = deps.project_service
    idx = slide_index - 1

    project_service.sync_outline_to_design_spec_count(project_dir)
    project_service.delete_design_spec_slide(project_dir, idx)
    project_service.delete_slide_html(project_dir, idx)
    project_service.delete_outline_slide(project_dir, idx)
