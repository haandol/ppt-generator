"""cycle-topology: 순환 다이어그램의 위상 일관성 검사 (cross-layer).

design_doc.layout 트리에서 role 이 사이클로 마킹된 (cycle 다이어그램) 묶음 노드를
찾아, 그 자식 노드(사이클 참여 노드)들이 화살표(line shape)로 연결될 때
**각 노드의 유입/유출 차수가 모두 1이고 전체가 단일 방향성 사이클을 이루는지**
검사한다.

"올바른 방향(A→B 가 옳다)"은 검증하지 않는다 — 코드에 도메인 ground-truth 가 없다.
시계/반시계 어느 방향이든 단일 사이클로 닫혀 있으면 통과한다. 즉 "사이클이
위상적으로 깨졌다(유입 2/유출 0 같은 차수 불균형)"만 warning 으로 넛지한다.

사이클 여부는 추측하지 않는다 — design_doc 에 명시 마킹된 묶음만 검사 대상이라
파이프라인/fan-out bus 패턴을 사이클로 오인하지 않는다.

연결 판정: 화살표(line) 의 화살촉(end_arrow → end 끝점, start_arrow → start 끝점)
끝점과 그 반대(tail) 끝점이 각각 어느 사이클 노드 bbox 변에 닿는지로 (tail 노드 →
head 노드) 방향 엣지를 만든다. 한 끝점이 여러 노드에 모호하게 닿거나 닿는 노드가
없으면 그 화살표는 엣지 집계에서 제외(보수적) — 부착 자체는 arrow-endpoint-
attachment 가 별도로 본다.
"""

from __future__ import annotations

from ppt_generator.interfaces.constants import LINT_ARROW_ATTACH_TOLERANCE_PX
from ppt_generator.interfaces.schemas import LayoutNode, PptxShape, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

# design_doc.layout 노드의 role 이 이 값이면 순환 다이어그램으로 마킹된 것.
CYCLE_DIAGRAM_ROLE = "cycle_diagram"


def _find_cycle_groups(nodes: list[LayoutNode]) -> list[LayoutNode]:
    """role 이 cycle 로 마킹된 묶음 노드들을 트리 전체에서 수집한다."""
    found: list[LayoutNode] = []

    def _walk(n: LayoutNode) -> None:
        if (n.role or "").strip().lower() == CYCLE_DIAGRAM_ROLE and n.children:
            found.append(n)
        for c in n.children:
            _walk(c)

    for root in nodes:
        _walk(root)
    return found


def _node_bbox(n: LayoutNode) -> tuple[float, float, float, float] | None:
    if (
        n.left_px is None
        or n.top_px is None
        or n.width_px is None
        or n.height_px is None
    ):
        return None
    left = n.left_px
    top = n.top_px
    return left, top, left + abs(n.width_px), top + abs(n.height_px)


