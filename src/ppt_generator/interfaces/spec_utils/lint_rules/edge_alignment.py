"""edge-alignment: 슬라이드 외곽 element 들의 좌/우/상/하 변 정렬 검사.

결정 13f (content layer rule):

같은 슬라이드 안에 배치된 element 들 중 좌측 외곽에 가까운 element 들(left
값이 슬라이드 최소 left 와 cluster_threshold 안)은 left 값이 일치해야 한다.
우측·상단·하단도 동일. 이 정렬이 깨지면 슬라이드 전체가 들쭉날쭉해 보인다.

검사 정책:
  - 클러스터: 슬라이드 element 들의 left/right/top/bottom 각 변에서 *외곽
    값* 을 기준 (left 변은 min(left), right 변은 max(left+width), 등) 으로
    잡고 그 값에서 ±CLUSTER_THRESHOLD_PX (16px) 안에 있는 element 들을 그
    변의 외곽 cluster 로 본다.
  - 정렬 검사: cluster 의 element 들 중 cluster 기준값(min 또는 max) 과의
    편차가 ALIGN_TOLERANCE_PX (4px) 초과면 위반.
  - cluster 에 element 가 1 개뿐이면 정렬 대상이 아님 (skip).
  - 장식 element (텍스트 없는 얇은 line/strip) 는 제외 — 의도적으로 외곽을
    가로지르는 디바이더를 정렬 위반으로 잡으면 false positive 가 많아진다.

Rules:
  - slide-edge-alignment-left: 좌측 외곽 element 들의 left 가 일치하지 않음
  - slide-edge-alignment-right: 우측 외곽 element 들의 right 가 일치하지 않음
  - slide-edge-alignment-top: 상단 외곽 element 들의 top 이 일치하지 않음
  - slide-edge-alignment-bottom: 하단 외곽 element 들의 bottom 이 일치하지 않음

severity="warning" — 시각 결함 신호이지만 데이터 구조 결함은 아니므로
generate 차단까진 하지 않는다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)

CLUSTER_THRESHOLD_PX = 16.0
ALIGN_TOLERANCE_PX = 4.0


def _candidates(
    spec: PptxSlideSpec,
) -> list[tuple[str, int, float, float, float, float, bool]]:
    """element 들의 (kind, idx, left, top, right, bottom, is_decoration).

    decoration 인 stripe/line 도 후보에 포함한다. 다른 본문 element 와
    같은 외곽 cluster 에 들어왔을 때만 정렬 검사 대상이 되도록 cluster
    구성 단계에서 다시 필터한다 — 단독으로 외곽을 가로지르는 의도적
    디바이더는 false positive 가 나지 않는다.
    """
    out: list[tuple[str, int, float, float, float, float, bool]] = []
    for i, tb in enumerate(spec.textboxes):
        # 빈 텍스트박스는 정렬 대상 아님 (clean_slide_spec 로 제거되지만
        # raw lint 에서는 남아있을 수 있음).
        has_text = any(run.text.strip() for para in tb.paragraphs for run in para.runs)
        if not has_text:
            continue
        out.append(
            (
                "textbox",
                i,
                tb.left_px,
                tb.top_px,
                tb.left_px + tb.width_px,
                tb.top_px + tb.height_px,
                False,
            )
        )
    for i, s in enumerate(spec.shapes):
        out.append(
            (
                "shape",
                i,
                s.left_px,
                s.top_px,
                s.left_px + s.width_px,
                s.top_px + s.height_px,
                is_decorative(s),
            )
        )
    return out


def _check_edge(
    edge: str,
    extreme_value: float,
    cluster: list[tuple[str, int, float]],
    result: SlideLintResult,
) -> None:
    """cluster: (kind, idx, edge_value) 리스트. extreme_value: cluster 기준 (min/max)."""
    if len(cluster) < 2:
        return
    misaligned = [
        (k, i, v)
        for (k, i, v) in cluster
        if abs(v - extreme_value) > ALIGN_TOLERANCE_PX
    ]
    if not misaligned:
        return
    locs = ", ".join(
        f"{k}#{i}({edge}={v:.1f}px, Δ{abs(v - extreme_value):.1f}px)"
        for k, i, v in misaligned
    )
    rule = f"slide-edge-alignment-{edge}"
    result.violations.append(
        LintViolation(
            rule=rule,
            severity="warning",
            message=(
                f"슬라이드 {edge} 외곽 정렬이 어긋납니다 (기준 {extreme_value:.1f}px, "
                f"tolerance ±{ALIGN_TOLERANCE_PX:.0f}px). 어긋난 element: {locs}."
            ),
            element_index=-1,
            element_type="slide",
            current_value={
                "edge": edge,
                "extreme": round(extreme_value, 1),
                "tolerance_px": ALIGN_TOLERANCE_PX,
                "misaligned": [
                    {"type": k, "index": i, "value": round(v, 1)}
                    for k, i, v in misaligned
                ],
            },
            expected=f"같은 외곽 cluster 의 {edge} 가 ±{ALIGN_TOLERANCE_PX:.0f}px 이내",
        )
    )


def check_edge_alignment(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    cands = _candidates(spec)
    if len(cands) < 2:
        return

    # 본문(비장식) element 만으로 외곽 기준값을 잡는다. decoration stripe 가
    # 본문 그리드 바깥으로 나가 있더라도 (예: 좌우 외곽 디바이더) 본문
    # 정렬 기준이 흔들리지 않게 한다.
    body = [v for v in cands if not v[6]]
    if len(body) < 2:
        return

    lefts = [v[2] for v in body]
    rights = [v[4] for v in body]
    tops = [v[3] for v in body]
    bottoms = [v[5] for v in body]

    min_left = min(lefts)
    max_right = max(rights)
    min_top = min(tops)
    max_bottom = max(bottoms)

    # cluster 후보는 decoration 포함 전체 element. 단, decoration 단독
    # cluster (본문 element 가 동일 cluster 에 없음) 는 _check_edge 에서
    # len < 2 로 자연 skip — 의도적 외곽 디바이더 false positive 방지.
    def _cluster(value_idx: int, extreme: float) -> list[tuple[str, int, float]]:
        return [
            (cand[0], cand[1], cand[value_idx])
            for cand in cands
            if abs(cand[value_idx] - extreme) <= CLUSTER_THRESHOLD_PX
        ]

    _check_edge("left", min_left, _cluster(2, min_left), result)
    _check_edge("right", max_right, _cluster(4, max_right), result)
    _check_edge("top", min_top, _cluster(3, min_top), result)
    _check_edge("bottom", max_bottom, _cluster(5, max_bottom), result)
