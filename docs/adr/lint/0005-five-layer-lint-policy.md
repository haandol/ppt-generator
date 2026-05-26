# 5단 디자인 스펙 계층 — Lint 정책

Date: 2026-05-26 (split from design/0011 결정 12/13)

## Status

Accepted

## Context

design/0011 가 5단 계층(Project / Slide / Layout / Section / Content) 의 *구조* 를 정의하고 design/0013 이 데이터 무결성을 강제하지만, 각 계층이 서로 정합적으로 link 되어 있는지(예: textbox.component_id 가 design_doc.layout 의 leaf 와 매칭되는지) 검증하는 메커니즘은 lint 안에 명시 결정이 없었다.

또한 lint 호출 지점들이 모든 규칙을 한꺼번에 돌렸기 때문에, 거시 위반(grid_plan 미정의) 이 미시 노이즈(개별 textbox 의 폰트 ±1pt) 와 섞여 사용자가 우선순위를 가리기 어려웠다. design/0011 결정 3 의 "구조적 사전 차단" 약속을 실행 차원에서 보강할 두 가지 정책이 필요하다.

1. **Cross-layer link 정합성 검증** — base prompt 가이드만으로는 LLM 결함이 사후 modify 단계에서 ValueError 로 늦게 터진다. 이른 단계에서 lint 로 잡아야 한다.
2. **단계적 lint 실행** — layer 별 우선순위에 따라 검사하다가 거시 layer 에 error 가 있으면 미시 검사를 스킵.

## Decision

### 결정 1 — cross-layer link 정합성을 lint 로 강제한다

다음 lint 규칙군을 `cross` layer 로 추가한다 (모두 design/0013 결정 2 의 RULE_LAYER_MAP 에 등록).

**Section ↔ Content 매칭 (`component-id-link`)**:
- 모든 textbox/shape 의 component_id 는 design_doc.layout 트리 어딘가의 leaf 노드 id 와 매칭되어야 한다 (orphan element).
- 모든 component leaf 는 정확히 1 개의 element 에서 참조되어야 한다 (orphan leaf 또는 ambiguous link).
- 한 component_id 가 textbox 와 shape 양쪽에 등장하면 modify 도구가 어느 element 를 가리키는지 결정 불가 — ambiguous.

`design_doc` 가 None 인 슬라이드(title/closing/imported 미-backfill) 는 검사 제외 (조건부 lint).

**Layout ↔ Section 매칭 (`grid-section-link`)**:
- design_doc.layout 의 모든 노드 cell_id 가 비어있지 않다면 GridPlan.cells.id 집합에 속해야 한다. 깨지면 modify 시 cell 정렬 일관성이 무너진다.

`design_doc` 또는 `grid_plan` 이 None 인 슬라이드는 검사 제외.

**Section ↔ Content bbox 동기화 (`section-element-bbox-mismatch`)**:
- design_doc 의 component leaf bbox 와 그 leaf 를 component_id 로 참조하는 textbox/shape 의 bbox 가 8px 이상 어긋나면 위반. design/0011 결정 3 의 "Section bbox 가 Content bbox 보다 *먼저* 결정된다" 는 약속을 lint 로 검증.

**Section/Cell containment**:
- `element-out-of-section` (severity=error): textbox/shape bbox 가 component_id 로 link 된 leaf 의 가장 가까운 ancestor section/group bbox 외부로 8px 초과 빠져나감.
- `element-out-of-grid-cell` (severity=warning): textbox/shape 의 grid_cell 이 link 된 cell 의 region 분할 estimated bbox 외부로 16px 초과 빠져나감. design_doc.layout 의 cell_id 매칭 노드 bbox 가 더 정확하므로 보조 정보 수준.

### 결정 2 — layout-tree 구조 위반은 warning 이 아닌 error 로 격상

design/0011 결정 3 의 "구조적 사전 차단" 을 실질화하려면 다음 3 개 규칙은 *데이터 구조 결함* 이라 시각 결함보다 우선순위가 높다. modify_component 시 의미 영역을 잘못 가리키게 되어 부분 수정이 신뢰를 잃는다.

- `layout-tree-sibling-overlap`: 같은 부모 아래 형제 섹션 bbox 가 1px² 초과로 겹침
- `layout-tree-containment`: 자식 bbox 가 부모 bbox 외부로 빠져나감
- `layout-tree-canvas-overflow`: bbox 가 캔버스 [0,0,1280,720] 밖

