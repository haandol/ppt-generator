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

from ppt_generator.interfaces.schemas import PptxShape, PptxSlideSpec, PptxTextBox
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
    is_decorative,
)

CLUSTER_THRESHOLD_PX = 16.0
ALIGN_TOLERANCE_PX = 4.0


def _candidates(
    spec: PptxSlideSpec,
) -> list[tuple[str, int, float, float, float, float]]:
    """장식 제외한 element 들의 (kind, idx, left, top, right, bottom)."""
    out: list[tuple[str, int, float, float, float, float]] = []
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
            )
        )
    for i, s in enumerate(spec.shapes):
        if is_decorative(s):
            continue
        out.append(
            (
                "shape",
                i,
                s.left_px,
                s.top_px,
                s.left_px + s.width_px,
                s.top_px + s.height_px,
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

    lefts = [v[2] for v in cands]
    rights = [v[4] for v in cands]
    tops = [v[3] for v in cands]
    bottoms = [v[5] for v in cands]

    min_left = min(lefts)
    max_right = max(rights)
    min_top = min(tops)
    max_bottom = max(bottoms)

    left_cluster = [
        (k, i, l_)
        for (k, i, l_, _t, _r, _b) in cands
        if abs(l_ - min_left) <= CLUSTER_THRESHOLD_PX
    ]
    right_cluster = [
        (k, i, r_)
        for (k, i, _l, _t, r_, _b) in cands
        if abs(r_ - max_right) <= CLUSTER_THRESHOLD_PX
    ]
    top_cluster = [
        (k, i, t_)
        for (k, i, _l, t_, _r, _b) in cands
        if abs(t_ - min_top) <= CLUSTER_THRESHOLD_PX
    ]
    bottom_cluster = [
        (k, i, b_)
        for (k, i, _l, _t, _r, b_) in cands
        if abs(b_ - max_bottom) <= CLUSTER_THRESHOLD_PX
    ]

    _check_edge("left", min_left, left_cluster, result)
    _check_edge("right", max_right, right_cluster, result)
    _check_edge("top", min_top, top_cluster, result)
    _check_edge("bottom", max_bottom, bottom_cluster, result)
