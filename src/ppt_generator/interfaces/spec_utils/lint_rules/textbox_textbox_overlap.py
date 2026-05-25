"""textbox-textbox-overlap: 두 텍스트박스의 bbox가 시각적으로 겹치는지 검사.

라벨/주석 텍스트박스끼리 좌표가 겹치면 글자가 서로 위에 그려져 가독성이
완전히 망가진다. 글자는 어떤 경우에도 다른 글자 위에 얹혀서는 안 된다.
좌표 기반으로 사전 차단한다.

검사 대상:
- 텍스트가 들어 있는 모든 textbox 쌍

위반 조건:
- 두 textbox bbox 의 교집합 면적이 어느 한쪽 면적의
  LINT_TEXTBOX_TEXTBOX_OVERLAP_RATIO 이상
- 단, 두 textbox 가 동일한 grid_cell 의 header (제목/부제 등) 영역 안에서
  의도적으로 겹치게 디자인된 경우는 제외 (현재는 적용 케이스 없음)

특수 케이스:
- 같은 textbox 가 multiple paragraphs 를 갖는 경우는 단일 요소이므로
  자기 자신과의 비교 대상이 아니다.
- 빈 textbox (empty paragraphs / empty runs) 는 검사 대상에서 제외.
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import LINT_TEXTBOX_TEXTBOX_OVERLAP_RATIO
from ppt_generator.interfaces.schemas import PptxSlideSpec, PptxTextBox
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)


def _bounds(tb: PptxTextBox) -> tuple[float, float, float, float]:
    return (
        tb.left_px,
        tb.top_px,
        tb.left_px + abs(tb.width_px),
        tb.top_px + abs(tb.height_px),
    )


def _rect_area(b: tuple[float, float, float, float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersection_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def _textbox_chars(tb: PptxTextBox) -> int:
    return sum(len(run.text) for para in tb.paragraphs for run in para.runs if run.text)


def check_textbox_textbox_overlap(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    boxes: list[tuple[int, PptxTextBox, tuple[float, float, float, float], float]] = []
    for i, tb in enumerate(spec.textboxes):
        if _textbox_chars(tb) == 0:
            continue
        b = _bounds(tb)
        a = _rect_area(b)
        if a <= 0:
            continue
        boxes.append((i, tb, b, a))

    n = len(boxes)
    for i in range(n):
        idx_a, _tb_a, b_a, area_a = boxes[i]
        for j in range(i + 1, n):
            idx_b, _tb_b, b_b, area_b = boxes[j]
            inter = _intersection_area(b_a, b_b)
            if inter <= 0:
                continue
            ratio = inter / min(area_a, area_b)
            if ratio < LINT_TEXTBOX_TEXTBOX_OVERLAP_RATIO:
                continue
            result.violations.append(
                LintViolation(
                    rule="textbox-textbox-overlap",
                    severity="warning",
                    message=(
                        f"textbox[{idx_a}] 와 textbox[{idx_b}] 의 bbox 가 "
                        f"{ratio * 100:.0f}% 겹침 — 글자끼리 충돌. 한쪽을 이동 필요"
                    ),
                    element_index=idx_a,
                    element_type="textbox",
                    current_value={
                        "overlap_ratio": round(ratio, 2),
                        "other_textbox_index": idx_b,
                    },
                    expected=(
                        f"두 textbox bbox 가 "
                        f"{LINT_TEXTBOX_TEXTBOX_OVERLAP_RATIO * 100:.0f}% 미만으로 겹쳐야 함"
                    ),
                )
            )