`layout-tree-bbox-missing` 만 warning 유지 — LLM 이 의도적으로 bbox 를 nested 노드로 미루는 경우가 있음.

### 결정 3 — 단계적 lint 실행 (`stop_on_layer_error`)

`lint_slide_spec` 호출에 `stop_on_layer_error: bool = False` 인자를 추가한다. True 일 때 layout → section → cross → content 순서로 layer 별 검사를 순차 실행하고, 어느 layer 에 `severity="error"` 위반이 발견되면 *그 다음 layer 검사를 중단* 한다. 거시 위반을 먼저 보고하고 미시 노이즈로 가리지 않는다.

generate_slides_design_spec / modify_design_spec(action="update") / modify_component 의 lint 호출 지점이 이 옵션을 사용한다. 기본값은 False (기존 동작 유지).

부수적으로 `ALL_RULES` 를 layer 그룹 순서(layout → section → cross → content) 로 재정렬해, 호출자가 layer 별로 결과를 훑을 때 생성 파이프라인 순서와 일치시킨다.

### 결정 4 — generate 응답에 cross-layer error 가드

generate_slides_design_spec 결과에서 `severity="error"` & `layer="cross"` 위반이 발견되면 슬라이드별 결과에 `cross_layer_errors` 필드로 명시 노출한다. 자동 재시도는 비용 영향이 커서 본 ADR 에선 *경고만* 한다 — 자동 재생성 정책은 별도 ADR 에서 다룬다.

### 결정 5 — 외곽 정렬 lint (`slide-edge-alignment-*`)

같은 슬라이드 안에서 외곽에 가까이 배치된 element 들의 좌/우/상/하 변이 일치해야 시각적 일관성이 유지된다. 각 변의 *극값* 에서 16px 이내(cluster_threshold) 에 있는 element 들을 "외곽 cluster" 로 보고, 그 cluster 내 element 들의 해당 변이 4px 초과로 극값과 어긋나면 위반 (severity=warning). 장식 element(얇은 디바이더) 는 검사 제외.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| cross-layer 정합성을 prompt 가이드만으로 강제 | LLM 결함이 modify 단계에서 ValueError 로 늦게 터짐 |
| 모든 layer 를 항상 동시에 검사 (단계적 stop 없음) | 거시 위반이 미시 노이즈에 가려져 사용자가 우선순위를 가리기 어려움 |
| layout-tree 구조 위반을 warning 유지 | "구조적 차단" 약속이 사실상 안내 수준에 머물러 데이터 무결성을 깨는 LLM 출력이 통과 |
| cross-layer error 발견 시 자동 재시도 | 토큰/지연 비용 영향 큼 — 사용자 결정에 맡김 (별도 ADR 에서 다룸) |

## Consequences

### Positive

- 5단 계층의 link 정합성이 schema 직후 단계에서 잡힘 → modify 단계의 ValueError 회귀 방지.
- 단계적 lint 로 사용자가 거시 위반에 먼저 집중 가능 → 미시 노이즈에 매몰되지 않음.
- layout-tree 구조 위반 error 격상으로 modify_component 가 잘못된 element 를 가리키는 회귀 차단.
- 외곽 정렬 lint 로 슬라이드 전체 인지 품질이 보호됨.

### Negative / Risks

- `cross` layer 가 새로 늘어나 분류 가이드를 사람이 명시 판단해야 함 (애매한 규칙은 의미를 헷갈릴 수 있음).
- `stop_on_layer_error=True` 는 검사 누락처럼 *보일* 수 있어, 호출자가 거시 위반을 *해결* 한 뒤 다시 lint 를 돌려야 미시 위반을 본다 — UX 안내 필요.
- generate 응답에 cross_layer_errors 가 추가되면서 응답 schema 가 약간 커짐.

## References

- [design/0011 (design): 5단 디자인 스펙 계층](../design/0011-five-layer-design-spec-hierarchy.md)
- [design/0013 (design): 5단 계층 데이터 무결성](../design/0013-five-layer-data-integrity.md)
- [0003: Validator 를 Lint 로 전환](./0003-validator-to-lint.md) — 본 ADR 이 그 위에 cross-layer 정책을 더함
- [0004: 화살표·라벨 부착 검증 lint](./0004-arrow-label-attachment-lint.md) — cross layer 이전 사례
