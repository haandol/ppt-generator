"""슬라이드 추가·수정의 준비 문맥 검증과 멱등 저장."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, replace
from pathlib import Path
from typing import TYPE_CHECKING

from ppt_generator.interfaces.schemas import SlideOutline
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.interfaces.utils import parse_outline_json
from ppt_generator.tools.design.backgrounds import _enforce_background_color
from ppt_generator.tools.design.edit_context import (
    ProjectSnapshot,
    SlideEditContext,
    load_receipt,
    project_edit_lock,
    project_revision,
    save_receipt,
)
from ppt_generator.tools.design.handlers.edit_validation import _raise_validation

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps
    from ppt_generator.tools.project.service import ProjectService

logger = logging.getLogger(__name__)


def handle_prepare_slide_edit(
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
    """add/update 슬라이드 생성 태스크와 불변 편집 컨텍스트를 조립한다."""
    if action not in ("add", "update"):
        _raise_validation(
            "prepare_slide_edit",
            f"action must be 'add' or 'update': {action}",
            project_id=project_id,
            action=action,
            slide_index=slide_index,
        )

    if not project_id:
        _raise_validation("prepare_slide_edit", "project_id is required")
    if action == "add" and slide_index != -1 and slide_index < 1:
        _raise_validation(
            "prepare_slide_edit",
            "add slide_index must be -1 or >= 1",
            slide_index=slide_index,
        )
    if action == "update" and slide_index < 1:
        _raise_validation(
            "prepare_slide_edit",
            "update slide_index must be >= 1",
            slide_index=slide_index,
        )

    project_service = deps.project_service
    project_id, project_dir = project_service.resolve_existing_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)
    revision = project_revision(project_dir)

    from ppt_generator.interfaces import bg_image_utils

    bg_image_utils.set_project_seed(project_id)

    design_summary = project_service.load_design_summary(project_dir)
    if design_summary and design_summary.get("color_theme"):
        color_theme = design_summary["color_theme"]

    if action == "add":
        prep = _prepare_add(
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
    else:
        prep = _prepare_update(
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

    context = SlideEditContext(
        project_id=project_id,
        action=action,
        requested_slide_index=slide_index,
        target_index=prep.pop("_target_index"),
        original_slide_count=slide_count,
        outline=prep.pop("_outline"),
        color_theme=color_theme,
        revision=revision,
    )
    if project_revision(project_dir) != revision:
        raise RuntimeError("Project changed while preparing slide edit; retry prepare")

    prep["project_id"] = project_id
    prep["action"] = action
    prep["color_theme"] = color_theme
    prep["edit_context"] = context.to_token(project_dir)
    return json.dumps(prep, ensure_ascii=False)


def handle_ingest_slide_edit(
    deps: DesignDeps,
    *,
    project_id: str,
    action: str,
    slide_index: int,
    spec_json: str,
    edit_context: str,
    color_theme: str,
) -> str:
    """생성 결과를 검증한 뒤 add/update를 원자적·멱등적으로 커밋한다."""
    if action not in ("add", "update"):
        _raise_validation(
            "ingest_slide_edit",
            f"action must be 'add' or 'update': {action}",
            project_id=project_id,
            action=action,
        )

    if not project_id:
        _raise_validation("ingest_slide_edit", "project_id is required")
    if action == "add" and slide_index != -1 and slide_index < 1:
        _raise_validation(
            "ingest_slide_edit",
            "add slide_index must be -1 or >= 1",
            slide_index=slide_index,
        )
    if action == "update" and slide_index < 1:
        _raise_validation(
            "ingest_slide_edit",
            "update slide_index must be >= 1",
            slide_index=slide_index,
        )

    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    context = SlideEditContext.from_token(edit_context, project_dir)
    if (
        context.project_id != project_id
        or context.action != action
        or context.requested_slide_index != slide_index
    ):
        raise ValueError("edit_context does not match ingest request")

    with project_edit_lock(project_dir):
        return _handle_ingest_slide_edit_locked(
            deps,
            project_id=project_id,
            action=action,
            spec_json=spec_json,
            context=context,
            project_dir=project_dir,
        )


def _handle_ingest_slide_edit_locked(
    deps: DesignDeps,
    *,
    project_id: str,
    action: str,
    spec_json: str,
    context: SlideEditContext,
    project_dir: Path,
) -> str:
    """프로젝트별 락 안에서 편집 검증과 커밋을 한 단위로 수행한다."""
    project_service = deps.project_service
    previous_result = load_receipt(project_dir, context.operation_id)
    if previous_result is not None:
        return json.dumps(previous_result, ensure_ascii=False)

    if project_revision(project_dir) != context.revision:
        raise ValueError("Stale edit_context: project changed after prepare")
    slide_count = project_service.get_design_spec_slide_count(project_dir)
    if slide_count != context.original_slide_count:
        raise ValueError("Stale edit_context: slide count changed after prepare")
    idx = context.target_index
    if action == "add":
        if idx < 0 or idx > slide_count:
            raise ValueError(f"Invalid add target index: {idx + 1}")
    elif idx < 0 or idx >= slide_count:
        raise ValueError(f"Invalid update target index: {idx + 1}")

    from ppt_generator.interfaces import bg_image_utils

    bg_image_utils.set_project_seed(project_id)

    outline_raw = json.dumps(context.outline, ensure_ascii=False)
    outline = parse_outline_json(outline_raw)
    # 동작 불변: 저장 slide_type 은 outline 원본 그대로, 모델 선택만 내부 정규화.
    raw_slide_type = outline.slides[0].slide_type

    spec, _overflow = deps.design_service.ingest_slide(
        spec_json, slide_type=raw_slide_type
    )
    spec = replace(spec, speaker_notes=outline.slides[0].speaker_notes)
    if spec.background_color is None:
        spec = _enforce_background_color(
            spec,
            project_service.load_design_summary(project_dir),
            project_service.load_bg_image_policy(project_dir),
            idx,
        )

    existing_images = None
    if action == "update":
        try:
            existing_spec = project_service.load_design_spec_slide(project_dir, idx)
            if existing_spec.images:
                existing_images = existing_spec.images
        except Exception:
            logger.debug(
                "update: 기존 spec 로드 실패 (이미지 복원 스킵)", exc_info=True
            )

    if existing_images:
        spec = replace(spec, images=existing_images)

    slide_html_path: str | None = None
    html: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(
            idx,
            spec,
            color_theme=context.color_theme,
            bg_image_policy=project_service.load_bg_image_policy(project_dir),
        )

    slide_lint = lint_slide_spec(spec, slide_index=idx + 1, stop_on_layer_error=True)
    with ProjectSnapshot(project_dir) as snapshot:
        project_service.sync_outline_to_design_spec_count(project_dir)
        if action == "add":
            project_service.insert_outline_slide(project_dir, idx, outline_raw)
            project_service.shift_slide_images(project_dir, idx, slide_count)
            project_service.shift_slide_htmls(project_dir, idx)
            project_service.insert_design_spec_slide(project_dir, idx, spec)
        else:
            project_service.save_outline_slide(project_dir, idx, outline_raw)
            project_service.save_design_spec_slide(project_dir, idx, spec)

        project_service.renumber_design_spec_image_srcs(project_dir)
        project_service.update_step(project_dir, "design_spec_modified")
        project_service.sync_num_slides(project_dir)
        if html is not None:
            html_path = project_service.save_single_slide_html(project_dir, idx, html)
            slide_html_path = str(html_path)

        result: dict = {
            "design_spec_dir": str(project_dir / "design_spec"),
            "project_id": project_id,
            "slide_count": project_service.get_design_spec_slide_count(project_dir),
            "slide_index": idx + 1,
        }
        if slide_html_path:
            result["slide_html_path"] = slide_html_path
        if slide_lint.has_violations:
            result["lint"] = slide_lint.to_dict()
            result["lint_suggestion"] = (
                f"슬라이드 {idx + 1}에서 "
                f"{len(slide_lint.violations)}건의 lint 위반이 발견되었습니다. "
                "위반 내용을 확인하고 수정 여부를 결정하세요."
            )
        save_receipt(project_dir, context.operation_id, result)
        snapshot.commit()

    return json.dumps(result, ensure_ascii=False)


def _prepare_add(
    deps: DesignDeps,
    *,
    project_dir: Path,
    slide_count: int,
    slide_index: int,
    title: str,
    content_summary: str,
    component_hint: str,
    slide_type: str,
    speaker_notes: str,
    color_theme: str,
    design_summary: dict | None,
) -> dict:
    """add: 파일 변경 없이 새 outline을 기준으로 생성 태스크를 만든다."""
    if not title or not content_summary:
        _raise_validation(
            "prepare_slide_edit.add",
            "title and content_summary are required for add action",
            slide_index=slide_index,
            title=title,
            content_summary_len=len(content_summary or ""),
        )

    project_service = deps.project_service
    insert_idx = (
        (slide_index - 1) if 1 <= slide_index <= slide_count + 1 else slide_count
    )
    if slide_index != -1 and slide_index > slide_count + 1:
        _raise_validation(
            "prepare_slide_edit.add",
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count + 1}, or -1)",
            slide_index=slide_index,
            slide_count=slide_count,
        )

    outline_data = {
        "title": title,
        "content_summary": content_summary,
        "component_hint": component_hint,
        "slide_type": slide_type,
        "speaker_notes": speaker_notes,
    }
    outline_json = json.dumps(outline_data, ensure_ascii=False)

    outline = parse_outline_json(outline_json)
    slide_outline = outline.slides[0]

    prev_outline = None
    next_outline = None
    new_count = slide_count + 1
    if insert_idx > 0:
        prev_outline = _load_outline_for_edit(
            project_service, project_dir, insert_idx - 1
        )
    if insert_idx + 1 < new_count:
        next_outline = _load_outline_for_edit(project_service, project_dir, insert_idx)

    directives = _directives_for(project_service, project_dir, insert_idx + 1, title)
    task = deps.design_service.prepare_slide(
        slide_outline,
        design_summary=design_summary,
        slide_index=insert_idx + 1,
        total_slides=new_count,
        color_theme=color_theme,
        prev_outline=prev_outline,
        next_outline=next_outline,
        design_directives=directives,
    )
    task["_target_index"] = insert_idx
    task["_outline"] = outline_data
    return task


def _prepare_update(
    deps: DesignDeps,
    *,
    project_dir: Path,
    slide_count: int,
    slide_index: int,
    title: str,
    content_summary: str,
    component_hint: str,
    slide_type: str,
    speaker_notes: str,
    color_theme: str,
    design_summary: dict | None,
) -> dict:
    """update: 파일 변경 없이 정규화된 outline으로 생성 태스크를 만든다."""
    if slide_index < 1 or slide_index > slide_count:
        _raise_validation(
            "prepare_slide_edit.update",
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})",
            slide_index=slide_index,
            slide_count=slide_count,
        )

    project_service = deps.project_service
    idx = slide_index - 1

    metadata = project_service.load_metadata(project_dir)
    if metadata.source == "imported" and (not title or not content_summary):
        _raise_validation(
            "prepare_slide_edit.update",
            "title and content_summary are required for update action "
            "on imported projects (no outline available)",
            slide_index=slide_index,
            source=metadata.source,
        )

    existing_outline = _load_outline_for_edit(project_service, project_dir, idx)
    existing_notes = (
        existing_outline.speaker_notes
        or project_service.load_design_spec_slide(project_dir, idx).speaker_notes
    )
    if title and content_summary:
        outline_data = {
            "title": title,
            "content_summary": content_summary,
            "component_hint": component_hint,
            "slide_type": slide_type,
            "speaker_notes": speaker_notes or existing_notes,
        }
        slide_outline = parse_outline_json(
            json.dumps(outline_data, ensure_ascii=False)
        ).slides[0]
        if content_summary == existing_outline.content_summary:
            slide_outline = replace(
                slide_outline,
                layout_plan=existing_outline.layout_plan,
                source_refs=existing_outline.source_refs,
                assumptions=existing_outline.assumptions,
            )
    else:
        slide_outline = replace(
            existing_outline, speaker_notes=speaker_notes or existing_notes
        )
    outline_data = asdict(slide_outline)
    directives = _directives_for(
        project_service, project_dir, slide_index, slide_outline.title
    )
    task = deps.design_service.prepare_slide(
        slide_outline,
        design_summary=design_summary,
        slide_index=slide_index,
        total_slides=slide_count,
        color_theme=color_theme,
        design_directives=directives,
    )
    task["_target_index"] = idx
    task["_outline"] = outline_data
    return task


def _load_outline_for_edit(
    project_service: ProjectService, project_dir: Path, index: int
) -> SlideOutline:
    """파일이 없는 imported 위치는 기존 동기화 placeholder와 동일하게 취급한다."""
    try:
        raw = project_service.load_outline_slide(project_dir, index)
    except (FileNotFoundError, IndexError):
        raw = json.dumps(
            {
                "title": "",
                "content_summary": "",
                "component_hint": "bullets",
                "slide_type": "content",
                "speaker_notes": "",
            }
        )
    return parse_outline_json(raw).slides[0]


def _directives_for(
    project_service: ProjectService, project_dir: Path, slide_index: int, title: str
) -> str:
    """DESIGN.md 에서 해당 슬라이드의 디자인 지시(톤+페이지 요청)를 만든다."""
    return project_service.load_design_directives(project_dir, slide_index, title)
