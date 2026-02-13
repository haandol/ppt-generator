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
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
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
    """요소 위치/크기를 캔버스 범위 내로 클리핑한다."""
    left = max(0, min(left, canvas_w - 10))
    top = max(0, min(top, canvas_h - 10))
    width = max(10, min(width, canvas_w - left))
    # 장식용 요소(얇은 라인/바)는 캔버스 끝까지 허용, 그 외는 하단 여백 확보
    max_bottom = canvas_h if is_decorative else (canvas_h - margin)
    height = max(10, min(height, max_bottom - top))
    return left, top, width, height


def _validate_textboxes(
    textboxes: list[PptxTextBox],
    canvas_w: float = _CANVAS_W,
    canvas_h: float = _CANVAS_H,
    font_min: int = _FONT_MIN,
    font_max: int = _FONT_MAX,
    lh_factor: float = _LH_FACTOR,
    margin: int = _MARGIN,
) -> list[PptxTextBox]:
    """텍스트박스 목록을 검증/보정한다."""
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
        num_lines = 0
        for para in tb.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                clamped_size = _clamp_font(run.font_size_pt, font_min, font_max)
                new_runs.append(replace(run, font_size_pt=clamped_size))
                if clamped_size and clamped_size > max_font_in_tb:
                    max_font_in_tb = clamped_size
            new_paragraphs.append(replace(para, runs=new_runs))
            num_lines += 1

        left, top, width, height = _clip_rect(
            tb.left_px, tb.top_px, tb.width_px, tb.height_px,
            canvas_w, canvas_h, margin,
        )

        min_required_height = num_lines * max_font_in_tb * lh_factor
        if height < min_required_height:
            height = min(min_required_height, canvas_h - margin - top)

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
    """도형 목록을 검증/보정한다."""
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
        shape_num_lines = 0
        for para in s.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                clamped = _clamp_font(run.font_size_pt, font_min, font_max)
                new_runs.append(replace(run, font_size_pt=clamped))
                if clamped and clamped > shape_max_font:
                    shape_max_font = clamped
            new_shape_paragraphs.append(replace(para, runs=new_runs))
            shape_num_lines += 1

        max_bottom = canvas_h if is_decorative else (canvas_h - margin)
        if s.text and clamped_text_size:
            line_count = s.text.count("\n") + 1
            min_h = line_count * clamped_text_size * lh_factor
            if height < min_h:
                height = min(min_h, max_bottom - top)

        if new_shape_paragraphs and shape_num_lines > 0:
            min_h = shape_num_lines * shape_max_font * lh_factor
            if height < min_h:
                height = min(min_h, max_bottom - top)

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


def validate_slide_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """LLM 출력 PptxSlideSpec을 검증하고 보정한다."""
    validated_textboxes = _validate_textboxes(spec.textboxes)
    validated_shapes = _validate_shapes(spec.shapes)

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=validated_textboxes,
        shapes=validated_shapes,
        images=spec.images,
        speaker_notes=spec.speaker_notes,
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
