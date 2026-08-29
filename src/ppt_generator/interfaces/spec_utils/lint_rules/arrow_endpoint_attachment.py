"""arrow-endpoint-attachment: 화살표 끝점이 박스 변에 부착되어 있는지 검사.

. `end_arrow=True` 또는 `start_arrow=True` 인 line shape 의 화살표 끝점이
어떤 non-decorative shape 의 외곽 변에서 LINT_ARROW_ATTACH_TOLERANCE_PX 이내에
위치하지 않으면 경고. 박스 위치를 옮긴 뒤 연결선 좌표를 갱신하지 않아 화살표가
허공에서 끝나는 회귀를 좌표 기반으로 사전 차단한다.

검사 대상:
- shape_type="line" 이며 end_arrow=True 또는 start_arrow=True 인 shape

비교 대상 박스:
- non-line, non-decorative shape (텍스트가 있거나 fill_color 가 있는 shape)
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import (
    LINT_ARROW_ATTACH_TOLERANCE_PX,
    LINT_ARROW_ENDPOINT_BOUNDARY_TOLERANCE_PX,
)
from ppt_generator.interfaces.line_geometry import line_endpoints
from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)


def _has_text(shape: PptxShape) -> bool:
    if shape.text and shape.text.strip():
        return True
    return any(run.text.strip() for para in shape.paragraphs for run in para.runs)


def _is_attachable_box(shape: PptxShape) -> bool:
    """화살표가 부착될 수 있는 박스 후보. line/decorative 는 제외."""
    if shape.shape_type == "line":
        return False
    if is_decorative(shape):
        return False
    if not _has_text(shape) and shape.fill_color is None:
        return False
    return True


def _box_bounds(shape: PptxShape) -> tuple[float, float, float, float]:
    left = shape.left_px
    top = shape.top_px
    right = left + abs(shape.width_px)
    bottom = top + abs(shape.height_px)
    return left, top, right, bottom


def _point_near_box_edge(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
    tolerance: float,
) -> bool:
    """점 (x, y) 가 박스 외곽 사각형의 4 변 중 어느 한 변에서 tolerance 이내인지.

    내부에 깊숙이 있는 경우는 부착으로 간주하지 않는다 (화살표는 박스 가장자리에
    닿아야 의미가 있음). 단, 박스 안쪽 tolerance 이내 (변 근처) 는 허용.
    """
    left, top, right, bottom = bounds
    # 점이 box 의 외곽 +tol 영역 안에 있어야 함
    if x < left - tolerance or x > right + tolerance:
        return False
    if y < top - tolerance or y > bottom + tolerance:
        return False
    # 4 변 중 한 변에서 tolerance 이내인지
    near_left = abs(x - left) <= tolerance
    near_right = abs(x - right) <= tolerance
    near_top = abs(y - top) <= tolerance
    near_bottom = abs(y - bottom) <= tolerance
    return near_left or near_right or near_top or near_bottom


def _point_box_penetration_depth(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
) -> float | None:
    """점이 박스 안에 있으면 가장 가까운 변까지의 깊이, 밖이면 None."""
    left, top, right, bottom = bounds
    if x < left or x > right or y < top or y > bottom:
        return None
    return min(x - left, right - x, y - top, bottom - y)


def _arrow_endpoints(line: PptxShape) -> list[tuple[float, float, str]]:
    """end_arrow / start_arrow 가 켜진 끝점들의 좌표를 반환.

    line bbox convention 은 렌더러/PPTX 익스포터와 동일하다: (left, top) 은 항상
    최소 좌표 모서리이고 박스는 (left, top)~(left+|w|, top+|h|) 를 차지한다.
    width/height 의 부호는 두 끝점의 대각 방향만 정한다 — 양수면 시작=최소 모서리,
    끝=최대 모서리이고, 음수면 그 축의 시작/끝이 뒤바뀐다. 이 부호를 반영하지
    않으면 음수 성분 라인의 끝점이 실제 렌더 위치와 최대 |w|/|h|px 어긋나 부착
    검사가 잘못된 좌표로 판정된다.
    """
    endpoints: list[tuple[float, float, str]] = []
    (start_x, start_y), (end_x, end_y) = line_endpoints(
        line.left_px,
        line.top_px,
        line.width_px,
        line.height_px,
    )
    if line.start_arrow:
        endpoints.append((start_x, start_y, "start"))
    if line.end_arrow:
        endpoints.append((end_x, end_y, "end"))
    return endpoints


def check_arrow_endpoint_attachment(
    spec: PptxSlideSpec, result: SlideLintResult
) -> None:
    boxes: list[tuple[float, float, float, float]] = [
        _box_bounds(s) for s in spec.shapes if _is_attachable_box(s)
    ]
    if not boxes:
        return

    for idx, shape in enumerate(spec.shapes):
        if shape.shape_type != "line":
            continue
        endpoints = _arrow_endpoints(shape)
        for x, y, which in endpoints:
            containing = [
                depth
                for bounds in boxes
                if (depth := _point_box_penetration_depth(x, y, bounds)) is not None
            ]
            if containing:
                penetration = min(containing)
                if penetration > LINT_ARROW_ENDPOINT_BOUNDARY_TOLERANCE_PX:
                    result.violations.append(
                        LintViolation(
                            rule="arrow-endpoint-penetration",
                            severity="error",
                            message=(
                                f"line shape[{idx}] 의 {which} 화살표 끝점 "
                                f"({x:.0f},{y:.0f}) 이 목표 박스 내부로 "
                                f"{penetration:.0f}px 침투함"
                            ),
                            element_index=idx,
                            element_type="shape",
                            current_value={
                                "endpoint": which,
                                "x": round(x, 1),
                                "y": round(y, 1),
                                "penetration_px": round(penetration, 1),
                            },
                            expected="화살촉 끝점이 목표 박스 경계선 위에 위치",
                        )
                    )
                    continue
            if any(
                _point_near_box_edge(x, y, bounds, LINT_ARROW_ATTACH_TOLERANCE_PX)
                for bounds in boxes
            ):
                continue
            result.violations.append(
                LintViolation(
                    rule="arrow-endpoint-attachment",
                    severity="warning",
                    message=(
                        f"line shape[{idx}] 의 {which} 화살표 끝점 "
                        f"({x:.0f},{y:.0f}) 이 어떤 박스 변에도 닿지 않음 "
                        f"(>={LINT_ARROW_ATTACH_TOLERANCE_PX:.0f}px 이내 필요)"
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={
                        "endpoint": which,
                        "x": round(x, 1),
                        "y": round(y, 1),
                    },
                    expected=(
                        f"화살표 끝점이 어떤 박스 변에서 "
                        f"{LINT_ARROW_ATTACH_TOLERANCE_PX:.0f}px 이내"
                    ),
                )
            )
