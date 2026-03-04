"""PptxSlideSpec 검증 및 보정 유틸리티.

LLM 출력 PptxSlideSpec의 경계/폰트/텍스트 오버플로우를 검증·보정한다.
레이아웃 위치 조정은 수행하지 않는다 — 프롬프트와 예제로 가이드한다.
"""

from __future__ import annotations

from dataclasses import replace

from ppt_generator.interfaces.constants import (
    PPTX_VALIDATE_FONT_MAX_PT,
    PPTX_VALIDATE_FONT_MIN_PT,
    PPTX_VALIDATE_LINE_HEIGHT_FACTOR,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
    SPEC_VALIDATE_MARGIN_BOTTOM_PX,
    SPEC_VALIDATE_MARGIN_PX,
    SPEC_VALIDATE_MIN_GAP_PX,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX,
)
from ppt_generator.interfaces.spec_utils.contrast_utils import ensure_text_contrast
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
    *,
    autofit: bool = True,
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

        pad_l = tb.padding_left_px or 0.0
        pad_r = tb.padding_right_px or 0.0
        pad_t = tb.padding_top_px or 0.0
        pad_b = tb.padding_bottom_px or 0.0

        if autofit:
            required_h = calculate_required_height(
                new_paragraphs, width, tb.line_spacing_pt,
                padding_left_px=pad_l, padding_right_px=pad_r,
                padding_top_px=pad_t, padding_bottom_px=pad_b,
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
            padding_left_px=tb.padding_left_px,
            padding_right_px=tb.padding_right_px,
            padding_top_px=tb.padding_top_px,
            padding_bottom_px=tb.padding_bottom_px,
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
    *,
    autofit: bool = True,
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

        if autofit:
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
# 대비 보정
# ---------------------------------------------------------------------------


def _fix_run_contrast(run: PptxTextRun, bg_color: str) -> PptxTextRun:
    """단일 run의 텍스트 색상 대비를 보정한다."""
    if not run.color:
        return run
    fixed = ensure_text_contrast(
        run.color, bg_color,
        font_size_pt=run.font_size_pt or 16,
        bold=run.bold,
    )
    if fixed != run.color:
        return replace(run, color=fixed)
    return run


def _fix_textbox_contrast(
    textboxes: list[PptxTextBox],
    bg_color: str,
) -> list[PptxTextBox]:
    """모든 textbox의 텍스트 색상 대비를 보정한다."""
    result: list[PptxTextBox] = []
    for tb in textboxes:
        new_paragraphs: list[PptxParagraph] = []
        changed = False
        for para in tb.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                fixed = _fix_run_contrast(run, bg_color)
                if fixed is not run:
                    changed = True
                new_runs.append(fixed)
            new_paragraphs.append(replace(para, runs=new_runs))
        if changed:
            result.append(replace(tb, paragraphs=new_paragraphs))
        else:
            result.append(tb)
    return result


def _fix_shape_contrast(
    shapes: list[PptxShape],
    slide_bg_color: str,
) -> list[PptxShape]:
    """모든 shape의 텍스트 색상 대비를 보정한다.

    shape에 fill_color가 있으면 그것을 배경으로, 없으면 slide 배경색을 사용한다.
    """
    result: list[PptxShape] = []
    for s in shapes:
        bg = s.fill_color or slide_bg_color
        changed = False

        # text_color 보정
        new_text_color = s.text_color
        if s.text_color and s.text:
            fixed = ensure_text_contrast(
                s.text_color, bg,
                font_size_pt=s.text_size_pt or 16,
                bold=s.text_bold,
            )
            if fixed != s.text_color:
                new_text_color = fixed
                changed = True

        # paragraphs 내 run color 보정
        new_paragraphs: list[PptxParagraph] = []
        for para in s.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                fixed_run = _fix_run_contrast(run, bg)
                if fixed_run is not run:
                    changed = True
                new_runs.append(fixed_run)
            new_paragraphs.append(replace(para, runs=new_runs))

        if changed:
            result.append(replace(s, text_color=new_text_color, paragraphs=new_paragraphs))
        else:
            result.append(s)
    return result


# ---------------------------------------------------------------------------
# 최소 간격 보정
# ---------------------------------------------------------------------------


def _has_text(s: PptxShape) -> bool:
    """shape에 텍스트가 있는지 판별한다."""
    if s.text:
        return True
    return any(
        run.text.strip()
        for para in s.paragraphs
        for run in para.runs
    )


def _fix_zero_gap(
    shapes: list[PptxShape],
    min_gap: int = SPEC_VALIDATE_MIN_GAP_PX,
) -> list[PptxShape]:
    """텍스트 있는 shape 간 최소 간격을 확보한다.

    수평/수직 겹침 영역이 있는 인접 shape 쌍의 간격이 min_gap 미만이면 균등하게 벌린다.
    """
    if len(shapes) < 2:
        return shapes

    # 텍스트가 있는 shape 인덱스만 추출
    text_indices = [i for i, s in enumerate(shapes) if _has_text(s)]
    if len(text_indices) < 2:
        return shapes

    # mutable copy
    result = list(shapes)
    adjusted: dict[int, PptxShape] = {}

    for idx_a in range(len(text_indices)):
        for idx_b in range(idx_a + 1, len(text_indices)):
            i = text_indices[idx_a]
            j = text_indices[idx_b]
            a = adjusted.get(i, result[i])
            b = adjusted.get(j, result[j])

            # 수평 겹침 여부 (두 shape의 x 범위가 겹쳐야 수직 간격이 의미 있음)
            a_right = a.left_px + a.width_px
            b_right = b.left_px + b.width_px
            h_overlap = min(a_right, b_right) - max(a.left_px, b.left_px)

            # 수직 겹침 여부 (두 shape의 y 범위가 겹쳐야 수평 간격이 의미 있음)
            a_bottom = a.top_px + a.height_px
            b_bottom = b.top_px + b.height_px
            v_overlap = min(a_bottom, b_bottom) - max(a.top_px, b.top_px)

            if h_overlap > 0:
                # 수직 간격 검사
                v_gap = max(a.top_px, b.top_px) - min(a_bottom, b_bottom)
                if 0 <= v_gap < min_gap:
                    fix = (min_gap - v_gap) / 2.0
                    if a.top_px <= b.top_px:
                        adjusted[i] = replace(a, top_px=a.top_px - fix)
                        adjusted[j] = replace(b, top_px=b.top_px + fix)
                    else:
                        adjusted[i] = replace(a, top_px=a.top_px + fix)
                        adjusted[j] = replace(b, top_px=b.top_px - fix)

            if v_overlap > 0:
                # 수평 간격 검사
                h_gap = max(a.left_px, b.left_px) - min(a_right, b_right)
                if 0 <= h_gap < min_gap:
                    fix = (min_gap - h_gap) / 2.0
                    a = adjusted.get(i, result[i])
                    b = adjusted.get(j, result[j])
                    if a.left_px <= b.left_px:
                        adjusted[i] = replace(a, left_px=a.left_px - fix)
                        adjusted[j] = replace(b, left_px=b.left_px + fix)
                    else:
                        adjusted[i] = replace(a, left_px=a.left_px + fix)
                        adjusted[j] = replace(b, left_px=b.left_px - fix)

    for idx, shape in adjusted.items():
        result[idx] = shape
    return result


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def validate_slide_spec(spec: PptxSlideSpec, *, autofit: bool = True) -> PptxSlideSpec:
    """LLM 출력 PptxSlideSpec을 검증하고 보정한다.

    수행하는 보정:
    - 폰트 크기 클램핑 (10~44pt)
    - 경계 여백 강제 (캔버스 밖 방지)
    - 빈 텍스트박스 제거
    - 텍스트 오버플로우 방지 (autofit)
    - 텍스트-배경 색상 대비 보정 (WCAG AA)
    - 텍스트 shape 간 최소 간격 확보

    수행하지 않는 보정 (프롬프트로 가이드):
    - 제목/메인 텍스트 위치 고정
    - 수직 중앙 정렬
    - 겹침 해소를 위한 요소 밀어내기
    """
    validated_textboxes = _validate_textboxes(spec.textboxes, autofit=autofit)
    validated_shapes = _validate_shapes(spec.shapes, autofit=autofit)

    # 대비 보정
    bg_color = spec.background_color or "#FFFFFF"
    validated_textboxes = _fix_textbox_contrast(validated_textboxes, bg_color)
    validated_shapes = _fix_shape_contrast(validated_shapes, bg_color)

    # 최소 간격 보정
    validated_shapes = _fix_zero_gap(validated_shapes)

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=validated_textboxes,
        shapes=validated_shapes,
        images=spec.images,
        speaker_notes=spec.speaker_notes,
        slide_type=spec.slide_type,
    )
