# modify_component MCP 도구 — Section 단위 부분 수정

Date: 2026-05-26

## Status

Accepted

## Context

ADR-0011 (design) 가 5단 디자인 스펙 계층(Project / Slide / Layout / Section / Content) 을 정의하면서 얻은 핵심 가치는 **Section 트리의 component_id 로 의미 단위 요소를 정확히 지칭할 수 있다** 는 점이다. 그러나 ADR-0011 (design) 는 그 가치를 사용자가 직접 호출할 수 있는 MCP 도구로 노출하지 않은 채 Out of Scope 로 미뤘다.

기존 `modify_design_spec(action="update")` 는 슬라이드 전체를 outline 기반으로 재생성한다. 이 방식의 문제:

1. **부분 변경에 과도한 비용** — "좌측 두 번째 카드 색을 빨간색으로" 같은 좁은 명령에도 슬라이드 전체 LLM 재호출이 일어나 토큰·시간 낭비.
2. **다른 요소가 의도치 않게 변경됨** — 전체 재생성이라 매 호출 결과가 동일하다는 보장이 없어 다이어그램/카드 위치/색이 미세하게 흔들림.
3. **5단 계층의 식별성 미활용** — design_doc.layout 트리와 component_id 링크는 이미 있는데 사용자 명령이 그 식별자를 거치지 않으니 계층의 핵심 가치가 사용되지 않음.

본 ADR 은 design_doc 트리 leaf 1 개를 지목한 부분 수정 도구를 도입한다.

## Decision

`modify_component(project_id, slide_index, component_id, instruction, color_theme)` MCP 도구를 추가한다. 한 호출당 정확히 1 개의 component leaf 를 수정하고, 다른 모든 것(다른 element, grid_plan, background, speaker_notes, design_doc 트리 구조) 은 byte-equal 로 보존한다.

### LLM 입력은 슬라이드 전체 + 대상 component_id

LLM 은 슬라이드 전체 spec(grid_plan, design_doc, textboxes, shapes) + 대상 component_id + 자연어 instruction 을 컨텍스트로 받는다. 토큰 비용이 element-only 방식보다 약간 크지만, 형제 노드의 색·폰트·정렬과 cell 내 다른 element 와의 충돌 회피, design_doc 트리 인식한 bbox 조정이 가능해진다.

### 단일 component 만 수정 (v1)

다중 component(예: "3 개 카드 모두 색 통일") 는 LLM 이 여러 번의 modify_component 호출로 풀거나 기존 update action 사용을 안내한다. API/구현이 단순해지고 부분 수정의 명확성(한 번에 한 곳) 이 디버그성 면에서 우월. 다중 수정은 v2 검토.

### 수정 가능 범위: Content + 대상 leaf bbox

LLM 이 수정할 수 있는 것:
1. 대상 leaf 의 textbox/shape 본체 (텍스트, 색, 폰트, 패딩, alignment, 모양)
2. 대상 leaf 의 bbox (left/top/width/height)
3. 대상 leaf 가 design_doc.layout 트리에서 가리키는 노드의 bbox (textbox/shape bbox 와 동기화)

수정 불가:
- design_doc 트리 구조 (노드 추가/삭제/parent 변경)
- 다른 component 의 spec
- grid_plan / background_color / speaker_notes / 다른 슬라이드

이 범위는 lint 가 자연스럽게 강제한다 — `layout-tree-containment`, `layout-tree-sibling-overlap`, `grid-cell-coverage`, `font-range`, `text-overflow` 등이 그대로 안전망 역할. 구조 변경이 필요한 변경은 기존 `modify_design_spec(action="update")` 를 사용한다.

### 후처리

수정 직후 (1) 변경된 슬라이드만 lint 재검증해 위반 있으면 응답에 포함 (재생성 자동 안 함, 호출자가 결정), (2) 단일 슬라이드 HTML 재렌더해 path 반환, (3) `steps_completed` 에 modify 단계 갱신. 기존 modify_design_spec 후처리와 동일한 패턴.

### 비-design 메타 필드 보존

LLM 이 element 전체를 출력해도, ADR-0013 (design) 결정 3 에 따라 schema 에 없는 z_index / grid_cell / component_id 는 코드가 기존 element 에서 가져와 보존한다.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| element-only LLM 입력 (슬라이드 컨텍스트 제외) | 형제 정렬·디자인 일관성 정보 손실 — 색만 바꿨는데 옆 카드와 보색 깨짐 |
| 다중 component 동시 수정을 v1 부터 지원 | API 복잡도 + 부분 실패 처리(어떤 component 만 적용?) 가 깊어짐 |
| design_doc 없는 슬라이드도 자동 backfill 후 수정 | 본 ADR 범위 밖. backfill 정책은 ADR-0004 에서 분리해 다룸 |
| 자동 review_service 재호출 후 재수정 | 부분 수정에는 비용 대비 이득 작음 — lint 결과 응답 노출로 충분 |

## 하위 호환성

- 기존 `modify_design_spec(action="update")` 는 그대로 유지. 사용자가 큰 변경(트리 구조, 여러 element) 을 요청하면 기존 도구를 안내.
- design_doc 없는 슬라이드(title/closing) 는 미지원 — 명확한 에러로 update 도구 안내.
- imported PPTX 슬라이드는 design_doc=None 이라 미지원이지만, ADR-0004 의 lazy backfill 이 첫 modify_component 호출 시 자동으로 design_doc 을 채운다.

## Consequences

### Positive

- **부분 수정 비용 감소** — 슬라이드 전체 재생성 대비 토큰·시간 절감.
- **결정성 향상** — 대상 외 element 가 byte-equal 보존되어 사용자 신뢰 상승.
- **5단 계층 가치 실현** — ADR-0011 (design) 가 정의한 component_id 식별성을 사용자 인터페이스까지 노출.
- **lint 의 구조적 보장** — 기존 layout-tree-* / grid-cell-* / font-range 규칙이 자연스럽게 부분 수정의 안전망.

### Negative / Risks

- LLM 이 대상 외 element 를 (명시 금지에도) 변경하려 시도할 가능성 — Pydantic 응답 모델이 단일 element 만 받도록 강제하므로 자연 차단.
- bbox 동기화 로직 결함 시 design_doc 트리와 element 가 불일치 — lint 가 즉시 잡지만 직전 결과는 어색할 수 있음.
- modify_component 와 modify_design_spec 사용 시점 분기를 사용자(LLM) 가 잘못 고를 위험 — tool docstring 의 명확한 분기 가이드로 완화.

## Out of Scope

- 다중 component 동시 수정 — v2 검토.
- design_doc 트리 구조 변경(노드 추가/삭제/parent) — 별도 ADR.
- review_service 자동 재호출 — 비용 대비 이득 작음.

## References

- [ADR-0001: 파일 기반 통신 + 슬라이드별 CRUD](./0001-file-based-communication-and-per-slide-crud.md)
- [ADR-0002: modify_design_spec inline outline](./0002-modify-design-spec-inline-outline.md)
- [ADR-0011 (design): 5단 디자인 스펙 계층](../design/0011-five-layer-design-spec-hierarchy.md)
- [ADR-0004: Imported 슬라이드 design_doc lazy backfill](./0004-imported-slide-lazy-backfill.md)
- [ADR-0013 (design): 5단 계층 데이터 무결성](../design/0013-five-layer-data-integrity.md) — z_index 등 비-design 메타 필드 보존 정책
