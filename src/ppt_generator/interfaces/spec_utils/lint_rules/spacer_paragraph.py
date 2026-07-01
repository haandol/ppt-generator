"""spacer-paragraph: 공백 한 글자뿐인 단락이 카드 fill 색상과 같은 색을 갖는 안티패턴.

LLM이 카드 paragraphs 사이에 시각적 간격을 주려고 ``text=" "``, ``font_size_pt=10``,
``color=<카드 fill_color>`` 인 spacer 단락을 끼워넣는 패턴이 있다.

이 spacer는 보이지 않는 글자지만 줄 높이를 점유하므로:

1. autofit_mode=expand_height 와 결합하면 카드를 추가로 부풀린다.
2. 같은 행에서 다른 카드와 paragraphs 수가 달라져 시각 정렬이 깨진다.
3. 텍스트가 한 글자뿐이라 contrast 룰을 우회한다 (실제로는 "보이지 않는 텍스트").

가독성에 기여하지 않고 레이아웃만 망치므로 패턴 자체를 차단하고, 간격이 필요한
경우 ``padding_*_px`` 또는 ``line_spacing_pt`` 로 표현하도록 유도한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxParagraph, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)


def _is_spacer_paragraph(para: PptxParagraph, host_fill_color: str | None) -> bool:
    """단락이 spacer 안티패턴인지 판정."""
    runs = para.runs
    if len(runs) != 1:
        return False
    run = runs[0]
    text = run.text or ""
    # 공백/빈 글자만 있는 단락
    if text.strip():
        return False
    if not text:  # 완전 빈 단락은 별도 — spacer가 아님
        return False
    # color가 host fill_color와 동일하면 의도적 은폐 → spacer
    if host_fill_color and run.color and run.color.lower() == host_fill_color.lower():
        return True
    return False


def check_spacer_paragraph(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    for s_idx, shape in enumerate(spec.shapes):
        host_fill = shape.fill_color
        for p_idx, para in enumerate(shape.paragraphs):
            if not _is_spacer_paragraph(para, host_fill):
                continue
            result.violations.append(
                LintViolation(
                    rule="spacer-paragraph",
                    severity="warning",
                    message=(
                        f"shape[{s_idx}] paragraphs[{p_idx}]가 spacer 안티패턴 — "
                        "공백 텍스트에 카드 fill_color를 사용해 보이지 않는 줄을 만든다."
                    ),
                    element_index=s_idx,
                    element_type="shape",
                    current_value={
                        "paragraph_index": p_idx,
                        "run_text": para.runs[0].text,
                        "run_color": para.runs[0].color,
                        "host_fill_color": host_fill,
                    },
                    expected=(
                        "spacer 단락을 제거하고 간격이 필요하면 padding_*_px "
                        "또는 line_spacing_pt 로 표현"
                    ),
                )
            )
