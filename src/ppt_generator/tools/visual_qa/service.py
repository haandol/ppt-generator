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
from dataclasses import replace
from pathlib import Path

from ppt_generator.interfaces.constants import (
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)
from ppt_generator.interfaces.handoff import build_llm_task
from ppt_generator.interfaces.llm_output_models import (
    VisualQAFixPatchOutput,
    VisualQAOutput,
    VisualQAPatchOperation,
)
from ppt_generator.interfaces.schemas import PptxParagraph, PptxSlideSpec
from ppt_generator.interfaces.layout_derivation import (
    derive_spec_layout_bboxes,
)
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
    "autofit",
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
        *,
        design_directives: str = "",
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
            f"\n\n<design_intent>\n{design_directives}\n</design_intent>"
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
        *,
        design_directives: str = "",
    ) -> dict:
        """수정 태스크를 조립한다. 현재 spec + 스크린샷 + 이슈 목록을 실어 보낸다."""
        spec_json = slide_spec_to_json(current_spec)
        issues_json = json.dumps(issues, ensure_ascii=False, indent=2)
        prompt = (
            "다음 슬라이드 디자인 스펙에서 시각적 이슈를 수정해주세요.\n\n"
            f"<current_design_spec>\n{spec_json}\n</current_design_spec>\n\n"
            f"<detected_issues>\n{issues_json}\n</detected_issues>\n\n"
            "위 이슈를 해결하는 최소 replace operation 목록만 출력해주세요. "
            "텍스트 내용, 요소 수·순서와 의미 링크는 변경하지 마세요."
            f"\n\n<design_intent>\n{design_directives}\n</design_intent>"
        )
        return build_llm_task(
            system_prompt=VISUAL_QA_FIX_SYSTEM_PROMPT,
            user_prompt=prompt,
            response_schema=VisualQAFixPatchOutput.model_json_schema(),
            images=[str(png_path)],
        )

    def ingest_fix(
        self,
        fix_json: str | dict,
        current_spec: PptxSlideSpec,
        issues: list[dict] | None = None,
    ) -> PptxSlideSpec | None:
        """클라이언트 patch를 issue 범위 안에서 원자적으로 적용한다.

        전체 spec을 다시 받지 않아 콘텐츠와 계층 메타데이터가 흔들리지 않으며,
        허용되지 않은 field나 target이 하나라도 있으면 아무 변경도 반환하지 않는다.
        """
        try:
            if isinstance(fix_json, str):
                output = VisualQAFixPatchOutput.model_validate_json(fix_json)
            else:
                output = VisualQAFixPatchOutput.model_validate(fix_json)
            return _apply_visual_patch(current_spec, output.operations, issues or [])
        except Exception:
            logger.exception("Visual QA patch 검증 실패")
            return None


def _issue_permissions(
    issues: list[dict],
) -> tuple[dict[tuple[str, int], set[str]], dict[tuple[str, int], set[str]], set[str]]:
    """검증된 issue 목록에서 element/run/slide field 권한을 계산한다."""
    field_permissions: dict[tuple[str, int], set[str]] = {}
    run_permissions: dict[tuple[str, int], set[str]] = {}
    issue_types: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_type = str(issue.get("issue_type"))
        issue_types.add(issue_type)
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
    return field_permissions, run_permissions, issue_types


def _replace_run(
    paragraphs: list[PptxParagraph],
    operation: VisualQAPatchOperation,
) -> list[PptxParagraph]:
    """지정된 text run의 허용 스타일 필드 하나만 교체한다."""
    assert operation.paragraph_index is not None
    assert operation.run_index is not None
    if operation.paragraph_index >= len(paragraphs):
        raise ValueError("paragraph_index is out of range")
    paragraph = paragraphs[operation.paragraph_index]
    if operation.run_index >= len(paragraph.runs):
        raise ValueError("run_index is out of range")
    run = paragraph.runs[operation.run_index]
    value = operation.value
    if operation.field == "font_size_pt" and not isinstance(value, int):
        raise ValueError("font_size_pt patch value must be an integer")
    if operation.field == "color" and value is not None and not isinstance(value, str):
        raise ValueError("color patch value must be a string or null")
    runs = list(paragraph.runs)
    runs[operation.run_index] = replace(run, **{operation.field: value})
    updated = list(paragraphs)
    updated[operation.paragraph_index] = replace(paragraph, runs=runs)
    return updated


