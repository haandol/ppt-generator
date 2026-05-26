# ADR-0051: Imported 슬라이드 design_doc lazy backfill

Date: 2026-05-26

## Status

Accepted (ADR-0049 Phase 3 — Out of Scope 였던 imported PPTX backfill 의 지연 실행 버전)

## Context

ADR-0027 은 외부 PPTX 파일을 DesignSpec 으로 임포트하는 파이프라인을 정의하고, ADR-0049
는 design_doc / component_id 의 graceful fallback 정책을 결정했다. 결과적으로 imported
슬라이드는 다음 상태로 들어온다:

- `grid_plan = None`
- `design_doc = None`
- 모든 textbox/shape 의 `grid_cell = None`, `component_id = None`

이 상태에서는 ADR-0050 의 `modify_component(component_id, instruction)` 도구를 사용할 수
없다. 사용자가 imported 슬라이드를 부분 수정하려면 `modify_design_spec(action="update")`
로 슬라이드 전체를 outline 기반 재생성해야 했고, 이는 imported 시각 자산의 "원본 보존"
가치를 깨뜨렸다.

import 시점에 모든 슬라이드를 일괄 backfill 하는 것은 다음 이유로 비합리적이다:
1. **불필요 비용**: 사용자가 안 만지는 슬라이드까지 LLM 호출이 들어간다 (PPTX 1 개에 30
   슬라이드면 30 회 호출).
2. **import 지연**: 사용자가 즉시 결과를 보고 싶은 import 단계가 길어진다.
3. **재시도 비용**: 일부 backfill 실패 시 전체 import 재실행이 부담.

본 ADR 은 backfill 을 **수정 시점에 해당 슬라이드에 한정해 수행** 하는 lazy 전략을 채택한다.

## Decision

### 결정 1 — modify_component 호출 시 자동 backfill

`modify_component(project_id, slide_index, component_id, instruction, ...)` 가 호출되었을 때,
대상 슬라이드의 `design_doc` 이 None 이면 다음 순서로 처리한다:

1. **backfill 단계**: 해당 슬라이드의 textbox/shape 목록을 LLM 에 전달하고, design_doc
   (topic / layout_summary / layout 트리) + 각 element 의 component_id 를 받는다.
2. **저장 + 응답 메타**: backfill 결과로 슬라이드를 저장한다 (이 시점부터 다음 호출은
   backfill 없이 바로 수정 가능).
3. **component_id 검증**: 사용자가 호출 시 넘긴 `component_id` 가 backfilled design_doc
   에 존재하면 즉시 수정으로 진행. 없으면 `available_components` 목록을 응답에 포함하여
   ValueError. 사용자(LLM) 가 재호출하면 됨.

```
modify_component
  ├ load slide
  ├ if design_doc is None:
  │     backfill_design_doc(slide)  ← LLM call #1
  │     save slide
  │     if user component_id ∉ design_doc.layout: return error with available_components
  ├ modify element                  ← LLM call #2
  └ save / lint / render
```

처음 호출에서 사용자(LLM)는 component_id 를 모르므로, 통상 흐름은:
- 1 회차: `modify_component(component_id="(unknown)", instruction="...")` 호출 →
  backfill 만 수행, component_id 매칭 실패 → 응답에 `available_components` 포함
- 사용자가 응답을 보고 적합한 component_id 선택
- 2 회차: 동일 도구를 정확한 component_id 로 호출 → 즉시 수정 (backfill 이미 됨)

이 흐름은 명확하고 재시도 비용이 적다. backfill 이 한 번만 일어나는 이상적인 경우 LLM
호출 총 2 회 (backfill 1 + modify 1).

### 결정 2 — backfill 추론 범위는 design_doc + component_id

backfill 이 채우는 것:
- `design_doc.topic`, `design_doc.layout_summary`
- `design_doc.layout`: section/group/component 트리 (bbox + role + description, parent_id 링크)
- 모든 textbox/shape 의 `component_id` (트리 leaf 와 매칭)

backfill 이 채우지 *않는* 것:
- `grid_plan`: imported PPTX 의 실제 좌표가 격자에 정확히 맞을 보장이 없다. 강제로
  맞추면 layout/grid 계열 lint 가 대량 위반된다. 본 ADR 에서는 `grid_plan = None` 유지.
