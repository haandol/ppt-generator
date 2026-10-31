"""단일 요소 수정과 임포트 슬라이드의 의미 트리 보완."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from ppt_generator.interfaces.index_validation import require_positive_slide_index
from ppt_generator.interfaces.schemas import LayoutNode, PptxSlideSpec
from ppt_generator.interfaces.spec_utils import lint_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_fingerprint
from ppt_generator.tools.design.edit_context import (
    ProjectSnapshot,
    decode_signed_context,
    encode_signed_context,
    load_receipt,
    project_edit_lock,
    project_revision,
    save_receipt,
)
from ppt_generator.tools.design.handlers.edit_validation import _raise_validation

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


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
    revision = project_revision(project_dir)

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
        if project_revision(project_dir) != revision:
            raise RuntimeError(
                "Project changed while preparing component backfill; retry prepare"
            )
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
    task["edit_context"] = encode_signed_context(
        {
            "kind": "component_modify",
            "version": 1,
            "project_id": project_id,
            "slide_index": slide_index,
            "component_id": component_id,
            "color_theme": color_theme,
            "revision": revision,
            "target_fingerprint": _component_fingerprint(spec),
        },
        project_dir,
    )
    if project_revision(project_dir) != revision:
        raise RuntimeError(
            "Project changed while preparing component edit; retry prepare"
        )
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
    edit_context: str,
    color_theme: str,
) -> str:
    """단일 component 부분 수정 결과를 검증·적용·저장·렌더·lint 한다."""
    require_positive_slide_index(slide_index)
    project_service = deps.project_service
    _, project_dir = project_service.resolve_existing_project_dir(project_id)
    with project_edit_lock(project_dir):
        context = decode_signed_context(edit_context, project_dir)
        expected = {
            "kind": "component_modify",
            "version": 1,
            "project_id": project_id,
            "slide_index": slide_index,
            "component_id": component_id,
            "color_theme": color_theme,
        }
        if any(context.get(key) != value for key, value in expected.items()):
            raise ValueError("edit_context does not match component ingest request")
        previous_result = load_receipt(project_dir, context["operation_id"])
        if previous_result is not None:
            return json.dumps(previous_result, ensure_ascii=False)
        if project_revision(project_dir) != context.get("revision"):
            raise ValueError("Stale edit_context: project changed after prepare")

        slide_count = project_service.get_design_spec_slide_count(project_dir)
        if slide_index > slide_count:
            raise ValueError(
                f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})"
            )

        from ppt_generator.interfaces import bg_image_utils

        bg_image_utils.set_project_seed(project_id)
        idx = slide_index - 1
        spec = project_service.load_design_spec_slide(project_dir, idx)
        if _component_fingerprint(spec) != context.get("target_fingerprint"):
            raise ValueError(
                "Stale edit_context: target component changed after prepare"
            )

        new_spec = deps.design_service.ingest_modify_component(
            spec=spec,
            component_id=component_id,
            output_json=modify_json,
        )
        if spec.images:
            new_spec = replace(new_spec, images=spec.images)
        kind, elem_idx, _ = _find_modified_element(new_spec, component_id)
        slide_lint = lint_slide_spec(
            new_spec, slide_index=slide_index, stop_on_layer_error=True
        )

        html: str | None = None
        if deps.slides_service is not None:
            html = deps.slides_service.render_single_slide_html(
                idx,
                new_spec,
                color_theme=color_theme,
                bg_image_policy=project_service.load_bg_image_policy(project_dir),
            )

        result: dict = {
            "project_id": project_id,
            "slide_index": slide_index,
            "component_id": component_id,
            "modified_element": {"type": kind, "index": elem_idx},
        }
        if slide_lint.has_violations:
            result["lint"] = slide_lint.to_dict()
            result["lint_suggestion"] = (
                f"슬라이드 {slide_index}에서 "
                f"{len(slide_lint.violations)}건의 lint 위반이 발견되었습니다. "
                "추가 수정이 필요한지 확인하세요."
            )

        with ProjectSnapshot(project_dir) as snapshot:
            project_service.save_design_spec_slide(project_dir, idx, new_spec)
            project_service.update_step(project_dir, "design_spec_modified")
            if html is not None:
                html_path = project_service.save_single_slide_html(
                    project_dir, idx, html
                )
                result["slide_html_path"] = str(html_path)
            save_receipt(project_dir, context["operation_id"], result)
            snapshot.commit()

        return json.dumps(result, ensure_ascii=False)


def _list_available_components(spec: PptxSlideSpec) -> list[dict]:
    """backfilled spec 의 component leaf 목록을 사용자 응답용으로 평탄화한다."""
    items: list[dict] = []

    def _walk(node: LayoutNode, path: list[str]) -> None:
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


def _find_modified_element(
    spec: PptxSlideSpec, component_id: str
) -> tuple[str, int, object]:
    """수정된 element 위치를 응답용으로 찾는다."""
    for i, tb in enumerate(spec.textboxes):
        if tb.component_id == component_id:
            return ("textbox", i, tb)
    for i, s in enumerate(spec.shapes):
        if s.component_id == component_id:
            return ("shape", i, s)
    raise ValueError(f"component_id missing after modification: {component_id}")


def _component_fingerprint(spec: PptxSlideSpec) -> str:
    """현재 슬라이드와 component 링크의 안정적인 fingerprint."""
    return slide_spec_fingerprint(spec)