def _validate_element_value(field_name: str, value) -> None:
    """시각 patch 값의 기본 타입과 허용 집합을 검증한다."""
    numeric = (
        _GEOMETRY_FIELDS
        | _PADDING_FIELDS
        | {
            "line_spacing_pt",
            "text_size_pt",
        }
    )
    if (
        field_name in numeric
        and value is not None
        and (isinstance(value, bool) or not isinstance(value, (int, float)))
    ):
        raise ValueError(f"{field_name} patch value must be numeric or null")
    if (
        field_name == "z_index"
        and value is not None
        and (isinstance(value, bool) or not isinstance(value, int))
    ):
        raise ValueError("z_index patch value must be an integer or null")
    if field_name == "vertical_alignment" and value not in {"top", "middle", "bottom"}:
        raise ValueError("vertical_alignment patch value is invalid")
    if field_name == "autofit" and value not in {"shrink", "none", "resize"}:
        raise ValueError("autofit patch value is invalid")
    if field_name == "autofit_mode" and value not in {"expand_height", "shrink_text"}:
        raise ValueError("autofit_mode patch value is invalid")
    if field_name in _COLOR_FIELDS and value is not None and not isinstance(value, str):
        raise ValueError(f"{field_name} patch value must be a string or null")


def _apply_visual_patch(
    current_spec: PptxSlideSpec,
    operations: list[VisualQAPatchOperation],
    issues: list[dict],
) -> PptxSlideSpec:
    """모든 operation을 검증한 뒤 새 spec에 원자적으로 적용한다."""
    field_permissions, run_permissions, issue_types = _issue_permissions(issues)
    spec = current_spec
    for operation in operations:
        if operation.element_type == "slide":
            if "contrast" not in issue_types:
                raise ValueError("background_color requires a contrast issue")
            if operation.value is not None and not isinstance(operation.value, str):
                raise ValueError("background_color must be a string or null")
            spec = replace(spec, background_color=operation.value)
            continue

        collection = (
            list(spec.textboxes)
            if operation.element_type == "textbox"
            else list(spec.shapes)
        )
        if operation.element_index >= len(collection):
            raise ValueError("element_index is out of range")
        element = collection[operation.element_index]
        key = (operation.element_type, operation.element_index)

        if operation.field in {"font_size_pt", "color"}:
            if operation.field not in run_permissions.get(key, set()):
                raise ValueError("run field is outside detected issue permissions")
            paragraphs = _replace_run(element.paragraphs, operation)
            collection[operation.element_index] = replace(
                element, paragraphs=paragraphs
            )
        else:
            if operation.field not in field_permissions.get(key, set()):
                raise ValueError("element field is outside detected issue permissions")
            if not hasattr(element, operation.field):
                raise ValueError(
                    f"{operation.element_type} does not support {operation.field}"
                )
            _validate_element_value(operation.field, operation.value)
            collection[operation.element_index] = replace(
                element, **{operation.field: operation.value}
            )

        if operation.element_type == "textbox":
            spec = replace(spec, textboxes=collection)
        else:
            spec = replace(spec, shapes=collection)
    return derive_spec_layout_bboxes(spec)


def _grant_issue_permission(
    permissions: dict[tuple[str, int], set[str]],
    element_type,
    element_index,
    allowed: set[str],
) -> None:
    if element_type not in {"textbox", "shape"} or not isinstance(element_index, int):
        return
    permissions.setdefault((element_type, element_index), set()).update(allowed)
