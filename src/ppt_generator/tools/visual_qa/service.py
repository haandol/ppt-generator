"""Visual QA 서비스 (prepare/ingest).

스크린샷 캡처(Playwright)는 결정론적 브라우저 렌더라 서버에 남는다. 그 스크린샷에
대한 비전 분석과 수정 spec 생성만 클라이언트로 오프로딩한다:

  1. capture_screenshots — 서버 (Playwright)
  2. prepare_analysis / ingest_analysis — 스크린샷+spec 로 이슈 감지 (클라이언트 생성)
  3. prepare_fix / ingest_fix — 이슈를 반영한 수정 spec 생성 (클라이언트 생성)
  4. 저장 + HTML 재렌더 — 서버

iteration 루프(분석→수정→재캡처)는 클라이언트(스킬)가 오케스트레이션한다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import fields, replace
from pathlib import Path

from ppt_generator.interfaces.constants import (
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)
from ppt_generator.interfaces.handoff import build_llm_task
from ppt_generator.interfaces.llm_output_models import (
    VisualQAContentSlideSpecOutput,
    VisualQAOutput,
    VisualQASimpleSlideSpecOutput,
    _BaseSlideSpecOutput,
)
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.tools.visual_qa.screenshot import capture_screenshots

logger = logging.getLogger(__name__)

_GEOMETRY_FIELDS = {"left_px", "top_px", "width_px", "height_px"}
_PADDING_FIELDS = {
    "padding_left_px",
    "padding_right_px",
    "padding_top_px",
    "padding_bottom_px",
}
_FONT_FIELDS = {"text_size_pt"}
_TEXT_FLOW_FIELDS = {
    "text_size_pt",
    "line_spacing_pt",
    "vertical_alignment",
    "autofit_mode",
}
_COLOR_FIELDS = {
    "fill_color",
    "border_color",
    "text_color",
}
_ISSUE_ALLOWED_FIELDS: dict[str, set[str]] = {
    "text_truncation": _GEOMETRY_FIELDS | _PADDING_FIELDS | _TEXT_FLOW_FIELDS,
    "overlap": _GEOMETRY_FIELDS,
    "label_intrusion": _GEOMETRY_FIELDS,
    "decoration_overlap": _GEOMETRY_FIELDS,
    "arrow_through_card": _GEOMETRY_FIELDS,
    "orphan_label_no_arrow": _GEOMETRY_FIELDS,
    "overflow": _GEOMETRY_FIELDS | _PADDING_FIELDS | _TEXT_FLOW_FIELDS,
    "contrast": _COLOR_FIELDS,
    "misalignment": _GEOMETRY_FIELDS,
    "arrow_disconnected": _GEOMETRY_FIELDS,
    "wrong_vertical_alignment": {"vertical_alignment"},
    "inconsistent_font_size": _FONT_FIELDS,
    "inconsistent_padding": _PADDING_FIELDS,
    "inconsistent_spacing": _GEOMETRY_FIELDS,
    "zero_gap": _GEOMETRY_FIELDS,
    "small_font": _FONT_FIELDS,
    "insufficient_padding": _GEOMETRY_FIELDS | _PADDING_FIELDS,
    "content_too_sparse": _GEOMETRY_FIELDS | _PADDING_FIELDS | _TEXT_FLOW_FIELDS,
    "content_too_dense": _GEOMETRY_FIELDS | _PADDING_FIELDS | _TEXT_FLOW_FIELDS,
    "unbalanced_spacing": _GEOMETRY_FIELDS,
    "label_line_overlap": _GEOMETRY_FIELDS,
    "hidden_decorative_strip": {"z_index"},
    "wrong_z_order": {"z_index"},
}
_ISSUE_ALLOWED_RUN_FIELDS: dict[str, set[str]] = {
    "text_truncation": {"font_size_pt"},
    "overflow": {"font_size_pt"},
    "contrast": {"color"},
    "inconsistent_font_size": {"font_size_pt"},
    "small_font": {"font_size_pt"},
    "content_too_sparse": {"font_size_pt"},
    "content_too_dense": {"font_size_pt"},
}


class VisualQAService:
    """스크린샷 캡처(서버) + 분석/수정 태스크 조립·검증(prepare/ingest)."""

    # ------------------------------------------------------------------
    # Phase 1: 스크린샷 캡처 (서버, Playwright)
    # ------------------------------------------------------------------

    @staticmethod
    def capture_screenshots(
        project_dir: Path,
        indices: list[int],
        iteration: int = 0,
    ) -> dict[int, Path]:
        """Playwright headless Chromium으로 슬라이드 스크린샷을 캡처한다."""
        return capture_screenshots(project_dir, indices, iteration)

    # ------------------------------------------------------------------
    # Phase 2: 스크린샷 분석 (prepare/ingest)
    # ------------------------------------------------------------------

    def prepare_analysis(
        self,
        png_path: Path,
        slide_index: int,
        design_spec: PptxSlideSpec,
    ) -> dict:
        """스크린샷 분석 태스크를 조립한다. images 에 스크린샷 경로를 실어 보낸다.

        Args:
            png_path: 분석할 스크린샷 파일 경로.
            slide_index: 0-based 슬라이드 인덱스.
            design_spec: 해당 슬라이드의 현재 디자인 스펙.
        """
        spec_json = slide_spec_to_json(design_spec)
        prompt = (
            f"다음은 슬라이드 {slide_index + 1}의 스크린샷과 디자인 스펙입니다.\n\n"
            f"<design_spec>\n{spec_json}\n</design_spec>\n\n"
            "위 스크린샷을 분석하여 시각적 이슈를 감지해주세요."
        )
        return build_llm_task(
            system_prompt=VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=VisualQAOutput.model_json_schema(),
            images=[str(png_path)],
        )

    def ingest_analysis(self, analysis_json: str | dict) -> VisualQAOutput:
        """클라이언트가 생성한 분석 결과 JSON 을 검증한다."""
        if isinstance(analysis_json, str):
            return VisualQAOutput.model_validate_json(analysis_json)
        return VisualQAOutput.model_validate(analysis_json)

    @staticmethod
    def validate_issue_targets(
        analysis: VisualQAOutput, current_spec: PptxSlideSpec
    ) -> None:
        """분석 이슈의 요소 참조가 현재 슬라이드 범위 안인지 검증한다."""
        counts = {
            "textbox": len(current_spec.textboxes),
            "shape": len(current_spec.shapes),
        }
        for issue in analysis.issues:
            if issue.element_index >= counts[issue.element_type]:
                raise ValueError(
                    f"Visual QA issue references invalid {issue.element_type} "
                    f"index {issue.element_index}"
                )
            if (
                issue.related_element_type is not None
                and issue.related_element_index is not None
                and issue.related_element_index >= counts[issue.related_element_type]
            ):
                raise ValueError(
                    "Visual QA issue references invalid related "
                    f"{issue.related_element_type} index "
                    f"{issue.related_element_index}"
                )

    # ------------------------------------------------------------------
    # Phase 3: 디자인 스펙 수정 (prepare/ingest)
    # ------------------------------------------------------------------

    def prepare_fix(
        self,
        png_path: Path,
        current_spec: PptxSlideSpec,
        issues: list[dict],
    ) -> dict:
        """수정 태스크를 조립한다. 현재 spec + 스크린샷 + 이슈 목록을 실어 보낸다."""
        spec_json = slide_spec_to_json(current_spec)
        issues_json = json.dumps(issues, ensure_ascii=False, indent=2)
        prompt = (
            "다음 슬라이드 디자인 스펙에서 시각적 이슈를 수정해주세요.\n\n"
            f"<current_design_spec>\n{spec_json}\n</current_design_spec>\n\n"
            f"<detected_issues>\n{issues_json}\n</detected_issues>\n\n"
            "위 이슈를 수정한 전체 디자인 스펙 JSON을 출력해주세요."
        )
        slide_type = current_spec.slide_type or "content"
        model: type[_BaseSlideSpecOutput] = (
            VisualQAContentSlideSpecOutput
            if slide_type == "content"
            else VisualQASimpleSlideSpecOutput
        )
        return build_llm_task(
            system_prompt=VISUAL_QA_FIX_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=model.model_json_schema(),
            images=[str(png_path)],
        )

    def ingest_fix(
        self,
        fix_json: str | dict,
        current_spec: PptxSlideSpec,
        issues: list[dict] | None = None,
    ) -> PptxSlideSpec | None:
        """클라이언트가 생성한 수정 spec JSON 을 검증·정합화한다.

        Pydantic 검증 → to_dataclass → 필드 보존/권한 검증을 적용한다.
        검증 실패 시 None.
        """
        slide_type = current_spec.slide_type or "content"
        model: type[_BaseSlideSpecOutput] = (
            VisualQAContentSlideSpecOutput
            if slide_type == "content"
            else VisualQASimpleSlideSpecOutput
        )
        try:
            if isinstance(fix_json, str):
                output = model.model_validate_json(fix_json)
            else:
                output = model.model_validate(fix_json)
            spec = output.to_dataclass()
            if len(spec.textboxes) != len(current_spec.textboxes):
                raise ValueError("Visual QA fix cannot add or remove textboxes")
            if len(spec.shapes) != len(current_spec.shapes):
                raise ValueError("Visual QA fix cannot add or remove shapes")
            if any(
                _textbox_identity(fixed) != _textbox_identity(existing)
                for fixed, existing in zip(
                    spec.textboxes, current_spec.textboxes, strict=True
                )
            ):
                raise ValueError(
                    "Visual QA fix cannot change or reorder textbox content"
                )
            if any(
                _shape_identity(fixed) != _shape_identity(existing)
                for fixed, existing in zip(
                    spec.shapes, current_spec.shapes, strict=True
                )
            ):
                raise ValueError("Visual QA fix cannot change or reorder shape content")

            _validate_issue_scoped_changes(spec, current_spec, issues or [])

            issue_types = {
                issue.get("issue_type")
                for issue in (issues or [])
                if isinstance(issue, dict)
            }
            can_change_z_index = bool(
                issue_types & {"wrong_z_order", "hidden_decorative_strip"}
            )
            if not can_change_z_index and (
                any(
                    fixed.z_index != existing.z_index
                    for fixed, existing in zip(
                        spec.textboxes, current_spec.textboxes, strict=True
                    )
                )
                or any(
                    fixed.z_index != existing.z_index
                    for fixed, existing in zip(
                        spec.shapes, current_spec.shapes, strict=True
                    )
                )
            ):
                raise ValueError(
                    "Visual QA fix cannot change z_index without a layering issue"
                )
            if (
                "contrast" not in issue_types
                and spec.background_color != current_spec.background_color
            ):
                raise ValueError(
                    "Visual QA fix cannot change background_color without "
                    "a contrast issue"
                )

            textboxes = [
                replace(
                    fixed,
                    paragraphs=_preserve_paragraph_content(
                        fixed.paragraphs, existing.paragraphs
                    ),
                    grid_cell=existing.grid_cell,
                    component_id=existing.component_id,
                )
                for fixed, existing in zip(
                    spec.textboxes, current_spec.textboxes, strict=True
                )
            ]
            shapes = [
                replace(
                    fixed,
                    shape_type=existing.shape_type,
                    text=existing.text,
                    paragraphs=_preserve_paragraph_content(
                        fixed.paragraphs, existing.paragraphs
                    ),
                    svg_path=existing.svg_path,
                    grid_cell=existing.grid_cell,
                    component_id=existing.component_id,
                )
                for fixed, existing in zip(
                    spec.shapes, current_spec.shapes, strict=True
                )
            ]
            spec = replace(
                spec,
                textboxes=textboxes,
                shapes=shapes,
                images=current_spec.images,
                slide_type=current_spec.slide_type,
                speaker_notes=current_spec.speaker_notes,
                grid_plan=current_spec.grid_plan,
                design_doc=current_spec.design_doc,
                background_image_bytes=current_spec.background_image_bytes,
                background_image_src=current_spec.background_image_src,
            )
            return spec
        except Exception:
            logger.exception("디자인 스펙 수정 검증 실패")
            return None


def _paragraph_text_identity(paragraphs) -> tuple:
    return tuple(
        tuple((run.text, run.href) for run in paragraph.runs)
        for paragraph in paragraphs
    )


def _textbox_identity(textbox) -> tuple:
    return (
        textbox.component_id,
        textbox.grid_cell,
        _paragraph_text_identity(textbox.paragraphs),
    )


def _shape_identity(shape) -> tuple:
    return (
        shape.component_id,
        shape.grid_cell,
        shape.shape_type,
        shape.text,
        shape.svg_path,
        _paragraph_text_identity(shape.paragraphs),
    )


def _preserve_paragraph_content(fixed_paragraphs, existing_paragraphs):
    """Visual 스타일은 적용하되 텍스트·링크·목록 구조는 기존 값을 보존한다."""
    return [
        replace(
            fixed_paragraph,
            bullet_level=existing_paragraph.bullet_level,
            margin_left_px=existing_paragraph.margin_left_px,
            indent_px=existing_paragraph.indent_px,
            runs=[
                replace(fixed_run, text=existing_run.text, href=existing_run.href)
                for fixed_run, existing_run in zip(
                    fixed_paragraph.runs,
                    existing_paragraph.runs,
                    strict=True,
                )
            ],
        )
        for fixed_paragraph, existing_paragraph in zip(
            fixed_paragraphs,
            existing_paragraphs,
            strict=True,
        )
    ]


def _validate_issue_scoped_changes(
    fixed_spec: PptxSlideSpec,
    current_spec: PptxSlideSpec,
    issues: list[dict],
) -> None:
    """서명된 issue가 지목한 요소와 필드에만 시각 변경을 허용한다."""
    field_permissions: dict[tuple[str, int], set[str]] = {}
    run_permissions: dict[tuple[str, int], set[str]] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_type = str(issue.get("issue_type"))
        allowed_fields = _ISSUE_ALLOWED_FIELDS.get(issue_type, set())
        allowed_run_fields = _ISSUE_ALLOWED_RUN_FIELDS.get(issue_type, set())
        _grant_issue_permission(
            field_permissions,
            issue.get("element_type"),
            issue.get("element_index"),
            allowed_fields,
        )
        _grant_issue_permission(
            field_permissions,
            issue.get("related_element_type"),
            issue.get("related_element_index"),
            allowed_fields,
        )
        _grant_issue_permission(
            run_permissions,
            issue.get("element_type"),
            issue.get("element_index"),
            allowed_run_fields,
        )
        _grant_issue_permission(
            run_permissions,
            issue.get("related_element_type"),
            issue.get("related_element_index"),
            allowed_run_fields,
        )

    for element_type, fixed_items, current_items in (
        ("textbox", fixed_spec.textboxes, current_spec.textboxes),
        ("shape", fixed_spec.shapes, current_spec.shapes),
    ):
        for index, (fixed, current) in enumerate(
            zip(fixed_items, current_items, strict=True)
        ):
            changed = {
                field.name
                for field in fields(current)
                if field.name != "paragraphs"
                if getattr(fixed, field.name) != getattr(current, field.name)
            }
            disallowed = changed - field_permissions.get((element_type, index), set())
            if disallowed:
                raise ValueError(
                    f"Visual QA fix cannot change {element_type}[{index}] fields "
                    f"outside detected issues: {sorted(disallowed)}"
                )
            _validate_paragraph_style_changes(
                fixed.paragraphs,
                current.paragraphs,
                element_type=element_type,
                element_index=index,
                allowed_run_fields=run_permissions.get((element_type, index), set()),
            )


def _validate_paragraph_style_changes(
    fixed_paragraphs,
    current_paragraphs,
    *,
    element_type: str,
    element_index: int,
    allowed_run_fields: set[str],
) -> None:
    for paragraph_index, (fixed_paragraph, current_paragraph) in enumerate(
        zip(fixed_paragraphs, current_paragraphs, strict=True)
    ):
        changed_paragraph_fields = {
            field.name
            for field in fields(current_paragraph)
            if field.name != "runs"
            if getattr(fixed_paragraph, field.name)
            != getattr(current_paragraph, field.name)
        }
        if changed_paragraph_fields:
            raise ValueError(
                f"Visual QA fix cannot change {element_type}[{element_index}] "
                f"paragraph[{paragraph_index}] fields outside detected issues: "
                f"{sorted(changed_paragraph_fields)}"
            )
        for run_index, (fixed_run, current_run) in enumerate(
            zip(fixed_paragraph.runs, current_paragraph.runs, strict=True)
        ):
            changed_run_fields = {
                field.name
                for field in fields(current_run)
                if getattr(fixed_run, field.name) != getattr(current_run, field.name)
            }
            disallowed = changed_run_fields - allowed_run_fields
            if disallowed:
                raise ValueError(
                    f"Visual QA fix cannot change {element_type}[{element_index}] "
                    f"paragraph[{paragraph_index}].run[{run_index}] fields outside "
                    f"detected issues: {sorted(disallowed)}"
                )


def _grant_issue_permission(
    permissions: dict[tuple[str, int], set[str]],
    element_type,
    element_index,
    allowed: set[str],
) -> None:
    if element_type not in {"textbox", "shape"} or not isinstance(element_index, int):
        return
    permissions.setdefault((element_type, element_index), set()).update(allowed)
