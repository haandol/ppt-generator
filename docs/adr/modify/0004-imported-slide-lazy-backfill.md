# Imported 슬라이드 design_doc lazy backfill

Date: 2026-05-26

## Status

Accepted

## Context

ADR-0001 (import) 의 임포트 파이프라인은 외부 PPTX 를 DesignSpec 으로 변환하지만, 임포트 결과 슬라이드는 design_doc / grid_plan / 모든 element 의 grid_cell·component_id 가 None 인 상태로 들어온다 (graceful fallback 정책). 이 상태에서는 ADR-0003 의 `modify_component` 가 design_doc.layout leaf 매칭에 의존하므로 사용 불가다. 사용자가 imported 슬라이드를 부분 수정하려면 `modify_design_spec(action="update")` 로 슬라이드 전체를 outline 기반 재생성해야 했고, 이는 imported 시각 자산의 "원본 보존" 가치를 깨뜨린다.

import 시점에 *모든* 슬라이드를 일괄 backfill 하는 것은 비합리적이다. 사용자가 안 만지는 슬라이드까지 LLM 호출이 들어가고(30 슬라이드 PPTX 면 30 회), 사용자가 즉시 결과를 보고 싶은 import 단계가 길어지며, 일부 backfill 실패 시 전체 import 재실행 부담이 크다.

## Decision

design_doc 를 import 시점이 아니라 **첫 modify_component 호출 시점에 해당 슬라이드 1 장만** lazy 로 추론한다. 추론 결과는 슬라이드 spec 에 영구 저장되어 다음 호출은 backfill 우회.

### modify_component 호출 시 자동 backfill

대상 슬라이드의 design_doc 가 None 이면:

1. **backfill 단계** — 슬라이드의 textbox/shape 목록을 LLM 에 전달, design_doc(topic / layout_summary / layout 트리) + 각 element 의 component_id 를 받는다.
2. **저장** — backfill 결과로 슬라이드 영구 저장. 다음 호출은 즉시 수정.
3. **component_id 검증** — 사용자가 호출 시 넘긴 component_id 가 backfilled tree 의 leaf 에 있으면 즉시 modify 진행. 없으면 `available_components` 목록을 응답에 포함하고 ValueError 대신 *경고 응답* 반환 (사용자가 적합한 id 를 골라 재호출).

처음 호출에서 사용자(LLM) 는 component_id 를 모르므로 통상 흐름은:
- 1 회차: dummy id 로 호출 → backfill 만 수행 + `available_components` 응답
- 사용자가 응답 보고 적합한 id 선택
- 2 회차: 정확한 component_id 로 호출 → 즉시 수정 (backfill 이미 됨)

이상적 경우 LLM 호출 총 2 회(backfill 1 + modify 1).

### backfill 추론 범위는 design_doc + component_id 만

backfill 이 채우는 것:
- design_doc.topic / layout_summary
- design_doc.layout 트리(section/group/component, role/description, parent_id 링크)
- 각 textbox/shape 의 component_id (트리 leaf 와 매칭)

backfill 이 채우지 *않는* 것:
- grid_plan / textbox·shape 의 grid_cell — imported PPTX 의 좌표가 격자에 정확히 맞을 보장이 없어 강제로 맞추면 layout/grid 계열 lint 가 대량 위반된다. None 유지.
- 슬라이드 본체(textbox/shape 의 위치/스타일/텍스트) — 원본 보존이 가치이므로 변경 금지.

이로써 backfill 결과는 5 단 계층 중 Section 계층만 채우고 Layout 계층은 비워둔다. 이 상태에서 layout-tree-bbox lint 만 의미가 있고, grid 계열 lint 는 grid_plan=None 슬라이드를 자동 스킵하도록 이미 설계되어 있다.

### bbox 는 코드 후처리, LLM 은 그룹화만

LLM 은 element 의 bbox 좌표를 직접 출력하지 않는다 — 픽셀 산수에 약하기 때문. LLM 은 의미 단위 section 묶음과 각 element 가 어느 section/component 에 속하는지 매핑만 출력한다. 코드는:

- 각 leaf component 의 bbox = 해당 element 의 bbox
- 각 group/section 의 bbox = 자식 bbox 의 axis-aligned 합집합 (post-order)

이 분담이 LLM 토큰 비용을 줄이고 결정성을 높인다.

### 실패 시 graceful fallback (트랜잭션)

backfill 이 실패(LLM throttle, parse error, schema violation) 하면:
1. 슬라이드 변경 없음 (design_doc=None 유지).
2. 명확한 에러 메시지 반환 — `modify_design_spec(action="update")` 사용 안내 포함.
3. 부분 성공(일부 element 만 component_id 채워짐) 은 허용하지 않음 — backfill 은 트랜잭션이라 전부 또는 전무.

### backfill 결과 영구 저장

backfill 결과는 슬라이드 spec 에 저장. 후속 modify_component 호출은 backfill 우회. 일관된 component_id(사용자가 메모해둘 수 있음), 비용 1 회만, modify 가 backfill 후 실패해도 design_doc 은 보존.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| import 시점 일괄 backfill | 사용자가 안 만지는 슬라이드까지 비용 발생 + import 지연 큼 + 부분 실패 시 재실행 부담 |
| LLM 이 bbox 좌표를 직접 출력 | LLM 픽셀 산수가 부정확 — 자식↔부모 bbox 정합성이 자주 깨짐 |
| backfill 결과를 메모리만 캐시 (저장 안 함) | 매 호출마다 backfill 비용 — 도구 호출 수가 늘어날수록 비효율 |
| grid_plan 도 함께 추론 | imported 좌표가 격자에 안 맞아 lint 대량 위반 위험. 본 ADR 범위 밖 |

## 하위 호환성

- import_pptx 자체는 변경 없음. design_doc=None 채로 들어옴.
- 사용자가 modify_component 를 안 부르면 backfill 도 안 일어남 — import 비용 0 추가.
- 이미 design_doc 가 채워진 슬라이드(generated 또는 이전 backfill 완료) 는 backfill 우회.

## Consequences

### Positive

- imported 슬라이드도 modify_component 사용 가능 → 5단 계층 가치 전파.
- 비용은 *실제 수정 시점에만* 발생, import 자체는 빠르게 유지.
- backfill 영구 저장으로 후속 호출은 즉시.
- 원본 슬라이드의 textbox/shape 좌표·스타일·텍스트 보존.

### Negative / Risks

- 첫 modify_component 호출이 round-trip 2 회 됨 — `available_components` 응답으로 완화.
- LLM 이 추론한 design_doc 트리 구조가 부자연스러울 수 있음 — instruction 으로 보정 가능하지만 큰 수정은 modify_design_spec(update) 가 더 적합.
- backfill 결과를 되돌릴 도구가 없음 — design_doc 만 추가되어 시각 출력에는 무영향이라 신뢰성 우려는 작음.

## Out of Scope

- import_pptx 시점 자동 backfill (본 ADR 의 결론과 정반대).
- imported 슬라이드의 grid_plan 추론 — 좌표 이산화/lint 충돌 위험.
- backfill 결과의 review/auto-fix — 사용자가 결과를 확인하고 instruction 으로 보정.

## References

- [ADR-0001 (import): PPTX 임포트 → 디자인 스펙](../import/0001-pptx-import-to-design-spec.md)
- [ADR-0011 (design): 5단 디자인 스펙 계층](../design/0011-five-layer-design-spec-hierarchy.md)
- [ADR-0003: modify_component MCP 도구](./0003-modify-component-mcp-tool.md)
