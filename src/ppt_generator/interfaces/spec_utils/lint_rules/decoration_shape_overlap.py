"""decoration-shape-overlap: 작은 장식 도형(✕ 뱃지, 아이콘 원, 작은 ellipse 등)이
다른 채워진 카드/박스 위에 얹혀 시각적 충돌을 일으키는지 검사.

다이어그램에서 의미를 강조하기 위해 추가된 작은 ellipse/뱃지가 인접 카드 영역
안에 박혀 있어 카드 텍스트와 겹치는 회귀를 좌표 기반으로 사전 차단한다.

검사 대상 (decoration):
- shape_type 이 line 이 아니고
- 한 변이 LINT_DECORATION_MAX_DIM_PX 이하인 작은 도형
- 텍스트가 매우 짧음 (<=4 문자) 또는 ellipse/별 같은 강조 모양

비교 대상 (card):
- fill_color 가 있고 본문 텍스트가 들어 있는 큰 shape

위반 조건:
- decoration 의 bbox 가 card 의 bbox 와 LINT_DECORATION_OVERLAP_RATIO 이상 겹침
- 단, decoration 이 card 의 정중앙(가운데 ±20%)에 의도적으로 배치된 경우는 제외
  (배경 강조용으로 의도된 디자인일 가능성)
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import (
    LINT_DECORATION_MAX_DIM_PX,
    LINT_DECORATION_OVERLAP_RATIO,
)
from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)


def _bounds(shape: PptxShape) -> tuple[float, float, float, float]:
    return (
        shape.left_px,
        shape.top_px,
        shape.left_px + abs(shape.width_px),
        shape.top_px + abs(shape.height_px),
    )


def _rect_area(b: tuple[float, float, float, float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersection_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def _shape_chars(shape: PptxShape) -> int:
    total = 0
    if shape.text:
        total += len(shape.text)
    for para in shape.paragraphs:
        for run in para.runs:
            if run.text:
                total += len(run.text)
    return total


def _is_decoration_candidate(shape: PptxShape) -> bool:
    if shape.shape_type == "line":
        return False
    if is_decorative(shape):
        # 매우 얇은 라인성 장식은 별도 규칙(hidden_decorative_strip)에서 처리
        return False
    w = abs(shape.width_px)
    h = abs(shape.height_px)
    if max(w, h) > LINT_DECORATION_MAX_DIM_PX:
        return False
    if min(w, h) <= 4:
        return False
    # 짧은 강조 표식 (✕, ✓, ★, 숫자 1자리 등) 또는 텍스트 없는 ellipse/뱃지
    chars = _shape_chars(shape)
    if chars > 4:
        return False
    return True


def _is_card_candidate(shape: PptxShape, decoration_idx: int, idx: int) -> bool:
    if idx == decoration_idx:
        return False
    if shape.shape_type == "line":
        return False
    if is_decorative(shape):
        return False
    if shape.fill_color is None:
        return False
    w = abs(shape.width_px)
    h = abs(shape.height_px)
    if max(w, h) <= LINT_DECORATION_MAX_DIM_PX:
        # 카드라기엔 너무 작음
        return False
    if _shape_chars(shape) == 0:
        return False
    return True


def _is_centered_overlay(
    deco_b: tuple[float, float, float, float],
    card_b: tuple[float, float, float, float],
) -> bool:
    """decoration 이 card 의 정중앙(가운데 ±20%) 에 위치하면 의도된 오버레이로 간주."""
    deco_cx = (deco_b[0] + deco_b[2]) / 2
    deco_cy = (deco_b[1] + deco_b[3]) / 2
    card_cx = (card_b[0] + card_b[2]) / 2
    card_cy = (card_b[1] + card_b[3]) / 2
    card_w = card_b[2] - card_b[0]
    card_h = card_b[3] - card_b[1]
    return (
        abs(deco_cx - card_cx) <= card_w * 0.2
        and abs(deco_cy - card_cy) <= card_h * 0.2
    )


def check_decoration_shape_overlap(
    spec: PptxSlideSpec, result: SlideLintResult
) -> None:
    decorations: list[tuple[int, PptxShape, tuple[float, float, float, float]]] = []
    for i, s in enumerate(spec.shapes):
        if _is_decoration_candidate(s):
            decorations.append((i, s, _bounds(s)))
    if not decorations:
        return

    for deco_idx, deco_shape, deco_b in decorations:
        deco_area = _rect_area(deco_b)
        if deco_area <= 0:
            continue
        for card_idx, card_shape in enumerate(spec.shapes):
            if not _is_card_candidate(card_shape, deco_idx, card_idx):
                continue
            card_b = _bounds(card_shape)
            inter = _intersection_area(deco_b, card_b)
            if inter <= 0:
                continue
            if _is_centered_overlay(deco_b, card_b):
                continue
            ratio = inter / deco_area
            if ratio < LINT_DECORATION_OVERLAP_RATIO:
                continue
            result.violations.append(
                LintViolation(
                    rule="decoration-shape-overlap",
                    severity="warning",
                    message=(
                        f"decoration shape[{deco_idx}] 이 카드 shape[{card_idx}] 영역에 "
                        f"{ratio * 100:.0f}% 얹힘 — 카드 바깥의 화살표 경로 위로 이동 필요"
                    ),
                    element_index=deco_idx,
                    element_type="shape",
                    current_value={
                        "overlap_ratio": round(ratio, 2),
                        "card_shape_index": card_idx,
                    },
                    expected=(
                        f"decoration 이 카드 영역과 "
                        f"{LINT_DECORATION_OVERLAP_RATIO * 100:.0f}% 미만 겹침"
                    ),
                )
            )
