"""PptxSlideSpec 검증 및 보정 유틸리티.

LLM 출력 PptxSlideSpec의 경계/폰트/제목 위치/수직 정렬을 검증·보정한다.
"""

from __future__ import annotations

from dataclasses import replace

from ppt_generator.interfaces.constants import (
    PPTX_VALIDATE_FONT_MAX_PT,
    PPTX_VALIDATE_FONT_MIN_PT,
    PPTX_VALIDATE_LINE_HEIGHT_FACTOR,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
    SPEC_VALIDATE_CONTENT_CENTER_THRESHOLD,
    SPEC_VALIDATE_MARGIN_BOTTOM_PX,
    SPEC_VALIDATE_MARGIN_PX,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX,
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.text_measurement import (
    calculate_autofit_font_scale,
    calculate_required_height,
    calculate_required_height_simple_text,
)


# ---------------------------------------------------------------------------
# 모듈 상수
# ---------------------------------------------------------------------------

_CANVAS_W = SLIDES_WIDTH_PX
_CANVAS_H = SLIDES_HEIGHT_PX
_FONT_MIN = PPTX_VALIDATE_FONT_MIN_PT
_FONT_MAX = PPTX_VALIDATE_FONT_MAX_PT
_LH_FACTOR = PPTX_VALIDATE_LINE_HEIGHT_FACTOR
_MARGIN = SPEC_VALIDATE_MARGIN_PX
_MARGIN_BOTTOM = SPEC_VALIDATE_MARGIN_BOTTOM_PX

# 콘텐츠 슬라이드 제목 위치 고정값
_CONTENT_TITLE_LEFT = 64
_CONTENT_TITLE_TOP = 72
_CONTENT_TITLE_WIDTH = 1152
_CONTENT_TITLE_HEIGHT = 48
_CONTENT_TITLE_MIN_FONT = 24

# 타이틀/클로징 슬라이드 메인 텍스트 위치 고정값
_TITLE_MAIN_LEFT = 64
_TITLE_MAIN_TOP = 260
_TITLE_MAIN_WIDTH = 1152
_TITLE_MAIN_HEIGHT = 80

_CLOSING_MAIN_LEFT = 64
_CLOSING_MAIN_TOP = 240
_CLOSING_MAIN_WIDTH = 1152
_CLOSING_MAIN_HEIGHT = 80



# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


def _clamp_font(pt: int | None, font_min: int = _FONT_MIN, font_max: int = _FONT_MAX) -> int | None:
    if pt is None:
        return None
    return max(font_min, min(font_max, pt))


def _clip_rect(
    left: float, top: float, width: float, height: float,
    canvas_w: float = _CANVAS_W, canvas_h: float = _CANVAS_H,
    margin: int = _MARGIN,
    margin_bottom: int = _MARGIN_BOTTOM,
    *, is_decorative: bool = False,
) -> tuple[float, float, float, float]:
    if is_decorative:
        left = max(0, min(left, canvas_w - 10))
        top = max(0, min(top, canvas_h - 10))
        width = max(10, min(width, canvas_w - left))
        height = max(10, min(height, canvas_h - top))
    else:
        left = max(margin, min(left, canvas_w - margin - 10))
        top = max(margin, min(top, canvas_h - margin_bottom - 10))
        max_right = canvas_w - margin
        width = max(10, min(width, max_right - left))
        max_bottom = canvas_h - margin_bottom
        height = max(10, min(height, max_bottom - top))
    return left, top, width, height


def _apply_font_scale(
    paragraphs: list[PptxParagraph],
    scale: float,
    font_min: int = _FONT_MIN,
) -> list[PptxParagraph]:
    if scale >= 1.0:
        return paragraphs
    result: list[PptxParagraph] = []
    for para in paragraphs:
        new_runs: list[PptxTextRun] = []
        for run in para.runs:
            if run.font_size_pt:
                scaled = max(font_min, int(run.font_size_pt * scale))
                new_runs.append(replace(run, font_size_pt=scaled))
            else:
                new_runs.append(run)
        result.append(replace(para, runs=new_runs))
    return result


# ---------------------------------------------------------------------------
# 텍스트박스 검증
# ---------------------------------------------------------------------------


def _validate_textboxes(
    textboxes: list[PptxTextBox],
    canvas_w: float = _CANVAS_W,
    canvas_h: float = _CANVAS_H,
    font_min: int = _FONT_MIN,
    font_max: int = _FONT_MAX,
    lh_factor: float = _LH_FACTOR,
    margin: int = _MARGIN,
) -> list[PptxTextBox]:
    validated: list[PptxTextBox] = []
    for tb in textboxes:
        has_text = any(
            run.text.strip()
            for para in tb.paragraphs
            for run in para.runs
        )
        if not has_text:
            continue

        new_paragraphs: list[PptxParagraph] = []
        max_font_in_tb = font_min
        for para in tb.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                clamped_size = _clamp_font(run.font_size_pt, font_min, font_max)
                new_runs.append(replace(run, font_size_pt=clamped_size))
                if clamped_size and clamped_size > max_font_in_tb:
                    max_font_in_tb = clamped_size
            new_paragraphs.append(replace(para, runs=new_runs))

        left, top, width, height = _clip_rect(
            tb.left_px, tb.top_px, tb.width_px, tb.height_px,
            canvas_w, canvas_h, margin,
        )

        required_h = calculate_required_height(
            new_paragraphs, width, tb.line_spacing_pt,
        )

        if required_h > 0 and height < required_h:
            scale = calculate_autofit_font_scale(
                required_h, height, font_min, max_font_in_tb,
            )
            new_paragraphs = _apply_font_scale(new_paragraphs, scale, font_min)

        validated.append(PptxTextBox(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            paragraphs=new_paragraphs,
            line_spacing_pt=tb.line_spacing_pt,
            vertical_alignment=tb.vertical_alignment,
        ))
    return validated


# ---------------------------------------------------------------------------
# 도형 검증
# ---------------------------------------------------------------------------


def _is_decorative_shape(s: PptxShape) -> bool:
    """텍스트 없는 얇은 shape(수평/수직 꾸밈 라인 등)을 장식 요소로 판별."""
    if s.text or s.paragraphs:
        return False
    return s.height_px <= 10 or s.width_px <= 10


def _validate_shapes(
    shapes: list[PptxShape],
    canvas_w: float = _CANVAS_W,
    canvas_h: float = _CANVAS_H,
    font_min: int = _FONT_MIN,
    font_max: int = _FONT_MAX,
    lh_factor: float = _LH_FACTOR,
    margin: int = _MARGIN,
) -> list[PptxShape]:
    validated: list[PptxShape] = []
    for s in shapes:
        is_decorative = _is_decorative_shape(s)
        left, top, width, height = _clip_rect(
            s.left_px, s.top_px, s.width_px, s.height_px,
            canvas_w, canvas_h, margin,
            is_decorative=is_decorative,
        )
        clamped_text_size = _clamp_font(s.text_size_pt, font_min, font_max)

        new_shape_paragraphs: list[PptxParagraph] = []
        shape_max_font = font_min
        for para in s.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                clamped = _clamp_font(run.font_size_pt, font_min, font_max)
                new_runs.append(replace(run, font_size_pt=clamped))
                if clamped and clamped > shape_max_font:
                    shape_max_font = clamped
            new_shape_paragraphs.append(replace(para, runs=new_runs))

        max_bottom = canvas_h if is_decorative else (canvas_h - _MARGIN_BOTTOM)

        pad_l = s.padding_left_px if s.padding_left_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX
        pad_r = s.padding_right_px if s.padding_right_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX
        pad_t = s.padding_top_px if s.padding_top_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX
        pad_b = s.padding_bottom_px if s.padding_bottom_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX

        required_h = 0.0

        if s.text and clamped_text_size:
            required_h = calculate_required_height_simple_text(
                s.text, clamped_text_size, width,
                line_spacing_pt=s.line_spacing_pt,
                padding_left_px=pad_l, padding_right_px=pad_r,
                padding_top_px=pad_t, padding_bottom_px=pad_b,
            )

        if new_shape_paragraphs:
            para_h = calculate_required_height(
                new_shape_paragraphs, width, s.line_spacing_pt,
                padding_left_px=pad_l, padding_right_px=pad_r,
                padding_top_px=pad_t, padding_bottom_px=pad_b,
            )
            required_h = max(required_h, para_h)

        if required_h > 0 and height < required_h:
            height = min(required_h, max_bottom - top)

        if required_h > 0 and height < required_h:
            scale = calculate_autofit_font_scale(
                required_h, height, font_min, shape_max_font,
            )
            if new_shape_paragraphs:
                new_shape_paragraphs = _apply_font_scale(
                    new_shape_paragraphs, scale, font_min,
                )
            if clamped_text_size and scale < 1.0:
                clamped_text_size = max(font_min, int(clamped_text_size * scale))

        validated.append(replace(
            s,
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            text_size_pt=clamped_text_size,
            paragraphs=new_shape_paragraphs,
        ))
    return validated


# ---------------------------------------------------------------------------
# 제목 위치 고정
# ---------------------------------------------------------------------------


def _fix_content_title_position(
    textboxes: list[PptxTextBox],
) -> list[PptxTextBox]:
    if not textboxes:
        return textboxes

    tb = textboxes[0]
    is_title = any(
        run.bold and run.font_size_pt and run.font_size_pt >= _CONTENT_TITLE_MIN_FONT
        for para in tb.paragraphs
        for run in para.runs
    )
    if not is_title:
        return textboxes

    fixed_tb = PptxTextBox(
        left_px=_CONTENT_TITLE_LEFT,
        top_px=_CONTENT_TITLE_TOP,
        width_px=_CONTENT_TITLE_WIDTH,
        height_px=_CONTENT_TITLE_HEIGHT,
        paragraphs=tb.paragraphs,
        line_spacing_pt=tb.line_spacing_pt,
        vertical_alignment=tb.vertical_alignment,
    )
    return [fixed_tb, *textboxes[1:]]


def _fix_title_closing_main_position(
    textboxes: list[PptxTextBox],
    slide_type: str,
) -> list[PptxTextBox]:
    """title/closing 슬라이드의 메인 텍스트박스 좌표를 프롬프트 명세에 맞게 고정한다.

    LLM이 content 슬라이드의 top=72를 title/closing에도 적용하는 경우를 보정.
    첫 번째 textbox만 고정 좌표로 설정하며, 나머지 요소는 건드리지 않는다.
    height는 검증 단계에서 확장된 값이 target_height보다 크면 그 값을 유지한다.
    """
    if not textboxes:
        return textboxes

    if slide_type == "title":
        target_left = _TITLE_MAIN_LEFT
        target_top = _TITLE_MAIN_TOP
        target_width = _TITLE_MAIN_WIDTH
        target_height = _TITLE_MAIN_HEIGHT
    elif slide_type == "closing":
        target_left = _CLOSING_MAIN_LEFT
        target_top = _CLOSING_MAIN_TOP
        target_width = _CLOSING_MAIN_WIDTH
        target_height = _CLOSING_MAIN_HEIGHT
    else:
        return textboxes

    tb = textboxes[0]
    # 이미 올바른 위치면 변경하지 않음
    if tb.top_px == target_top and tb.left_px == target_left:
        return textboxes

    # 검증 단계에서 텍스트 줄바꿈에 맞게 확장된 높이를 유지한다
    final_height = max(target_height, tb.height_px)

    fixed_tb = PptxTextBox(
        left_px=target_left,
        top_px=target_top,
        width_px=target_width,
        height_px=final_height,
        paragraphs=tb.paragraphs,
        line_spacing_pt=tb.line_spacing_pt,
        vertical_alignment=tb.vertical_alignment,
    )
    return [fixed_tb, *textboxes[1:]]



# ---------------------------------------------------------------------------
# 수직 중앙 정렬
# ---------------------------------------------------------------------------


def _center_content_vertically(
    textboxes: list[PptxTextBox],
    threshold: float = SPEC_VALIDATE_CONTENT_CENTER_THRESHOLD,
) -> list[PptxTextBox]:
    result: list[PptxTextBox] = []
    for tb in textboxes:
        if (
            tb.vertical_alignment == "top"
            and tb.top_px >= 100
            and tb.height_px >= 200
        ):
            content_h = calculate_required_height(
                tb.paragraphs, tb.width_px, tb.line_spacing_pt,
            )
            if content_h < tb.height_px * threshold:
                tb = PptxTextBox(
                    left_px=tb.left_px,
                    top_px=tb.top_px,
                    width_px=tb.width_px,
                    height_px=tb.height_px,
                    paragraphs=tb.paragraphs,
                    line_spacing_pt=tb.line_spacing_pt,
                    vertical_alignment="middle",
                )
        result.append(tb)
    return result


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def validate_slide_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """LLM 출력 PptxSlideSpec을 검증하고 보정한다."""
    validated_textboxes = _validate_textboxes(spec.textboxes)
    validated_shapes = _validate_shapes(spec.shapes)

    if spec.slide_type == "content":
        validated_textboxes = _fix_content_title_position(validated_textboxes)
    elif spec.slide_type in ("title", "closing"):
        validated_textboxes = _fix_title_closing_main_position(validated_textboxes, spec.slide_type)

    if spec.slide_type == "content":
        validated_textboxes = _center_content_vertically(validated_textboxes)

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=validated_textboxes,
        shapes=validated_shapes,
        images=spec.images,
        speaker_notes=spec.speaker_notes,
        slide_type=spec.slide_type,
    )
