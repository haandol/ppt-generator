"""PptxSlideSpec 파싱, 검증, 직렬화 공유 유틸리티.

llm_converter.py, dom_extractor.py, design service 등에서 공통으로 사용한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace

from ppt_generator.interfaces.constants import (
    PPTX_VALIDATE_FONT_MAX_PT,
    PPTX_VALIDATE_FONT_MIN_PT,
    PPTX_VALIDATE_LINE_HEIGHT_FACTOR,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX,
    TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
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
# parse_slide_spec: dict → PptxSlideSpec
# ---------------------------------------------------------------------------

def parse_slide_spec(data: dict) -> PptxSlideSpec:
    """JSON dict를 PptxSlideSpec dataclass로 변환."""
    textboxes: list[PptxTextBox] = []
    for tb in data.get("textboxes", []):
        paragraphs: list[PptxParagraph] = []
        for p in tb.get("paragraphs", []):
            runs: list[PptxTextRun] = []
            for r in p.get("runs", []):
                runs.append(PptxTextRun(
                    text=r.get("text", ""),
                    font_size_pt=r.get("font_size_pt"),
                    color=r.get("color"),
                    bold=r.get("bold", False),
                    italic=r.get("italic", False),
                    font_family=r.get("font_family"),
                ))
            paragraphs.append(PptxParagraph(
                runs=runs,
                bullet_level=p.get("bullet_level", -1),
                alignment=p.get("alignment"),
            ))
        textboxes.append(PptxTextBox(
            left_px=tb.get("left_px", 0),
            top_px=tb.get("top_px", 0),
            width_px=tb.get("width_px", 100),
            height_px=tb.get("height_px", 50),
            paragraphs=paragraphs,
            line_spacing_pt=tb.get("line_spacing_pt"),
            vertical_alignment=tb.get("vertical_alignment") or "top",
        ))

    shapes: list[PptxShape] = []
    for s in data.get("shapes", []):
        shape_paragraphs: list[PptxParagraph] = []
        for p in s.get("paragraphs", []):
            s_runs: list[PptxTextRun] = []
            for r in p.get("runs", []):
                s_runs.append(PptxTextRun(
                    text=r.get("text", ""),
                    font_size_pt=r.get("font_size_pt"),
                    color=r.get("color"),
                    bold=r.get("bold", False),
                    italic=r.get("italic", False),
                    font_family=r.get("font_family"),
                ))
            shape_paragraphs.append(PptxParagraph(
                runs=s_runs,
                bullet_level=p.get("bullet_level", -1),
                alignment=p.get("alignment"),
            ))
        shapes.append(PptxShape(
            left_px=s.get("left_px", 0),
            top_px=s.get("top_px", 0),
            width_px=s.get("width_px", 100),
            height_px=s.get("height_px", 50),
            shape_type=s.get("shape_type", "rectangle"),
            fill_color=s.get("fill_color"),
            border_color=s.get("border_color"),
            border_width_pt=s.get("border_width_pt"),
            corner_radius_px=s.get("corner_radius_px"),
            text=s.get("text"),
            text_color=s.get("text_color"),
            text_size_pt=s.get("text_size_pt"),
            text_bold=s.get("text_bold", False),
            paragraphs=shape_paragraphs,
            line_spacing_pt=s.get("line_spacing_pt"),
            padding_left_px=s.get("padding_left_px"),
            padding_right_px=s.get("padding_right_px"),
            padding_top_px=s.get("padding_top_px"),
            padding_bottom_px=s.get("padding_bottom_px"),
            vertical_alignment=s.get("vertical_alignment") or "top",
        ))

    return PptxSlideSpec(
        background_color=data.get("background_color"),
        textboxes=textboxes,
        shapes=shapes,
        images=[],
        speaker_notes=data.get("speaker_notes", ""),
        slide_type=data.get("slide_type", "content"),
    )


# ---------------------------------------------------------------------------
# validate_slide_spec: 경계/폰트 검증 및 보정 (헬퍼 함수)
# ---------------------------------------------------------------------------

_CANVAS_W = SLIDES_WIDTH_PX
_CANVAS_H = SLIDES_HEIGHT_PX
_FONT_MIN = PPTX_VALIDATE_FONT_MIN_PT
_FONT_MAX = PPTX_VALIDATE_FONT_MAX_PT
_LH_FACTOR = PPTX_VALIDATE_LINE_HEIGHT_FACTOR
_MARGIN = 40  # 슬라이드 가장자리 최소 여백 (px)


def _clamp_font(pt: int | None, font_min: int = _FONT_MIN, font_max: int = _FONT_MAX) -> int | None:
    """폰트 크기를 허용 범위로 클램핑한다."""
    if pt is None:
        return None
    return max(font_min, min(font_max, pt))


def _clip_rect(
    left: float, top: float, width: float, height: float,
    canvas_w: float = _CANVAS_W, canvas_h: float = _CANVAS_H,
    margin: int = _MARGIN,
    *, is_decorative: bool = False,
) -> tuple[float, float, float, float]:
    """요소 위치/크기를 캔버스 범위 내로 클리핑한다.

    일반 요소는 margin 여백을 강제하고, 장식 요소(is_decorative)는
    캔버스 전체를 사용할 수 있도록 기존 동작을 유지한다.
    """
    if is_decorative:
        # 장식용 요소: 캔버스 전체 허용 (left>=0, 캔버스 끝까지)
        left = max(0, min(left, canvas_w - 10))
        top = max(0, min(top, canvas_h - 10))
        width = max(10, min(width, canvas_w - left))
        height = max(10, min(height, canvas_h - top))
    else:
        # 일반 요소: margin 여백 강제
        left = max(margin, min(left, canvas_w - margin - 10))
        top = max(margin, min(top, canvas_h - margin - 10))
        max_right = canvas_w - margin
        width = max(10, min(width, max_right - left))
        max_bottom = canvas_h - margin
        height = max(10, min(height, max_bottom - top))
    return left, top, width, height


def _apply_font_scale(
    paragraphs: list[PptxParagraph],
    scale: float,
    font_min: int = _FONT_MIN,
) -> list[PptxParagraph]:
    """모든 run의 font_size_pt에 scale을 적용한다. font_min 이하로는 축소하지 않음."""
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


def _validate_textboxes(
    textboxes: list[PptxTextBox],
    canvas_w: float = _CANVAS_W,
    canvas_h: float = _CANVAS_H,
    font_min: int = _FONT_MIN,
    font_max: int = _FONT_MAX,
    lh_factor: float = _LH_FACTOR,
    margin: int = _MARGIN,
) -> list[PptxTextBox]:
    """텍스트박스 목록을 검증/보정한다.

    폰트 메트릭 기반 줄바꿈 계산으로 필요 높이를 산출하고,
    높이 부족 시 박스 확장 → 캔버스 초과 시 폰트 축소를 적용한다.
    """
    validated: list[PptxTextBox] = []
    for tb in textboxes:
        has_text = any(
            run.text.strip()
            for para in tb.paragraphs
            for run in para.runs
        )
        if not has_text:
            continue

        # 폰트 클램핑
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

        # 폰트 메트릭 기반 필요 높이 계산
        required_h = calculate_required_height(
            new_paragraphs, width, tb.line_spacing_pt,
        )

        max_available_h = canvas_h - margin - top
        if height < required_h:
            # 먼저 박스 확장 시도
            height = min(required_h, max_available_h)

        # 확장 후에도 부족하면 폰트 축소
        if height < required_h and required_h > 0:
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


def _validate_shapes(
    shapes: list[PptxShape],
    canvas_w: float = _CANVAS_W,
    canvas_h: float = _CANVAS_H,
    font_min: int = _FONT_MIN,
    font_max: int = _FONT_MAX,
    lh_factor: float = _LH_FACTOR,
    margin: int = _MARGIN,
) -> list[PptxShape]:
    """도형 목록을 검증/보정한다.

    폰트 메트릭 기반 줄바꿈 계산으로 필요 높이를 산출하고,
    높이 부족 시 박스 확장 → 캔버스 초과 시 폰트 축소를 적용한다.
    """
    validated: list[PptxShape] = []
    for s in shapes:
        # 장식용 shape: 텍스트/paragraphs 없고 높이 ≤ 10px인 얇은 라인/바
        is_decorative = (
            not s.text
            and not s.paragraphs
            and s.height_px <= 10
        )
        left, top, width, height = _clip_rect(
            s.left_px, s.top_px, s.width_px, s.height_px,
            canvas_w, canvas_h, margin,
            is_decorative=is_decorative,
        )
        clamped_text_size = _clamp_font(s.text_size_pt, font_min, font_max)

        # paragraphs 내부 폰트 클램핑
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

        max_bottom = canvas_h if is_decorative else (canvas_h - margin)

        # padding 해석
        pad_l = s.padding_left_px if s.padding_left_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX
        pad_r = s.padding_right_px if s.padding_right_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX
        pad_t = s.padding_top_px if s.padding_top_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX
        pad_b = s.padding_bottom_px if s.padding_bottom_px is not None else TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX

        required_h = 0.0

        # shape.text (단순 텍스트) 높이 계산
        if s.text and clamped_text_size:
            required_h = calculate_required_height_simple_text(
                s.text, clamped_text_size, width,
                line_spacing_pt=s.line_spacing_pt,
                padding_left_px=pad_l, padding_right_px=pad_r,
                padding_top_px=pad_t, padding_bottom_px=pad_b,
            )

        # shape.paragraphs (구조화 텍스트) 높이 계산
        if new_shape_paragraphs:
            para_h = calculate_required_height(
                new_shape_paragraphs, width, s.line_spacing_pt,
                padding_left_px=pad_l, padding_right_px=pad_r,
                padding_top_px=pad_t, padding_bottom_px=pad_b,
            )
            required_h = max(required_h, para_h)

        if required_h > 0 and height < required_h:
            # 먼저 확장 시도
            height = min(required_h, max_bottom - top)

        # 확장 후에도 부족하면 폰트 축소
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


_OVERLAP_GAP = 8  # 겹침 해소 시 요소 간 최소 간격 (px)
_OVERLAP_MAX_PASSES = 3  # 겹침 해소 최대 반복 횟수


def _resolve_overlaps(
    textboxes: list[PptxTextBox],
    shapes: list[PptxShape],
    canvas_h: float = _CANVAS_H,
    margin: int = _MARGIN,
    gap: int = _OVERLAP_GAP,
    max_passes: int = _OVERLAP_MAX_PASSES,
) -> tuple[list[PptxTextBox], list[PptxShape]]:
    """비장식 요소 간 수직 겹침을 해소한다.

    알고리즘:
    1. 비장식 요소의 bounding box를 수집
    2. top_px 오름차순 정렬
    3. 겹치는 쌍 → 아래 요소를 push-down (위 요소의 bottom + gap)
    4. push-down 후 캔버스 초과 시 height 축소 (최소 10px)
    5. 최대 max_passes회 반복

    한계: 수평 겹침은 해소하지 않음 (수평 이동은 레이아웃을 크게 망가뜨릴 수 있음).
    """
    # 인덱싱: (종류, 원본 인덱스, left, top, width, height)
    items: list[tuple[str, int, float, float, float, float]] = []
    for i, tb in enumerate(textboxes):
        items.append(("tb", i, tb.left_px, tb.top_px, tb.width_px, tb.height_px))
    for i, s in enumerate(shapes):
        is_decorative = not s.text and not s.paragraphs and s.height_px <= 10
        if is_decorative:
            continue
        items.append(("sh", i, s.left_px, s.top_px, s.width_px, s.height_px))

    if len(items) <= 1:
        return textboxes, shapes

    max_bottom = canvas_h - margin

    for _ in range(max_passes):
        # top 기준 정렬
        items.sort(key=lambda x: x[3])
        changed = False
        for a_idx in range(len(items)):
            a_kind, a_orig, a_l, a_t, a_w, a_h = items[a_idx]
            a_right = a_l + a_w
            a_bottom = a_t + a_h
            for b_idx in range(a_idx + 1, len(items)):
                b_kind, b_orig, b_l, b_t, b_w, b_h = items[b_idx]
                b_right = b_l + b_w
                # 수평 겹침 확인
                if a_l >= b_right or b_l >= a_right:
                    continue
                # 수직 겹침 확인
                if a_bottom <= b_t:
                    continue
                # 겹침 → 아래 요소 push-down
                new_top = a_bottom + gap
                if new_top + b_h > max_bottom:
                    # 캔버스 초과 시 height 축소
                    b_h = max(10, max_bottom - new_top)
                if new_top >= max_bottom:
                    # push-down 자체가 불가능한 경우는 건너뜀
                    continue
                items[b_idx] = (b_kind, b_orig, b_l, new_top, b_w, b_h)
                changed = True
        if not changed:
            break

    # 결과를 반영
    new_textboxes = list(textboxes)
    new_shapes = list(shapes)
    for kind, orig_idx, _l, new_top, _w, new_h in items:
        if kind == "tb":
            tb = new_textboxes[orig_idx]
            if tb.top_px != new_top or tb.height_px != new_h:
                new_textboxes[orig_idx] = PptxTextBox(
                    left_px=tb.left_px,
                    top_px=new_top,
                    width_px=tb.width_px,
                    height_px=new_h,
                    paragraphs=tb.paragraphs,
                    line_spacing_pt=tb.line_spacing_pt,
                    vertical_alignment=tb.vertical_alignment,
                )
        else:
            s = new_shapes[orig_idx]
            if s.top_px != new_top or s.height_px != new_h:
                new_shapes[orig_idx] = replace(s, top_px=new_top, height_px=new_h)

    return new_textboxes, new_shapes


def validate_slide_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """LLM 출력 PptxSlideSpec을 검증하고 보정한다."""
    validated_textboxes = _validate_textboxes(spec.textboxes)
    validated_shapes = _validate_shapes(spec.shapes)
    validated_textboxes, validated_shapes = _resolve_overlaps(
        validated_textboxes, validated_shapes,
    )

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=validated_textboxes,
        shapes=validated_shapes,
        images=spec.images,
        speaker_notes=spec.speaker_notes,
        slide_type=spec.slide_type,
    )


# ---------------------------------------------------------------------------
# 직렬화 / 역직렬화
# ---------------------------------------------------------------------------

def slide_spec_to_json(slide_spec: PptxSlideSpec) -> str:
    """단일 PptxSlideSpec을 JSON 문자열로 직렬화."""
    data = asdict(slide_spec)
    for img in data.get("images", []):
        img.pop("image_bytes", None)
    return json.dumps(data, ensure_ascii=False, indent=2)


def parse_slide_spec_json(json_str: str) -> PptxSlideSpec:
    """JSON 문자열을 단일 PptxSlideSpec으로 역직렬화."""
    data = json.loads(json_str)
    return parse_slide_spec(data)


def design_spec_to_json(design_spec: DesignSpec) -> str:
    """DesignSpec을 JSON 문자열로 직렬화."""
    data = asdict(design_spec)
    # image_bytes는 직렬화 대상에서 제외
    for slide in data.get("slides", []):
        for img in slide.get("images", []):
            img.pop("image_bytes", None)
    return json.dumps(data, ensure_ascii=False, indent=2)


def parse_design_spec_json(json_str: str) -> DesignSpec:
    """JSON 문자열을 DesignSpec으로 역직렬화."""
    data = json.loads(json_str)
    slides: list[PptxSlideSpec] = []
    for slide_data in data.get("slides", []):
        slides.append(parse_slide_spec(slide_data))
    return DesignSpec(slides=slides)
