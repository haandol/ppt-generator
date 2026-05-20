"""PptxSlideSpec 디자인 lint — 위반 감지 + 기계적 정리.

강제 수정(보정)은 하지 않는다. 디자인 규칙 위반을 감지하여 리포트하고,
기계적 정리(빈 textbox 제거)만 spec에 적용한다.

규칙 구현은 lint_rules/ 패키지에 규칙별 파일로 분리되어 있다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec, PptxTextBox
from ppt_generator.interfaces.spec_utils.lint_rules import ALL_RULES
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintResult,
    LintViolation,
    SlideLintResult,
)


def lint_slide_spec(spec: PptxSlideSpec, slide_index: int = 1) -> SlideLintResult:
    """단일 슬라이드를 lint한다. 위반을 감지하되 수정하지 않는다."""
    result = SlideLintResult(slide_index=slide_index)
    for rule in ALL_RULES:
        rule(spec, result)
    return result


def lint_design_spec(specs: list[PptxSlideSpec]) -> LintResult:
    """전체 슬라이드에 대해 lint를 실행한다.

    Returns:
        LintResult: 슬라이드별 위반 리포트 + 기계적 정리가 적용된 spec 리스트
    """
    result = LintResult()
    for idx, spec in enumerate(specs):
        slide_result = lint_slide_spec(spec, slide_index=idx + 1)
        result.slides.append(slide_result)
        result.cleaned_specs.append(_clean_spec(spec))
    return result


def clean_slide_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """기계적 정리만 적용한다 (빈 textbox 제거). 디자인 변경 없음."""
    return _clean_spec(spec)


def _clean_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """빈 텍스트박스를 제거한다."""
    cleaned_tbs: list[PptxTextBox] = []
    for tb in spec.textboxes:
        has_text = any(run.text.strip() for para in tb.paragraphs for run in para.runs)
        if has_text:
            cleaned_tbs.append(tb)

    return PptxSlideSpec(
        background_color=spec.background_color,
        background_image_bytes=spec.background_image_bytes,
        background_image_src=spec.background_image_src,
        textboxes=cleaned_tbs,
        shapes=spec.shapes,
        images=spec.images,
        speaker_notes=spec.speaker_notes,
        slide_type=spec.slide_type,
        grid_plan=spec.grid_plan,
    )