- 각 textbox/shape 의 `grid_cell`: 위와 동일 이유로 None 유지.
- 슬라이드 본체 (textbox/shape 의 위치/스타일/텍스트): 원본 보존이 가치이므로 변경 금지.

이로써 backfill 결과는 ADR-0049 5 단 계층 중 Section 계층만 채우고 Layout 계층은 비워둔다.
이 상태에서 `layout-tree-bbox` lint 만 의미가 있고 `grid-plan-required` 등 격자 계열
lint 는 design_doc 트리 검사 흐름과 무관하다 (rule 자체가 grid_plan=None 슬라이드를
스킵하도록 이미 구현되어 있다 — section 슬라이드 type 만 검사 대상).

### 결정 3 — backfill 입력은 textbox/shape JSON, LLM 은 추론만

LLM 에게는 다음을 준다:
- 슬라이드의 textbox/shape 목록 (좌표 + 텍스트 + 스타일)
- canvas 크기 (1280x720)

LLM 은 다음을 추론하여 출력한다:
- 의미 단위 section 묶음 (예: 좌측 카드 그룹 vs 우측 다이어그램)
- 각 element 가 어느 section/component 에 속하는지 매핑 (component_id)
- bbox 는 직접 추론하지 않고 *element bbox 의 합집합* 또는 *section 영역 minimal bounding box* 사용

bbox 계산은 코드에서 후처리한다 (LLM 이 픽셀 산수에 약함):
- LLM 은 component 노드별 element index 매핑만 출력
- 각 leaf component 의 bbox = 해당 element 의 bbox
- 각 group/section 의 bbox = 자식 bbox 의 합집합 (axis-aligned)

이는 LLM 토큰 비용을 줄이고 결정성을 높인다.

### 결정 4 — 실패 시 graceful fallback

backfill 이 실패 (LLM throttle, parse error, schema violation) 하면:
1. 슬라이드를 변경하지 않는다 (design_doc=None 유지).
2. 명확한 에러 메시지 반환 — `modify_design_spec(action="update")` 사용 안내 포함.
3. 부분 성공 (일부 element 만 component_id 채워짐) 은 허용하지 않는다 — backfill 은 트랜잭션.

### 결정 5 — backfill 결과 저장 시점

backfill 결과는 슬라이드 spec 에 *영구 저장* 한다. 다음 modify_component 호출에서는
backfill 을 다시 하지 않는다. 이로써:
- 일관된 component_id (사용자가 메모해둘 수 있음)
- 비용 1 회만 (재호출 무료)
- modify_component 가 backfill 후 실패하더라도 design_doc 은 보존 — 다음 시도는 즉시
  수정으로 시작

## Technical Details

### 영향 범위

- **interfaces/llm_output_models.py**
  - `BackfillDesignDocOutput` Pydantic 모델 신설:
    - `topic: str`
    - `layout_summary: str`
    - `sections: list[BackfillSection]`
      - `id`, `parent_id`, `kind`, `role`, `description`
      - `element_indices`: 자식 component 가 참조하는 textbox/shape 의 (kind, index) 목록
      - `children: list[str]` (자식 노드 id, parent_id 와 별도로 LLM 이 명시)
    - LLM 은 element 의 bbox 좌표를 직접 출력하지 않는다 (코드에서 계산)

- **interfaces/prompts/backfill_design_doc_system.prompt.md** (신규)
- **interfaces/prompts/backfill_design_doc_user.prompt.md** (신규)
- **interfaces/constants.py**: 신규 prompt 상수 등록
- **tools/design/service.py**
  - `DesignService.backfill_design_doc(spec)` 추가
  - 헬퍼 `_compute_node_bboxes()` (post-order 로 leaf bbox 부터 위로 합집합)
  - 헬퍼 `_link_components_to_elements()` (LLM 출력의 element_indices → 실제 element 의
    component_id 채우기)
- **tools/design/handlers/modification.py**
  - `handle_modify_component` 에 backfill 분기 추가:
    - `if spec.design_doc is None:` → `svc.backfill_design_doc(spec)` 호출, 슬라이드 저장
    - 이후 backfilled spec 에서 component_id 매칭 시도. 매칭 실패면 `available_components`
      목록 + `lint_suggestion` 비슷한 안내 텍스트 응답에 포함하여 ValueError 대신 *경고
      응답* 반환 (사용자가 즉시 재호출 가능하도록).
