"""component-id-link: Section ↔ Content 계층 link 정합성 검사.

Cross-layer rule:
  - component-id-link-orphan-element: textbox/shape 의 component_id 가 design_doc.layout
    트리의 어떤 leaf id 와도 매칭되지 않음
  - component-id-link-orphan-leaf: design_doc.layout 의 component leaf 가 어떤 textbox/
    shape 도 그것을 참조하지 않음 (0 references)
  - component-id-link-ambiguous: 같은 component_id 가 두 개 이상의 element 에서 참조됨
    (textbox-shape 양쪽 또는 같은 collection 내 중복)

design_doc 자체가 None 인 슬라이드 (title/closing/imported 미-backfill) 는 검사 대상
제외 — None 은 정상 graceful fallback.
component_id 가 None 인 element 는 정상 (장식 connector 등). 검사는 component_id 가
설정된 element 에 한정한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import LayoutNode, PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)


def _collect_leaf_ids(nodes: list[LayoutNode]) -> set[str]:
    """design_doc.layout 트리 (임의 깊이) 의 leaf 노드 id 집합."""
    leaves: set[str] = set()

    def _walk(n: LayoutNode) -> None:
        if not n.children:
            leaves.add(n.id)
            return
        for c in n.children:
            _walk(c)

    for root in nodes:
        _walk(root)
    return leaves


def check_component_id_link(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    if spec.design_doc is None:
        return  # title/closing/imported 미-backfill — 정상 graceful fallback

    leaf_ids = _collect_leaf_ids(spec.design_doc.layout)
    # element 별 (kind, index, component_id) 수집 (None 제외)
    refs: list[tuple[str, int, str]] = []
    for i, tb in enumerate(spec.textboxes):
        if tb.component_id:
            refs.append(("textbox", i, tb.component_id))
    for i, s in enumerate(spec.shapes):
        if s.component_id:
            refs.append(("shape", i, s.component_id))

    # 1) orphan element — component_id 가 leaf 에 없음
    for kind, idx, cid in refs:
        if cid not in leaf_ids:
            result.violations.append(
                LintViolation(
                    rule="component-id-link-orphan-element",
                    severity="error",
                    message=(
                        f"{kind}#{idx}.component_id={cid!r} 가 design_doc.layout 트리의 "
                        "어떤 leaf 와도 매칭되지 않습니다."
                    ),
                    element_index=idx,
                    element_type=kind,
                    current_value=cid,
                    expected="design_doc.layout 의 leaf id 와 매칭",
                )
            )

    # 2) ambiguous — 같은 component_id 가 두 군데 이상 참조됨
    by_cid: dict[str, list[tuple[str, int]]] = {}
    for kind, idx, cid in refs:
        by_cid.setdefault(cid, []).append((kind, idx))
    for cid, locs in by_cid.items():
        if len(locs) > 1:
            loc_str = ", ".join(f"{k}#{i}" for k, i in locs)
            result.violations.append(
                LintViolation(
                    rule="component-id-link-ambiguous",
                    severity="error",
                    message=(
                        f"component_id={cid!r} 가 두 개 이상의 element 에서 참조됨: "
                        f"{loc_str}. component_id 는 슬라이드 내 unique 해야 합니다."
                    ),
                    element_index=-1,
                    element_type="slide",
                    current_value=cid,
                )
            )

    # 3) orphan leaf — design_doc 의 leaf 인데 어떤 element 도 참조 안 함
    referenced_cids = {cid for _, _, cid in refs}
    for leaf_id in leaf_ids:
        if leaf_id not in referenced_cids:
            result.violations.append(
                LintViolation(
                    rule="component-id-link-orphan-leaf",
                    severity="warning",
                    message=(
                        f"design_doc.layout leaf {leaf_id!r} 가 어떤 textbox/shape 에서도 "
                        "component_id 로 참조되지 않습니다. 의도된 결과가 아니라면 element 를 "
                        "트리에 연결하거나 leaf 를 제거하세요."
                    ),
                    element_index=-1,
                    element_type="slide",
                    current_value=leaf_id,
                )
            )
