# ADR-0050: modify_component MCP 도구 — Section 단위 부분 수정

Date: 2026-05-26

## Status

Accepted (ADR-0049 Phase 2 — Out of Scope 항목의 첫 구현)

## Context

ADR-0049가 5단 디자인 스펙 계층(Project / Slide / Layout / Section / Content)을 정의하면서
얻은 핵심 가치는 **Section 트리의 component_id로 의미 단위 요소를 정확히 지칭할 수 있다**는
점이다. 그러나 ADR-0049는 그 가치를 사용자가 직접 호출할 수 있는 MCP 도구로 노출하지 않은
채 Out of Scope (Phase 2)로 미뤘다.

현재 `modify_design_spec(action="update")`는 슬라이드 전체를 outline 기반으로 재생성한다.
이 방식은 다음 문제를 가진다.

1. **부분 변경에 과도한 비용**: "좌측 두 번째 카드 색을 빨간색으로" 같은 좁은 명령에도
   슬라이드 전체 LLM 재호출이 일어나 토큰·시간을 낭비한다.
2. **다른 요소가 의도치 않게 변경됨**: 전체 재생성이라 LLM이 매번 같은 결과를 낸다는
   보장이 없다. 다이어그램·카드 위치·색이 미세하게 흔들린다.
3. **5단 계층의 식별성 미활용**: design_doc.layout 트리와 component_id 링크는 이미 있지만
   사용자 명령이 그 식별자를 거치지 않으므로, 계층의 핵심 가치가 사용되지 않는다.

본 ADR은 `modify_component(project_id, slide_index, component_id, instruction)` MCP 도구를
도입해, design_doc 트리 leaf 1개를 지목한 부분 수정을 LLM에게 명시적으로 위임한다.

## Decision

다음 5가지 결정으로 모듈을 구성한다.

### 결정 1 — MCP 도구 시그니처

```python
modify_component(
    project_id: str,
    slide_index: int,            # 1-based
    component_id: str,           # design_doc.layout 의 leaf id
    instruction: str,            # 자연어 수정 지시
    color_theme: str = "dark",
) -> str  # JSON
```

응답 JSON:

```json
{
  "project_id": "...",
  "slide_index": 1,
  "component_id": "right_diagram.llm_box",
  "modified_element": {"type": "shape", "index": 3},  // 변경된 element 의 종류 + 0-based index
  "slide_html_path": "...",
  "lint": { ... },           // 단일 슬라이드 lint (위반 있을 때만)
  "token_usage": {...},
  "estimated_cost": {...}
}
```

### 결정 2 — LLM 입력은 슬라이드 전체 + 대상 component_id

LLM 호출 시 다음을 컨텍스트로 전달한다:

- 슬라이드 전체 spec (background_color, grid_plan, design_doc, textboxes, shapes)
- 대상 `component_id`
- 사용자 `instruction`
- color_theme

이 방식은 토큰 비용이 단순 element-only 방식보다 약간 크지만, 다음을 가능하게 한다:
- 형제 노드의 색·폰트·크기와 정렬 유지 (디자인 일관성)
- 같은 cell 내 다른 element 와 충돌 회피
- design_doc 트리 구조 인식한 bbox 조정

### 결정 3 — 단일 component 만 수정 (v1)