def _arrow_endpoints(
    line: PptxShape,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """(tail, head) 끝점 좌표. head = 화살촉이 가리키는 끝 (흐름의 도착).

    line bbox convention(arrow-endpoint-attachment 와 동일): height_px<0(↗) 이면
    박스가 뒤집혀 start=(left, top+|h|), end=(left+w, top). end_arrow 면 화살촉이
    end 에, start_arrow 면 start 에.
    """
    h = line.height_px
    if h < 0:
        start = (line.left_px, line.top_px + abs(h))
        end = (line.left_px + line.width_px, line.top_px)
    else:
        start = (line.left_px, line.top_px)
        end = (line.left_px + line.width_px, line.top_px + h)
    if line.start_arrow and not line.end_arrow:
        return end, start  # tail=end, head=start
    # end_arrow (또는 양쪽/없음 — 기본 end 를 head 로)
    return start, end


def _node_at_point(
    x: float,
    y: float,
    boxes: list[tuple[str, tuple[float, float, float, float]]],
    tol: float,
) -> str | None:
    """점이 닿는 노드 id. 모호(2개 이상) 하거나 없으면 None."""
    hits: list[str] = []
    for nid, (left, top, right, bottom) in boxes:
        if x < left - tol or x > right + tol or y < top - tol or y > bottom + tol:
            continue
        if (
            min(abs(x - left), abs(x - right)) <= tol
            or min(abs(y - top), abs(y - bottom)) <= tol
        ):
            hits.append(nid)
    return hits[0] if len(hits) == 1 else None


def check_cycle_topology(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    if spec.design_doc is None:
        return

    groups = _find_cycle_groups(spec.design_doc.layout)
    if not groups:
        return  # 마킹된 사이클 다이어그램 없음 — 검사 안 함 (추측 금지)

    tol = LINT_ARROW_ATTACH_TOLERANCE_PX

    for group in groups:
        # 사이클 참여 노드 = 마킹 묶음의 직계 자식 중 bbox 가 있는 노드
        node_boxes: list[tuple[str, tuple[float, float, float, float]]] = []
        for child in group.children:
            bbox = _node_bbox(child)
            if bbox is not None:
                node_boxes.append((child.id, bbox))
        node_ids = {nid for nid, _ in node_boxes}
        if len(node_ids) < 2:
            continue  # 노드가 너무 적어 사이클 판정 무의미

        # 화살표(line) 로 방향 엣지 수집
        in_deg: dict[str, int] = {nid: 0 for nid in node_ids}
        out_deg: dict[str, int] = {nid: 0 for nid in node_ids}
        edges: list[tuple[str, str]] = []
        for shape in spec.shapes:
            if shape.shape_type != "line":
                continue
            if not (shape.start_arrow or shape.end_arrow):
                continue
            tail_pt, head_pt = _arrow_endpoints(shape)
            tail = _node_at_point(*tail_pt, node_boxes, tol)
            head = _node_at_point(*head_pt, node_boxes, tol)
            # 양 끝이 모두 사이클 노드에 명확히 닿을 때만 엣지로 채택 (보수적)
            if tail is None or head is None or tail == head:
                continue
            out_deg[tail] += 1
            in_deg[head] += 1
            edges.append((tail, head))

        if not edges:
            continue  # 사이클 노드를 잇는 화살표가 없으면 판정 보류

        # 위상 일관성: 모든 노드 in==1 and out==1, 엣지 수 == 노드 수,
        # 그리고 하나의 사이클로 연결 (단일 순환).
        unbalanced = [nid for nid in node_ids if in_deg[nid] != 1 or out_deg[nid] != 1]
        single_cycle = (
            not unbalanced
            and len(edges) == len(node_ids)
            and _is_single_cycle(edges, node_ids)
        )
        if single_cycle:
            continue

        # 위반 — 깨진 지점을 메시지에 노출
        detail = ", ".join(
            f"{nid}(in={in_deg[nid]},out={out_deg[nid]})"
            for nid in sorted(node_ids)
            if in_deg[nid] != 1 or out_deg[nid] != 1
        )
        result.violations.append(
            LintViolation(
                rule="cycle-topology-broken",
                severity="warning",
                message=(
                    f"순환 다이어그램 {group.id!r} 이 단일 방향성 사이클을 이루지 "
                    "않습니다 — 화살표 방향이 일관되지 않을 수 있습니다. "
                    f"차수 불균형: {detail or '(엣지 연결이 사이클을 이루지 못함)'}. "
                    "각 노드는 유입 1·유출 1 이어야 합니다."
                ),
                element_index=-1,
                element_type="slide",
                current_value={
                    nid: {"in": in_deg[nid], "out": out_deg[nid]} for nid in node_ids
                },
                expected="모든 노드 유입=1·유출=1, 단일 방향성 사이클",
            )
        )


def _is_single_cycle(edges: list[tuple[str, str]], node_ids: set[str]) -> bool:
    """엣지 집합이 모든 노드를 정확히 한 번 도는 단일 방향성 사이클인지."""
    succ: dict[str, str] = {}
    for tail, head in edges:
        if tail in succ:
            return False  # out-degree > 1
        succ[tail] = head
    if len(succ) != len(node_ids):
        return False
    # 한 노드에서 출발해 모든 노드를 거쳐 출발점으로 돌아오는지
    start = next(iter(node_ids))
    seen: set[str] = set()
    cur = start
    for _ in range(len(node_ids)):
        if cur in seen or cur not in succ:
            return False
        seen.add(cur)
        cur = succ[cur]
    return cur == start and len(seen) == len(node_ids)