- **tests/test_modify_component.py** 또는 신규 `test_backfill_design_doc.py`
  - imported 슬라이드 (design_doc=None) 에 modify_component 호출 시 backfill 호출됨
  - backfill 후 slide 가 영구 저장되어 다음 호출에 반영
  - LLM 가 산출한 component_id 매칭 실패 시 available_components 응답
  - bbox 후처리: leaf bbox = element bbox, group/section bbox = 자식 합집합
  - backfill 실패 (LLM 예외) → design_doc=None 유지 + 명확한 에러

### 흐름 의사코드

```python
def handle_modify_component(deps, ..., component_id, instruction):
    spec = load(slide)
    if spec.design_doc is None:
        try:
            spec = svc.backfill_design_doc(spec)
        except Exception as exc:
            raise ValueError(f"backfill 실패: {exc}. modify_design_spec(action='update') 사용 권장.")
        save(slide, spec)  # 영구 저장

    if not _has_component(spec, component_id):
        return _response_with_available_components(spec, component_id)

    new_spec = svc.modify_component(spec, component_id, instruction)
    save(slide, new_spec)
    render_html
    lint
    return ok_response
```

### Acceptance Criteria

1. design_doc=None 슬라이드에 modify_component 호출 → backfill 자동 실행되고 spec 에 영구 저장.
2. backfill 후 design_doc.layout 은 모든 textbox/shape 에 매칭되는 component leaf 포함.
3. group/section bbox 는 자식 bbox 의 합집합과 일치 (단위 테스트로 검증).
4. component_id 가 backfilled tree 에 없으면 응답에 `available_components` 포함, ValueError 발생 안 함 (재호출용).
5. 이미 design_doc 있는 슬라이드에서는 backfill 우회.
6. backfill 실패 시 spec 변경 없음 + ValueError + modify_design_spec 안내.
7. backfill 후 동일 슬라이드 두 번째 modify_component 호출은 backfill 호출 없음 (1 회만).
8. 회귀 없음 — 기존 import_pptx, modify_design_spec 동작 유지.
9. grid_plan 은 None 그대로 유지 (강제 backfill 안 함).

### Out of Scope

- import_pptx 시점 자동 backfill — 비용·지연 이슈 (본 ADR 결론).
- imported 슬라이드의 grid_plan 추론 — 좌표 이산화/lint 충돌 위험. 별도 ADR.
- backfill 결과의 review/auto-fix — 사용자가 결과를 확인하고 instruction 으로 보정.
- backfill 결과 캐시/버전 관리 — design_doc 은 spec 내부 필드라 슬라이드 저장이 곧 캐시.

## Consequences

긍정적:
- imported 슬라이드도 ADR-0050 modify_component 사용 가능 → 5 단 계층 가치 전파
- 비용은 *실제 수정 시점에만* 발생 — import 자체는 빠르게 유지
- backfill 영구 저장으로 후속 modify 호출은 즉시
- 원본 슬라이드의 textbox/shape 좌표/스타일/텍스트 보존 (textbox/shape 변경 안 함)

부정적/리스크:
- 첫 modify_component 호출이 두 단계 (backfill + 매칭 실패 응답) 가 되어 round-trip 2 회
  소요 — `available_components` 응답 메커니즘으로 완화 (사용자가 한 번 더 호출하면 됨)
- LLM 추론한 design_doc 트리 구조가 부자연스러울 수 있음 — instruction 으로 보정 가능
  하지만 큰 수정은 modify_design_spec(update) 가 더 적합
- backfill 결과 저장 후 사용자가 마음에 안 들어도 되돌릴 도구 없음 — 일단은 design_doc
  필드만 추가되므로 시각 출력에는 무영향, 사용자 신뢰성 우려 적음

## References

- [ADR-0027: PPTX 임포트 to design_spec](./0027-pptx-import-to-design-spec.md)
- [ADR-0049: 5단 디자인 스펙 계층](./0049-five-layer-design-spec-hierarchy.md)
- [ADR-0050: modify_component MCP 도구](./0050-modify-component-mcp-tool.md)
