"""슬라이드 수정 핸들러 (prepare/ingest) + move/delete.

add/update/modify_component 는 LLM 생성이 필요하므로 prepare/ingest 로 나뉜다.
move/delete 는 LLM 이 필요 없어 단일 도구로 유지된다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING, NoReturn

from ppt_generator.interfaces.index_validation import require_positive_slide_index
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.interfaces.utils import parse_outline_json
from ppt_generator.tools.design.edit_context import (
    ProjectSnapshot,
    SlideEditContext,
    load_receipt,
    project_edit_lock,
    project_revision,
    save_receipt,
)

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


def _raise_validation(tool: str, msg: str, **context) -> NoReturn:
    """입력 검증 실패를 로깅하고 ValueError 를 raise."""
    ctx_str = " ".join(f"{k}={v!r}" for k, v in context.items() if v is not None)
    logger.error("%s validation failed: %s | %s", tool, msg, ctx_str)
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# move / delete (LLM 불필요)
# ---------------------------------------------------------------------------


def handle_move(
    deps: DesignDeps,
    *,
    project_id: str,
    from_index: int,
    to_index: int,
) -> str:
    """슬라이드를 from_index → to_index로 이동한다."""
    if from_index < 1:
        _raise_validation(
            "move_slide",
            f"Invalid from_index: {from_index} (must be >= 1)",
            from_index=from_index,
        )
    if to_index < 1:
        _raise_validation(
            "move_slide",
            f"Invalid to_index: {to_index} (must be >= 1)",
            to_index=to_index,
        )
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
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


def handle_delete(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
) -> str:
    """슬라이드를 삭제한다."""
    require_positive_slide_index(slide_index)
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)

    if slide_index < 1 or slide_index > slide_count:
        _raise_validation(
            "delete_slide",
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})",
            slide_index=slide_index,
            slide_count=slide_count,
        )

    idx = slide_index - 1
    project_service.sync_outline_to_design_spec_count(project_dir)
    project_service.delete_slide_images(project_dir, idx, slide_count)
    project_service.delete_design_spec_slide(project_dir, idx)
    project_service.delete_slide_html(project_dir, idx)
    project_service.delete_outline_slide(project_dir, idx)
    project_service.renumber_design_spec_image_srcs(project_dir)
    project_service.update_step(project_dir, "design_spec_modified")
    project_service.sync_num_slides(project_dir)

    return json.dumps(
        {
            "project_id": project_id,
            "slide_count": project_service.get_design_spec_slide_count(project_dir),
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# add / update — prepare (outline 변경 + 슬라이드 생성 태스크) / ingest (저장)
# ---------------------------------------------------------------------------


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
    prep["edit_context"] = context.to_token()
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

    context = SlideEditContext.from_token(edit_context)
    if (
        context.project_id != project_id
        or context.action != action
        or context.requested_slide_index != slide_index
    ):
        raise ValueError("edit_context does not match ingest request")

    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
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
    project_dir,
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


# --- add/update prepare helpers ---


def _prepare_add(
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

    if title and content_summary:
        outline_data = {
            "title": title,
            "content_summary": content_summary,
            "component_hint": component_hint,
            "slide_type": slide_type,
            "speaker_notes": speaker_notes,
        }
        slide_outline = parse_outline_json(
            json.dumps(outline_data, ensure_ascii=False)
        ).slides[0]
    else:
        slide_outline = _load_outline_for_edit(project_service, project_dir, idx)
        outline_data = {
            "title": slide_outline.title,
            "content_summary": slide_outline.content_summary,
            "component_hint": slide_outline.component_hint,
            "slide_type": slide_outline.slide_type,
            "speaker_notes": slide_outline.speaker_notes,
        }
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


def _load_outline_for_edit(project_service, project_dir, index: int):
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


def _directives_for(project_service, project_dir, slide_index: int, title: str) -> str:
    """DESIGN.md 에서 해당 슬라이드의 디자인 지시(톤+페이지 요청)를 만든다."""
    design_doc = project_service.load_design_doc_md(project_dir)
    if design_doc is None:
        return ""
    return design_doc.directives_for(slide_index, title)


# ---------------------------------------------------------------------------
# modify_component — prepare (+ lazy backfill) / ingest
# ---------------------------------------------------------------------------


def handle_prepare_modify_component(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    component_id: str,
    instruction: str,
    color_theme: str,
) -> str:
    """단일 component 부분 수정 태스크를 조립한다.

    imported 슬라이드(design_doc=None)면 backfill 태스크를 먼저 반환한다
    (stage="backfill"). 클라이언트가 backfill 을 ingest 한 뒤 다시 이 도구를 호출하면
    stage="modify" 태스크를 반환한다.
    """
    if not project_id:
        _raise_validation("prepare_modify_component", "project_id is required")
    if slide_index < 1:
        _raise_validation(
            "prepare_modify_component",
            f"slide_index must be >= 1: {slide_index}",
            project_id=project_id,
            slide_index=slide_index,
        )
    if not component_id:
        _raise_validation(
            "prepare_modify_component",
            "component_id is required",
            project_id=project_id,
            slide_index=slide_index,
        )
    if not instruction or not instruction.strip():
        _raise_validation(
            "prepare_modify_component",
            "instruction is required",
            project_id=project_id,
            slide_index=slide_index,
            component_id=component_id,
        )

    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)

    from ppt_generator.interfaces import bg_image_utils

    bg_image_utils.set_project_seed(project_id)

    slide_count = project_service.get_design_spec_slide_count(project_dir)
    if slide_index > slide_count:
        _raise_validation(
            "prepare_modify_component",
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})",
            project_id=project_id,
            slide_index=slide_index,
            slide_count=slide_count,
        )

    idx = slide_index - 1
    spec = project_service.load_design_spec_slide(project_dir, idx)

    if spec.design_doc is None:
        # imported 슬라이드는 backfill 먼저.
        if spec.slide_type not in ("content", ""):
            _raise_validation(
                "prepare_modify_component",
                f"Slide {slide_index} has no design_doc and slide_type="
                f"{spec.slide_type!r}. modify_component supports content slides only. "
                "Use update slide instead.",
                project_id=project_id,
                slide_index=slide_index,
                slide_type=spec.slide_type,
            )
        task = deps.design_service.prepare_backfill(spec, slide_index=slide_index)
        task["project_id"] = project_id
        task["slide_index"] = slide_index
        task["component_id"] = component_id
        task["instruction"] = instruction
        task["stage"] = "backfill"
        logger.info(
            "prepare_modify_component: backfill task | project_id=%r slide_index=%d",
            project_id,
            slide_index,
        )
        return json.dumps(task, ensure_ascii=False)

    task = deps.design_service.prepare_modify_component(
        spec=spec,
        component_id=component_id,
        instruction=instruction,
        slide_index=slide_index,
        color_theme=color_theme,
    )
    task["project_id"] = project_id
    task["slide_index"] = slide_index
    task["component_id"] = component_id
    task["stage"] = "modify"
    return json.dumps(task, ensure_ascii=False)


def handle_ingest_backfill(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    backfill_json: str,
) -> str:
    """imported 슬라이드 backfill 결과를 검증·저장한다.

    저장 후 available_components 를 반환해 클라이언트가 유효한 component_id 로
    prepare_modify_component 를 다시 호출하게 한다.
    """
    require_positive_slide_index(slide_index)
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)
    if slide_index > slide_count:
        raise ValueError(
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
        )
    idx = slide_index - 1
    spec = project_service.load_design_spec_slide(project_dir, idx)

    try:
        new_spec = deps.design_service.ingest_backfill(
            spec, backfill_json, slide_index=slide_index
        )
    except Exception as exc:
        logger.error(
            "ingest_backfill failed | project_id=%r slide_index=%d error=%s",
            project_id,
            slide_index,
            exc,
            exc_info=True,
        )
        raise ValueError(
            f"design_doc backfill failed for slide {slide_index}: {exc}. "
            "Use update slide for this slide instead."
        ) from exc

    project_service.save_design_spec_slide(project_dir, idx, new_spec)
    project_service.update_step(project_dir, "design_spec_modified")

    return json.dumps(
        {
            "project_id": project_id,
            "slide_index": slide_index,
            "status": "backfilled",
            "available_components": _list_available_components(new_spec),
        },
        ensure_ascii=False,
    )


def handle_ingest_modify_component(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_index: int,
    component_id: str,
    modify_json: str,
    color_theme: str,
) -> str:
    """단일 component 부분 수정 결과를 검증·적용·저장·렌더·lint 한다."""
    require_positive_slide_index(slide_index)
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)
    if slide_index > slide_count:
        raise ValueError(
            f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
        )

    from ppt_generator.interfaces import bg_image_utils

    bg_image_utils.set_project_seed(project_id)

    idx = slide_index - 1
    spec = project_service.load_design_spec_slide(project_dir, idx)

    new_spec = deps.design_service.ingest_modify_component(
        spec=spec,
        component_id=component_id,
        output_json=modify_json,
    )

    if spec.images:
        new_spec = replace(new_spec, images=spec.images)

    project_service.save_design_spec_slide(project_dir, idx, new_spec)
    project_service.renumber_design_spec_image_srcs(project_dir)
    project_service.update_step(project_dir, "design_spec_modified")

    kind, elem_idx, _ = _find_modified_element(new_spec, component_id)

    slide_html_path: str | None = None
    if deps.slides_service is not None:
        html = deps.slides_service.render_single_slide_html(
            idx,
            new_spec,
            color_theme=color_theme,
            bg_image_policy=project_service.load_bg_image_policy(project_dir),
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

    return json.dumps(result, ensure_ascii=False)


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


def _find_modified_element(spec, component_id: str) -> tuple[str, int, object]:
    """수정된 element 위치를 응답용으로 찾는다."""
    for i, tb in enumerate(spec.textboxes):
        if tb.component_id == component_id:
            return ("textbox", i, tb)
    for i, s in enumerate(spec.shapes):
        if s.component_id == component_id:
            return ("shape", i, s)
    raise ValueError(f"component_id missing after modification: {component_id}")
