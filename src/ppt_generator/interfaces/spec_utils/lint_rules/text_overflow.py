"""text-overflow: 텍스트가 컨테이너(textbox/shape) 높이 또는 폭을 초과하는지 검사."""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)
from ppt_generator.interfaces.text_measurement import (
    calculate_required_height,
    calculate_required_height_simple_text,
    estimate_text_width_px,
    required_height_after_shrink,
)

_TEXT_OVERFLOW_TOLERANCE = 1.15  # 15% 여유 허용 (폰트 메트릭 추정 오차 흡수)


def check_text_overflow(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    _check_textboxes(spec, result)
    _check_shapes(spec, result)
    _check_shapes_width_overflow(spec, result)


def _check_textboxes(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, tb in enumerate(spec.textboxes):
        has_text = any(run.text.strip() for para in tb.paragraphs for run in para.runs)
        if not has_text:
            continue

        text_paras = [p for p in tb.paragraphs if any(r.text.strip() for r in p.runs)]
        if len(text_paras) <= 1:
            total_runs_text = "".join(r.text for p in text_paras for r in p.runs)
            if "\n" not in total_runs_text:
                continue

        required_h = calculate_required_height(
            tb.paragraphs,
            tb.width_px,
            line_spacing_pt=tb.line_spacing_pt,
            padding_left_px=tb.padding_left_px or 0.0,
            padding_right_px=tb.padding_right_px or 0.0,
            padding_top_px=tb.padding_top_px or 0.0,
            padding_bottom_px=tb.padding_bottom_px or 0.0,
        )
        available_h = tb.height_px * _TEXT_OVERFLOW_TOLERANCE
        if required_h > available_h:
            result.violations.append(
                LintViolation(
                    rule="text-overflow",
                    severity="warning",
                    message=(
                        f"textbox 텍스트가 높이를 초과함 "
                        f"(필요 {required_h:.0f}px > 가용 {tb.height_px:.0f}px)"
                    ),
                    element_index=idx,
                    element_type="textbox",
                    current_value={
                        "required_height": round(required_h),
                        "available_height": round(tb.height_px),
                    },
                    expected=f"<= {tb.height_px:.0f}px",
                )
            )


def _check_shapes(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for idx, shape in enumerate(spec.shapes):
        if is_decorative(shape):
            continue

        has_paragraphs = any(
            run.text.strip() for para in shape.paragraphs for run in para.runs
        )
        has_simple_text = bool(shape.text and shape.text.strip())

        if not has_paragraphs and not has_simple_text:
            continue

        pad_l = shape.padding_left_px or 0.0
        pad_r = shape.padding_right_px or 0.0
        pad_t = shape.padding_top_px or 0.0
        pad_b = shape.padding_bottom_px or 0.0
        shape_h = abs(shape.height_px)

        # autofit_mode="shrink_text" 인 shape 는 폰트가 자동 축소되지만, 축소 하한
        # (절대 10pt) 에 걸리면 축소해도 여전히 박스를 넘을 수 있다. PPTX 는 도형
        # 클리핑이 없어 그 잔여 넘침이 박스 밖으로 삐져나오므로, "축소 후에도 남는"
        # 넘침을 검사한다 (paragraphs 경로만 — simple text 는 shrink 대상 아님).
        if shape.autofit_mode == "shrink_text" and has_paragraphs:
            residual_h = required_height_after_shrink(
                shape.paragraphs,
                abs(shape.width_px),
                shape_h,
                line_spacing_pt=shape.line_spacing_pt,
                padding_left_px=pad_l,
                padding_right_px=pad_r,
                padding_top_px=pad_t,
                padding_bottom_px=pad_b,
            )
            if residual_h > shape_h * _TEXT_OVERFLOW_TOLERANCE:
                result.violations.append(
                    LintViolation(
                        rule="text-overflow",
                        severity="warning",
                        message=(
                            f"shape 텍스트가 폰트 최소 축소(10pt) 후에도 높이를 "
                            f"초과함 (필요 {residual_h:.0f}px > 가용 {shape_h:.0f}px). "
                            f"텍스트를 줄이거나 박스를 키워야 합니다."
                        ),
                        element_index=idx,
                        element_type="shape",
                        current_value={
                            "required_height": round(residual_h),
                            "available_height": round(shape_h),
                        },
                        expected=f"<= {shape_h:.0f}px",
                    )
                )
            continue

        if has_paragraphs:
            required_h = calculate_required_height(
                shape.paragraphs,
                abs(shape.width_px),
                line_spacing_pt=shape.line_spacing_pt,
                padding_left_px=pad_l,
                padding_right_px=pad_r,
                padding_top_px=pad_t,
                padding_bottom_px=pad_b,
            )
        else:
            font_pt = shape.text_size_pt or 16
            required_h = calculate_required_height_simple_text(
                shape.text,
                font_pt,
                abs(shape.width_px),
                line_spacing_pt=shape.line_spacing_pt,
                padding_left_px=pad_l,
                padding_right_px=pad_r,
                padding_top_px=pad_t,
                padding_bottom_px=pad_b,
            )

        available_h = shape_h * _TEXT_OVERFLOW_TOLERANCE
        if required_h > available_h:
            result.violations.append(
                LintViolation(
                    rule="text-overflow",
                    severity="warning",
                    message=(
                        f"shape 텍스트가 높이를 초과함 "
                        f"(필요 {required_h:.0f}px > 가용 {shape_h:.0f}px)"
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={
                        "required_height": round(required_h),
                        "available_height": round(shape_h),
                    },
                    expected=f"<= {shape_h:.0f}px",
                )
            )


def _check_shapes_width_overflow(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    """shape 내 단일 단어가 가용 폭을 초과하는지 검사한다."""
    for idx, shape in enumerate(spec.shapes):
        if is_decorative(shape):
            continue
        if not shape.paragraphs:
            continue

        pad_l = shape.padding_left_px or 0.0
        pad_r = shape.padding_right_px or 0.0
        available_w = abs(shape.width_px) - pad_l - pad_r
        if available_w <= 0:
            continue

        found = False
        for para in shape.paragraphs:
            if found:
                break
            for run in para.runs:
                if found:
                    break
                if not run.text or not run.text.strip():
                    continue
                font_pt = run.font_size_pt or 16
                is_mono = run.font_family == "monospace"
                for word in run.text.split():
                    word_w = estimate_text_width_px(word, font_pt, is_mono)
                    if word_w > available_w * _TEXT_OVERFLOW_TOLERANCE:
                        result.violations.append(
                            LintViolation(
                                rule="text-width-overflow",
                                severity="warning",
                                message=(
                                    f"shape 내 텍스트 '{word}'가 가용 폭을 초과함 "
                                    f"(단어 {word_w:.0f}px > 가용 {available_w:.0f}px)"
                                ),
                                element_index=idx,
                                element_type="shape",
                                current_value={
                                    "word": word,
                                    "word_width": round(word_w),
                                    "available_width": round(available_w),
                                },
                                expected=f"<= {available_w:.0f}px",
                            )
                        )
                        found = True
                        break
