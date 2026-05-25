"""textbox-shape-intrusion: 텍스트박스가 다른 채워진 도형 영역으로 침범하는지 검사.

라벨/주석 텍스트박스가 인접한 카드/컨테이너 도형의 bbox 안으로 일정 비율 이상
들어가면 위반. 다이어그램에서 라벨이 인접 박스 위에 얹혀 가독성을 해치는
회귀를 좌표 기반으로 사전 차단한다.

검사 대상:
- 짧은 텍스트박스 (라벨, 주석, 화살표 부착 텍스트 등)

비교 대상:
- fill_color 가 있는 non-line, non-decorative shape

제외 케이스:
- 컨테이너-자식 관계: 텍스트박스가 큰 shape 내부에 의도적으로 놓인 경우
  (텍스트박스 bbox 가 shape bbox 안에 완전히 포함되어 있고, shape 가 dash_style 점선
  컨테이너이거나 라벨이 그 shape 의 grid_cell 과 일치)는 정상.
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import LINT_TEXTBOX_INTRUSION_RATIO
from ppt_generator.interfaces.schemas import (
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
)
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)


def _bounds(
    left: float, top: float, width: float, height: float
) -> tuple[float, float, float, float]:
    return left, top, left + abs(width), top + abs(height)


def _rect_area(b: tuple[float, float, float, float]) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _intersection_area(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def _is_filled_card(shape: PptxShape) -> bool:
    if shape.shape_type == "line":
        return False
    if is_decorative(shape):
        return False
    if shape.fill_color is None:
        return False
    return True


def _textbox_chars(tb: PptxTextBox) -> int:
    return sum(len(run.text) for para in tb.paragraphs for run in para.runs if run.text)


def _is_container_child(
    tb_bounds: tuple[float, float, float, float],
    shape: PptxShape,
    shape_bounds: tuple[float, float, float, float],
    tb_grid_cell: str | None,
) -> bool:
    """텍스트박스가 shape 의 의도된 자식 컨테이너인지.

    - shape 가 dash_style 점선 컨테이너이고 텍스트박스가 완전히 안에 들어 있으면 자식.
    - 두 요소가 같은 grid_cell 을 공유하고 텍스트박스가 완전히 안에 들어 있으면 자식.
    """
    if not (
        shape_bounds[0] <= tb_bounds[0]
        and shape_bounds[1] <= tb_bounds[1]
        and shape_bounds[2] >= tb_bounds[2]
        and shape_bounds[3] >= tb_bounds[3]
    ):
        return False
    if shape.dash_style and shape.fill_color in (None, "transparent"):
        return True
    if tb_grid_cell and shape.grid_cell == tb_grid_cell:
        # 같은 cell 안에 의도적으로 배치된 경우만 자식으로 간주
        # 단, shape 가 그 cell 의 메인 카드일 때만
        return True
    return False


def check_textbox_shape_intrusion(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    cards: list[tuple[int, PptxShape, tuple[float, float, float, float]]] = [
        (i, s, _bounds(s.left_px, s.top_px, s.width_px, s.height_px))
        for i, s in enumerate(spec.shapes)
        if _is_filled_card(s)
    ]
    if not cards:
        return

    for tb_idx, tb in enumerate(spec.textboxes):
        if _textbox_chars(tb) == 0:
            continue
        tb_bounds = _bounds(tb.left_px, tb.top_px, tb.width_px, tb.height_px)
        tb_area = _rect_area(tb_bounds)
        if tb_area <= 0:
            continue

        for card_idx, card_shape, card_bounds in cards:
            inter = _intersection_area(tb_bounds, card_bounds)
            if inter <= 0:
                continue
            if _is_container_child(tb_bounds, card_shape, card_bounds, tb.grid_cell):
                continue
            ratio = inter / tb_area
            if ratio < LINT_TEXTBOX_INTRUSION_RATIO:
                continue
            result.violations.append(
                LintViolation(
                    rule="textbox-shape-intrusion",
                    severity="warning",
                    message=(
                        f"textbox[{tb_idx}] 가 채워진 shape[{card_idx}] 영역으로 "
                        f"{ratio * 100:.0f}% 침범 (라벨이 카드 위에 얹힘) — "
                        f"라벨을 카드 바깥으로 이동 필요"
                    ),
                    element_index=tb_idx,
                    element_type="textbox",
                    current_value={
                        "intrusion_ratio": round(ratio, 2),
                        "card_shape_index": card_idx,
                    },
                    expected=(
                        f"텍스트박스 bbox 가 채워진 shape bbox 와 "
                        f"{LINT_TEXTBOX_INTRUSION_RATIO * 100:.0f}% 미만으로 겹쳐야 함"
                    ),
                )
            )
