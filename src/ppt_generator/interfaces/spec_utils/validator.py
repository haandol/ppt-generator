"""PptxSlideSpec 검증 및 보정 유틸리티.

LLM 출력 PptxSlideSpec의 경계/폰트/텍스트 오버플로우를 검증·보정한다.
레이아웃 위치 조정은 수행하지 않는다 — 프롬프트와 예제로 가이드한다.
"""

from __future__ import annotations

from dataclasses import replace

from ppt_generator.interfaces.constants import (
    CARD_BODY_FONT_MIN_PT,
    CARD_TITLE_FONT_MIN_PT,
    PPTX_VALIDATE_FONT_MAX_PT,
    PPTX_VALIDATE_FONT_MIN_PT,
    PPTX_VALIDATE_LINE_HEIGHT_FACTOR,
    SECTION_LABEL_FONT_MIN_PT,
    SLIDE_TITLE_FONT_MIN_PT,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
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
_CARD_TITLE_MIN = CARD_TITLE_FONT_MIN_PT
_CARD_BODY_MIN = CARD_BODY_FONT_MIN_PT
_SECTION_LABEL_MIN = SECTION_LABEL_FONT_MIN_PT
_SLIDE_TITLE_MIN = SLIDE_TITLE_FONT_MIN_PT


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


def _clamp_font(
    pt: int | None, font_min: int = _FONT_MIN, font_max: int = _FONT_MAX
) -> int | None:
    if pt is None:
        return None
    return max(font_min, min(font_max, pt))


def _clip_rect(
    left: float,
    top: float,
    width: float,
    height: float,
    canvas_w: float = _CANVAS_W,
    canvas_h: float = _CANVAS_H,
    margin: int = _MARGIN,
    margin_bottom: int = _MARGIN_BOTTOM,
    *,
    is_decorative: bool = False,
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


def _scale_line_spacing(
    line_spacing_pt: float | None,
    scale: float,
) -> float | None:
    """line_spacing_pt를 scale에 맞게 축소한다."""
    if line_spacing_pt is None or scale >= 1.0:
        return line_spacing_pt
    return round(line_spacing_pt * scale, 1)


def _is_card_shape(s: PptxShape) -> bool:
    """fill_color가 있고 line이 아닌 shape → 카드로 판별."""
    return bool(s.fill_color) and s.shape_type != "line"


def _is_slide_title(tb: PptxTextBox, is_first: bool) -> bool:
    """슬라이드 제목 textbox 판별: 첫 번째 textbox, top ~64~100, 단일 paragraph, bold."""
    if not is_first:
        return False
    if not (64 <= tb.top_px <= 100):
        return False
    if len(tb.paragraphs) != 1:
        return False
    para = tb.paragraphs[0]
    return any(run.bold for run in para.runs)


def _is_section_label(tb: PptxTextBox) -> bool:
    """단일 paragraph, 총 20자 미만 textbox → 섹션 레이블로 판별."""
    if len(tb.paragraphs) != 1:
        return False
    para = tb.paragraphs[0]
    total_chars = sum(len(run.text) for run in para.runs)
    return total_chars < 20


def _clamp_card_paragraphs(
    paragraphs: list[PptxParagraph],
    font_max: int = _FONT_MAX,
) -> tuple[list[PptxParagraph], int]:
    """Card shape용: 첫 번째 볼드 런은 18pt, 나머지는 16pt로 클램핑.

    Returns:
        (clamped_paragraphs, shape_max_font)
    """
    result: list[PptxParagraph] = []
    shape_max_font = _CARD_BODY_MIN
    found_title = False

    for para in paragraphs:
        new_runs: list[PptxTextRun] = []
        for run in para.runs:
            if not found_title and run.bold:
                floor = _CARD_TITLE_MIN
                found_title = True
            else:
                floor = _CARD_BODY_MIN
            clamped = _clamp_font(run.font_size_pt, floor, font_max)
            new_runs.append(replace(run, font_size_pt=clamped))
            if clamped and clamped > shape_max_font:
                shape_max_font = clamped
        result.append(replace(para, runs=new_runs))

    return result, shape_max_font


def _apply_font_scale_card(
    paragraphs: list[PptxParagraph],
    scale: float,
) -> list[PptxParagraph]:
    """Card shape용 font scale 적용. 카드 제목은 18pt, 바디는 16pt 바닥."""
    if scale >= 1.0:
        return paragraphs

    result: list[PptxParagraph] = []
    found_title = False

    for para in paragraphs:
        new_runs: list[PptxTextRun] = []
        for run in para.runs:
            if not found_title and run.bold:
                floor = _CARD_TITLE_MIN
                found_title = True
            else:
                floor = _CARD_BODY_MIN
            if run.font_size_pt:
                scaled = max(floor, int(run.font_size_pt * scale))
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
    *,
    autofit: bool = True,
) -> list[PptxTextBox]:
    validated: list[PptxTextBox] = []
    found_first_text_tb = False
    for tb in textboxes:
        has_text = any(run.text.strip() for para in tb.paragraphs for run in para.runs)
        if not has_text:
            continue

        is_first = not found_first_text_tb
        found_first_text_tb = True

        if _is_slide_title(tb, is_first):
            tb_font_min = _SLIDE_TITLE_MIN
        elif _is_section_label(tb):
            tb_font_min = _SECTION_LABEL_MIN
        else:
            tb_font_min = font_min

        new_paragraphs: list[PptxParagraph] = []
        max_font_in_tb = tb_font_min
        for para in tb.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                clamped_size = _clamp_font(run.font_size_pt, tb_font_min, font_max)
                new_runs.append(replace(run, font_size_pt=clamped_size))
                if clamped_size and clamped_size > max_font_in_tb:
                    max_font_in_tb = clamped_size
            new_paragraphs.append(replace(para, runs=new_runs))

        left, top, width, height = _clip_rect(
            tb.left_px,
            tb.top_px,
            tb.width_px,
            tb.height_px,
            canvas_w,
            canvas_h,
            margin,
        )

        pad_l = tb.padding_left_px or 0.0
        pad_r = tb.padding_right_px or 0.0
        pad_t = tb.padding_top_px or 0.0
        pad_b = tb.padding_bottom_px or 0.0

        new_line_spacing = tb.line_spacing_pt
        if autofit:
            required_h = calculate_required_height(
                new_paragraphs,
                width,
                tb.line_spacing_pt,
                padding_left_px=pad_l,
                padding_right_px=pad_r,
                padding_top_px=pad_t,
                padding_bottom_px=pad_b,
            )

            if required_h > 0 and height < required_h:
                scale = calculate_autofit_font_scale(
                    required_h,
                    height,
                    tb_font_min,
                    max_font_in_tb,
                )
                new_paragraphs = _apply_font_scale(new_paragraphs, scale, tb_font_min)
                new_line_spacing = _scale_line_spacing(tb.line_spacing_pt, scale)

        validated.append(
            PptxTextBox(
                left_px=left,
                top_px=top,
                width_px=width,
                height_px=height,
                paragraphs=new_paragraphs,
                line_spacing_pt=new_line_spacing,
                vertical_alignment=tb.vertical_alignment,
                padding_left_px=tb.padding_left_px,
                padding_right_px=tb.padding_right_px,
                padding_top_px=tb.padding_top_px,
                padding_bottom_px=tb.padding_bottom_px,
                z_index=tb.z_index,
            )
        )
    return validated


# ---------------------------------------------------------------------------
# 도형 검증
# ---------------------------------------------------------------------------


def _is_decorative_shape(s: PptxShape) -> bool:
    """텍스트 없는 얇은 shape(수평/수직 꾸밈 라인 등)을 장식 요소로 판별."""
    if s.text or s.paragraphs:
        return False
    return abs(s.height_px) <= 10 or s.width_px <= 10


def _validate_shapes(
    shapes: list[PptxShape],
    canvas_w: float = _CANVAS_W,
    canvas_h: float = _CANVAS_H,
    font_min: int = _FONT_MIN,
    font_max: int = _FONT_MAX,
    lh_factor: float = _LH_FACTOR,
    margin: int = _MARGIN,
    *,
    autofit: bool = True,
) -> list[PptxShape]:
    validated: list[PptxShape] = []
    for s in shapes:
        is_decorative = _is_decorative_shape(s)
        # line shape는 음수 height(대각선 방향)를 가질 수 있으므로 abs로 clip 후 부호 복원
        h_sign = -1 if (s.shape_type == "line" and s.height_px < 0) else 1
        left, top, width, height = _clip_rect(
            s.left_px,
            s.top_px,
            s.width_px,
            abs(s.height_px) if h_sign < 0 else s.height_px,
            canvas_w,
            canvas_h,
            margin,
            is_decorative=is_decorative,
        )
        height = height * h_sign
        is_card = _is_card_shape(s)
        shape_font_min = _CARD_BODY_MIN if is_card else font_min

        clamped_text_size = _clamp_font(
            s.text_size_pt,
            _CARD_TITLE_MIN if (is_card and s.text_bold) else shape_font_min,
            font_max,
        )

        if is_card and s.paragraphs:
            new_shape_paragraphs, shape_max_font = _clamp_card_paragraphs(
                s.paragraphs, font_max
            )
        else:
            new_shape_paragraphs = []
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

        pad_l = (
            s.padding_left_px
            if s.padding_left_px is not None
            else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX
        )
        pad_r = (
            s.padding_right_px
            if s.padding_right_px is not None
            else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX
        )
        pad_t = (
            s.padding_top_px
            if s.padding_top_px is not None
            else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX
        )
        pad_b = (
            s.padding_bottom_px
            if s.padding_bottom_px is not None
            else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX
        )

        new_line_spacing = s.line_spacing_pt
        if autofit:
            required_h = 0.0

            if s.text and clamped_text_size:
                required_h = calculate_required_height_simple_text(
                    s.text,
                    clamped_text_size,
                    width,
                    line_spacing_pt=s.line_spacing_pt,
                    padding_left_px=pad_l,
                    padding_right_px=pad_r,
                    padding_top_px=pad_t,
                    padding_bottom_px=pad_b,
                )

            if new_shape_paragraphs:
                para_h = calculate_required_height(
                    new_shape_paragraphs,
                    width,
                    s.line_spacing_pt,
                    padding_left_px=pad_l,
                    padding_right_px=pad_r,
                    padding_top_px=pad_t,
                    padding_bottom_px=pad_b,
                )
                required_h = max(required_h, para_h)

            if required_h > 0 and height < required_h:
                if s.autofit_mode == "shrink_text":
                    # shrink_text: height를 유지하고 폰트+줄간격 축소
                    effective_max_font = max(
                        shape_max_font, clamped_text_size or shape_font_min
                    )
                    scale = calculate_autofit_font_scale(
                        required_h,
                        height,
                        shape_font_min,
                        effective_max_font,
                    )
                    if new_shape_paragraphs:
                        if is_card:
                            new_shape_paragraphs = _apply_font_scale_card(
                                new_shape_paragraphs, scale
                            )
                        else:
                            new_shape_paragraphs = _apply_font_scale(
                                new_shape_paragraphs, scale, font_min
                            )
                    if clamped_text_size and scale < 1.0:
                        text_floor = (
                            _CARD_TITLE_MIN
                            if (is_card and s.text_bold)
                            else shape_font_min
                        )
                        clamped_text_size = max(
                            text_floor, int(clamped_text_size * scale)
                        )
                    new_line_spacing = _scale_line_spacing(s.line_spacing_pt, scale)
                else:
                    # expand_height (기본값): height를 확장한 후, 여전히 부족하면 폰트+줄간격 축소
                    height = min(required_h, max_bottom - top)

                    if required_h > 0 and height < required_h:
                        scale = calculate_autofit_font_scale(
                            required_h,
                            height,
                            shape_font_min,
                            shape_max_font,
                        )
                        if new_shape_paragraphs:
                            if is_card:
                                new_shape_paragraphs = _apply_font_scale_card(
                                    new_shape_paragraphs, scale
                                )
                            else:
                                new_shape_paragraphs = _apply_font_scale(
                                    new_shape_paragraphs, scale, font_min
                                )
                        if clamped_text_size and scale < 1.0:
                            text_floor = (
                                _CARD_TITLE_MIN
                                if (is_card and s.text_bold)
                                else shape_font_min
                            )
                            clamped_text_size = max(
                                text_floor, int(clamped_text_size * scale)
                            )
                        new_line_spacing = _scale_line_spacing(s.line_spacing_pt, scale)

        validated.append(
            replace(
                s,
                left_px=left,
                top_px=top,
                width_px=width,
                height_px=height,
                text_size_pt=clamped_text_size,
                paragraphs=new_shape_paragraphs,
                line_spacing_pt=new_line_spacing,
            )
        )
    return validated


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def validate_slide_spec(
    spec: PptxSlideSpec,
    *,
    autofit: bool = True,
) -> PptxSlideSpec:
    """LLM 출력 PptxSlideSpec을 검증하고 보정한다.

    수행하는 보정:
    - 폰트 크기 클램핑 (10~44pt, 카드: title 18pt/body 16pt, 섹션 레이블: 14pt)
    - 경계 여백 강제 (캔버스 밖 방지)
    - 빈 텍스트박스 제거
    - 텍스트 오버플로우 방지 (autofit — 카드는 16/18pt 이하로 축소 불가)

    수행하지 않는 보정 (프롬프트로 가이드):
    - 제목/메인 텍스트 위치 고정
    - 수직 중앙 정렬
    - 겹침 해소를 위한 요소 밀어내기
    - 텍스트-배경 색상 대비
    - 텍스트 shape 간 최소 간격
    """
    validated_textboxes = _validate_textboxes(spec.textboxes, autofit=autofit)
    validated_shapes = _validate_shapes(spec.shapes, autofit=autofit)

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=validated_textboxes,
        shapes=validated_shapes,
        images=spec.images,
        speaker_notes=spec.speaker_notes,
        slide_type=spec.slide_type,
    )
