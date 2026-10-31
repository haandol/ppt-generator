"""슬라이드 이동·삭제와 연결된 산출물의 트랜잭션 처리."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ppt_generator.interfaces.index_validation import require_positive_slide_index
from ppt_generator.tools.design.design_doc_md import remap_page_request_numbers
from ppt_generator.tools.design.edit_context import (
    ProjectSnapshot,
    project_edit_lock,
)
from ppt_generator.tools.design.handlers.edit_validation import _raise_validation

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps


def handle_move(
    deps: DesignDeps,
    *,
    project_id: str,
    from_index: int,
    to_index: int,
) -> str:
    """슬라이드 파일과 번호로 연결된 디자인 요청을 같은 트랜잭션에서 이동한다."""
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
    with project_edit_lock(project_dir):
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        if from_index > slide_count:
            _raise_validation(
                "move_slide",
                f"Invalid from_index: {from_index} (valid range: 1-{slide_count})",
                project_id=project_id,
                from_index=from_index,
                slide_count=slide_count,
            )
        if to_index > slide_count:
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
        with ProjectSnapshot(project_dir) as snapshot:
            project_service.sync_outline_to_design_spec_count(project_dir)
            project_service.move_outline_slide(project_dir, from_idx, to_idx)
            project_service.move_slide_images(
                project_dir, from_idx, to_idx, slide_count
            )
            project_service.move_design_spec_slide(project_dir, from_idx, to_idx)
            project_service.move_slide_html(project_dir, from_idx, to_idx)
            project_service.renumber_design_spec_image_srcs(project_dir)
            raw_design = project_service.design_spec_store.load_design_doc_md(
                project_dir
            )
            if raw_design is not None:
                order = list(range(1, slide_count + 1))
                order.insert(to_idx, order.pop(from_idx))
                positions = {old: new for new, old in enumerate(order, start=1)}
                updated_design = remap_page_request_numbers(raw_design, positions)
                if updated_design != raw_design:
                    project_service.save_design_doc_md(project_dir, updated_design)
            project_service.update_step(project_dir, "design_spec_modified")
            snapshot.commit()

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

    with project_edit_lock(project_dir):
        slide_count = project_service.get_design_spec_slide_count(project_dir)

        if slide_index > slide_count:
            _raise_validation(
                "delete_slide",
                f"Invalid slide_index: {slide_index} (valid range: 1-{slide_count})",
                slide_index=slide_index,
                slide_count=slide_count,
            )

        idx = slide_index - 1
        with ProjectSnapshot(project_dir) as snapshot:
            project_service.sync_outline_to_design_spec_count(project_dir)
            project_service.delete_slide_images(project_dir, idx, slide_count)
            project_service.delete_design_spec_slide(project_dir, idx)
            project_service.delete_slide_html(project_dir, idx)
            project_service.delete_outline_slide(project_dir, idx)
            project_service.renumber_design_spec_image_srcs(project_dir)
            project_service.update_step(project_dir, "design_spec_modified")
            project_service.sync_num_slides(project_dir)
            result = {
                "project_id": project_id,
                "slide_count": project_service.get_design_spec_slide_count(project_dir),
            }
            snapshot.commit()

        return json.dumps(result, ensure_ascii=False)