한 호출당 정확히 1 개의 component_id 를 받는다. 다중 component (예: "3개 카드 모두
색 통일") 는 LLM 이 호출자에게 여러 번의 modify_component 호출로 풀어내거나, 또는
기존 update action 사용을 안내한다. 다중 수정은 v2 검토 항목.

이유: API/구현이 단순해지고, 부분 수정의 명확성 (한 번에 한 곳) 이 디버그성 면에서
우월하다. ADR-0049 Out of Scope 문구 "modify_component(component_id, instruction)" 와
형식적으로 일치한다.

### 결정 4 — 수정 가능 범위: Content + 대상 leaf bbox

LLM 이 수정할 수 있는 것:
1. **대상 leaf 의 textbox/shape 본체** (텍스트, 색, 폰트, 패딩, alignment, 모양 등)
2. **대상 leaf 의 bbox** (left_px / top_px / width_px / height_px)
3. **대상 leaf 의 design_doc.layout 노드의 bbox** (textbox/shape bbox 와 동기화)

수정 *불가*한 것:
- design_doc 트리 구조 (노드 추가/삭제/parent 변경)
- 다른 component 의 spec
- grid_plan
- background_color
- speaker_notes
- 다른 슬라이드

이 범위는 lint 가 자연스럽게 강제한다:
- `layout-tree-containment` — 수정된 leaf bbox 가 부모 section bbox 를 벗어나면 fail
- `layout-tree-sibling-overlap` — 형제 leaf 와 겹치면 fail
- `grid-cell-coverage` 등 격자 lint — grid_plan 변경 없으므로 자연 통과
- `font-range`, `text-overflow`, `zero-size-shape` 등 content lint — 통상대로

구조 변경 (트리 재구성, 노드 추가) 이 필요한 변경은 기존 `modify_design_spec(action="update")`
또는 향후 Phase 3 도구를 사용한다.

### 결정 5 — 후처리: lint 재검증 + 자동 HTML 재렌더 + step 갱신

수정 직후:
1. 변경된 슬라이드만 `lint_slide_spec` 으로 재검증. 위반 있으면 응답 JSON 의 `lint` 필드에
   포함하여 호출자(LLM)가 추가 호출을 결정할 수 있게 한다 (재생성은 자동으로 하지 않는다).
2. 단일 슬라이드 HTML 을 `slides_service.render_single_slide_html` 로 재렌더하고
   `slide_html_path` 반환.
3. `project_service.update_step(project_dir, "design_spec_modified")` 호출 — 기존 modify
   파이프라인과 동일.

## Technical Details

### 영향 범위

- **interfaces/llm_output_models.py**
  - `ComponentModifyOutput` Pydantic 모델 신설:
    - `element_kind: Literal["textbox", "shape"]`
    - `textbox: TextBoxOutput | None`
    - `shape: ShapeOutput | None`
    - `bbox_changed: bool`
  - 헬퍼 `to_textbox_dataclass()`, `to_shape_dataclass()` (기존 `_convert_paragraphs` 재사용)

- **interfaces/prompts/component_modify_system.prompt.md** (신규)
  - 5단 계층 인식, 대상 component_id 외 변경 금지, bbox-first 원칙
  - 출력 스키마

- **interfaces/prompts/component_modify_user.prompt.md** (신규)
  - 슬라이드 spec JSON, 대상 component_id, instruction, color_theme

- **interfaces/constants.py**
  - `COMPONENT_MODIFY_SYSTEM_PROMPT`, `COMPONENT_MODIFY_USER_PROMPT_TEMPLATE` 등록

- **tools/design/service.py**
  - `DesignService.modify_component(spec, component_id, instruction, color_theme)` 추가
  - structured_output 으로 `ComponentModifyOutput` 받고, 슬라이드 spec 의 해당 element 만
    교체한 새 PptxSlideSpec 반환
  - 기존 `_generate_with_structured_output` 패턴 재사용

- **tools/design/handlers/modification.py**
  - `handle_modify_component(deps, project_id, slide_index, component_id, instruction, color_theme)` 추가
  - 흐름: load spec → service.modify_component → lint → save spec → render html → update step
  - 기존 `_generate_and_review` 와는 별개 경로 (review_service 호출 안 함 — 부분 수정에 과함)

- **tools/design/controller.py**
  - `@mcp.tool() modify_component(...)` 등록
  - docstring 에 ADR-0050 언급, 후속 export_html 안내 (자동 single-slide html 은 즉시 반환)

- **tests/test_design_controller.py** 또는 신규 `test_modify_component.py`
  - component_id 매칭 시 element 만 변경되는지 (다른 element 보존)
  - leaf bbox 가 design_doc 노드 bbox 와 동기화되는지
  - 존재하지 않는 component_id → ValueError
  - design_doc 없는 슬라이드 (title/closing) → 명확한 에러
  - lint 위반 응답 포함 확인

### 구현 순서

1. Pydantic `ComponentModifyOutput` + 헬퍼
2. system/user prompt md 파일
3. constants 등록
4. DesignService.modify_component
5. handle_modify_component
6. controller @mcp.tool 등록
7. 테스트
8. 버전 bump (0.6.5 → 0.7.0 — 신규 MCP 도구 추가는 minor bump)

### Element 매칭 로직

```python
def _find_element_by_component_id(spec, component_id):
    for i, tb in enumerate(spec.textboxes):
        if tb.component_id == component_id:
            return ("textbox", i, tb)
    for i, s in enumerate(spec.shapes):
        if s.component_id == component_id:
            return ("shape", i, s)
    raise ValueError(f"component_id not found: {component_id}")
```

design_doc.layout 의 leaf 매칭 (bbox 동기화용) 은 트리 재귀 탐색 — 단순 helper.

### bbox 동기화

LLM 응답이 `bbox_changed=True` 면:
1. 새 textbox/shape 의 bbox 를 가져옴
2. design_doc.layout 트리에서 동일 id 의 LayoutNode 찾아 `dataclass.replace(left_px=, top_px=, width_px=, height_px=)`
3. 부모 트리는 재귀 재구성 (frozen dataclass 라 path 따라 replace 체인)

### 하위 호환성

- 기존 `modify_design_spec(action="update")` 는 그대로 유지. 사용자가 큰 변경(트리 구조,
  여러 element) 을 요청하면 기존 도구를 안내한다.
- design_doc 없는 슬라이드(title/closing)는 modify_component 미지원. 명확한 에러 메시지로
  `modify_design_spec(action="update")` 를 안내.
- imported PPTX 슬라이드는 design_doc=None 이라 미지원. ADR-0049 결정 5의 graceful
  fallback 정책과 일치.

### Acceptance Criteria

1. content 슬라이드의 textbox component 1개를 instruction 으로 변경 시 그 element 만 수정되고 다른 textbox/shape 는 byte-equal 보존됨 (단위 테스트로 검증).
2. shape component 변경 시 동일.
3. component_id 가 design_doc 에 없으면 `ValueError`.
4. design_doc=None 슬라이드(title/closing/imported) 에서 호출 시 명확한 에러 메시지.
5. bbox_changed=True 응답 처리 시 design_doc.layout 트리의 동일 id 노드 bbox 가 element bbox 와 일치.
6. 수정 후 단일 슬라이드 lint 결과가 응답에 포함 (위반 있을 때).
7. 수정 후 single slide HTML 이 재렌더되고 path 가 응답에 포함.
8. `steps_completed` 에 `design_spec_modified` 가 갱신.
9. 회귀 없음 — 기존 modify/move/review/generate 동작 그대로.

### Out of Scope

- 다중 component 동시 수정 (`component_ids: list[str]`) — v2 검토
- design_doc 트리 구조 변경 (노드 추가/삭제/parent 이동) — 별도 ADR
- review_service 자동 재호출 — 부분 수정은 review 비용 대비 이득 작음
- imported PPTX 의 design_doc 자동 backfill — ADR-0049 Out of Scope 그대로

## Consequences

긍정적:
- **부분 수정 비용 감소**: 슬라이드 전체 재생성 대비 LLM 토큰·시간 절감 (실측은 구현 후 확인)
- **결정성 향상**: 대상 외 element 가 byte-equal 보존되어 사용자 신뢰 상승
- **5단 계층 가치 실현**: ADR-0049 가 정의한 component_id 식별성을 사용자 인터페이스까지 노출
- **lint 의 구조적 보장**: 기존 layout-tree-* 규칙이 자연스럽게 부분 수정의 안전망 역할

부정적/리스크:
- LLM 이 대상 외 element 를 (명시 금지에도 불구하고) 변경하려 시도할 경우 응답 처리 로직이 무시해야 함 — Pydantic 응답 모델이 단일 element 만 받도록 강제하므로 자연 차단
- bbox 동기화 로직 결함 시 design_doc 트리와 element 가 불일치 → lint 가 즉시 잡지만 사용자가 보는 직전 결과는 어색 가능
- 기존 도구(`modify_design_spec`)와 사용 시점 분기를 사용자(LLM) 가 잘못 선택할 위험 → tool docstring 에 명확한 분기 가이드 명시

## References

- [ADR-0014: 파일 기반 통신 + 슬라이드별 CRUD](./0014-file-based-communication-and-per-slide-crud.md)
- [ADR-0028: modify_design_spec inline outline](./0028-modify-design-spec-inline-outline.md)
- [ADR-0049: 5단 디자인 스펙 계층](./0049-five-layer-design-spec-hierarchy.md)
