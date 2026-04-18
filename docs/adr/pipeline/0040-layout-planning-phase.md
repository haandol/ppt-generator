# ADR-0040: 레이아웃 계획 단계 추가 (Layout Planning Phase)

Date: 2026-04-18

## Status

Proposed

## Context

현재 파이프라인: outline → script → design_spec

문제점:
1. design_spec 생성 시 다이어그램/요소 수를 사전에 모르고 바로 생성 → 복잡한 레이아웃에서 겹침/잘림 발생
2. component_hint만으로 복잡도를 결정하므로, 같은 hint라도 요소 수에 따라 실제 난이도가 다름
3. 다이어그램을 적극적으로 사용하도록 유도하는 메커니즘이 없음

## Decision

outline 이후, script 작성 전에 **레이아웃 계획(layout planning)** 단계를 추가한다.

### 파이프라인 변경

```
outline → layout_plan → script → design_spec
```

### Layout Plan 단계의 역할

1. **다이어그램 적극 활용 결정**: 내용이 시각화 가능한 경우 다이어그램(arch_diagram, process_flow, pipeline 등)을 적극 선택
2. **요소 수 사전 계산**: 각 슬라이드에 포함될 요소(노드, 화살표, 카드, 행/열 등)의 수를 미리 결정
3. **레이아웃 스케치**: 요소 배치 방향(가로/세로), 대략적인 영역 분할을 결정
4. **복잡도 재평가**: 요소 수 + 다이어그램 여부로 실제 complexity를 재산정 → budget_tokens 결정에 활용

### Layout Plan 출력 스키마 (안)

```json
{
  "slides": [
    {
      "slide_index": 1,
      "component_hint": "arch_diagram",
      "element_count": 7,
      "layout_direction": "horizontal",
      "regions": ["header", "diagram_area", "footer_note"],
      "complexity_override": 5,
      "reasoning": "3-tier 아키텍처 + 네트워크 연결선 → 노드 7개, 화살표 6개"
    }
  ]
}
```

### Thinking Budget 활용

- Layout plan 단계 자체는 medium budget (5120)으로 실행
- Layout plan 결과의 `complexity_override` 또는 `element_count` 기반으로 design_spec의 budget_tokens를 동적 결정:
  - element_count ≥ 6 또는 다이어그램 hint → high (10240)
  - element_count 3-5 → medium (5120)
  - element_count ≤ 2 → low (1024)

### 프롬프트 변경

- Outline 프롬프트: 다이어그램 사용을 적극 권장하는 가이드라인 추가
- Layout plan 전용 시스템 프롬프트: 요소 수/배치 계획에 집중

## Technical Details

### 구현 범위

1. `LayoutPlanService` 신규: outline을 입력받아 layout plan JSON 생성
2. `layout_plan` 아티팩트 저장: `project_dir/layout_plan/` 디렉토리
3. `generate_slides_design_spec` 핸들러: layout plan이 있으면 이를 참조하여 complexity → budget_tokens 결정
4. `ProjectService`: layout plan CRUD 메서드 추가
5. outline 프롬프트: 다이어그램 적극 사용 가이드라인 추가

### 하위 호환성

- layout_plan이 없는 기존 프로젝트는 현재처럼 component_hint 기반 complexity 사용 (fallback)
- MCP tool 추가: `generate_layout_plan(project_id)` — 선택적 호출 가능

## Consequences

- 다이어그램 활용도 증가 → 시각적 품질 향상
- 사전 레이아웃 계획으로 겹침/잘림 감소
- 파이프라인에 LLM 호출 1회 추가 → 비용/시간 증가 (medium budget이므로 제한적)
- 기존 프로젝트와의 하위 호환성 유지
