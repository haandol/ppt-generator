"""PptxSlideSpec 검증 및 보정 유틸리티.

최소한의 검증만 수행한다:
- 슬라이드 제목(각 페이지 최상단 textbox)의 최소 폰트 크기 보장
- title/closing 슬라이드의 제목 최소 폰트 크기 보장
- 빈 텍스트박스 제거

그 외 레이아웃(위치, 크기, 경계 클리핑)이나 본문 텍스트의 폰트 크기는
LLM 출력을 그대로 존중한다.
"""

from __future__ import annotations

from dataclasses import replace

from ppt_generator.interfaces.constants import (
    SLIDE_TITLE_FONT_MIN_PT,
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)

_SLIDE_TITLE_MIN = SLIDE_TITLE_FONT_MIN_PT
_TITLE_SLIDE_TITLE_MIN = 36


def _is_slide_title(tb: PptxTextBox, is_first: bool) -> bool:
    """슬라이드 제목 textbox 판별: 첫 번째 텍스트가 있는 textbox."""
    return is_first


def _enforce_title_min_font(
    paragraphs: list[PptxParagraph],
    min_pt: int,
) -> list[PptxParagraph]:
    """제목 paragraph의 폰트를 min_pt 이상으로 보장한다."""
    result: list[PptxParagraph] = []
    for para in paragraphs:
        new_runs: list[PptxTextRun] = []
        for run in para.runs:
            if run.font_size_pt is not None and run.font_size_pt < min_pt:
                new_runs.append(replace(run, font_size_pt=min_pt))
            else:
                new_runs.append(run)
        result.append(replace(para, runs=new_runs))
    return result


def _validate_textboxes(
    textboxes: list[PptxTextBox],
    slide_type: str,
) -> list[PptxTextBox]:
    """텍스트박스 검증: 빈 textbox 제거, 제목 최소 폰트 보장."""
    validated: list[PptxTextBox] = []
    found_first_text_tb = False

    for tb in textboxes:
        has_text = any(run.text.strip() for para in tb.paragraphs for run in para.runs)
        if not has_text:
            continue

        is_first = not found_first_text_tb
        if is_first:
            found_first_text_tb = True
            if slide_type in ("title", "closing"):
                min_pt = _TITLE_SLIDE_TITLE_MIN
            else:
                min_pt = _SLIDE_TITLE_MIN
            new_paragraphs = _enforce_title_min_font(tb.paragraphs, min_pt)
            validated.append(replace(tb, paragraphs=new_paragraphs))
        else:
            validated.append(tb)

    return validated


def validate_slide_spec(
    spec: PptxSlideSpec,
    *,
    autofit: bool = True,
) -> PptxSlideSpec:
    """LLM 출력 PptxSlideSpec을 검증하고 보정한다.

    수행하는 보정:
    - 빈 텍스트박스 제거
    - 슬라이드 제목(최상단 textbox) 최소 폰트 크기 보장
    - title/closing 슬라이드 제목은 36pt 이상, content 슬라이드 제목은 24pt 이상

    수행하지 않는 보정:
    - 경계 클리핑 (캔버스 밖 요소 강제 이동)
    - 본문 텍스트/shape 폰트 크기 강제 변경
    - autofit (높이 초과 시 폰트 축소/높이 확장)
    - 카드 폰트 바닥값 강제
    """
    validated_textboxes = _validate_textboxes(spec.textboxes, spec.slide_type)

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=validated_textboxes,
        shapes=spec.shapes,
        images=spec.images,
        speaker_notes=spec.speaker_notes,
        slide_type=spec.slide_type,
    )
