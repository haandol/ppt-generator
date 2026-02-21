# 19. 슬라이드 복잡도 기반 스케줄링 및 Adaptive Thinking Effort

Date: 2026-02-21

## Status

Accepted

## Context

[ADR-0018](./0018-parallel-design-spec-and-prompt-caching.md)에서 도입한 `ThreadPoolExecutor` 기반 병렬 처리는 슬라이드를 순차 인덱스 순서(0, 1, 2, ...)로 thread pool에 제출한다. 그러나 슬라이드별 LLM 생성 시간은 레이아웃 복잡도에 따라 크게 차이난다.

### 해결해야 할 문제

1. **비효율적 스케줄링**: `arch_diagram`이나 `process_flow` 같은 복잡한 슬라이드가 뒤에 제출되면, 마지막 워커가 혼자 오래 걸리는 작업을 처리하면서 다른 워커들은 idle 상태. 전체 wall-clock time이 가장 긴 작업에 의해 결정됨.
2. **일률적 thinking effort**: 단순한 `bullets`/`quote` 슬라이드에도 복잡한 `arch_diagram`과 동일한 `high` thinking effort를 사용하여 불필요한 토큰 소비 및 지연 발생.

### 복잡도 차이 근거

| 유형 | 예시 component_hint | LLM이 해야 할 작업 |
|------|-------------------|-------------------|
| 단순 | bullets, quote, agenda | 텍스트 배치, 불릿 포인트 |
| 중간 | step_cards, code_block, two_column | 다수 카드/도형 배치, 2칼럼 레이아웃 |
| 복잡 | arch_diagram, process_flow, pipeline | 블록+화살표+커넥터, 2칼럼+다이어그램, 공간 추론 |

## Decision

### 1. 결정론적 복잡도 추정 (LLM 예측 불필요)

`component_hint` + `content_summary` 길이로 복잡도 점수를 결정론적으로 산출한다. LLM 호출이나 프롬프트/스키마 변경이 불필요하다.

```python
# interfaces/constants.py
COMPONENT_HINT_COMPLEXITY: dict[str, int] = {
    "arch_diagram": 10,  # 블록+화살표, 공간 추론 최다
    "process_flow": 9,   # 2칼럼+플로우 다이어그램
    "pipeline": 8,       # 순차 흐름+커넥터
    "concept_list": 8,   # 2칼럼: 텍스트+다이어그램
    "quote_code": 7,     # 2칼럼: 인용문+코드
    "vs_comparison": 7,  # 2패널 비교
    "summary_grid": 7,   # 2x2 그리드
    "step_cards": 6,     # 다수 카드 도형
    "info_cards": 6,     # 카드 그리드
    "code_block": 5,     # 모노스페이스 코드 영역
    "two_column": 5,     # 2칼럼 텍스트
    "feature_list": 4,   # 구조화된 리스트
    "agenda": 3,         # 단순 번호/불릿
    "cta": 3,            # 단순 CTA
    "bullets": 2,        # 가장 단순
    "quote": 1,          # 단일 인용문
}

# interfaces/utils.py
def estimate_slide_complexity(slide: SlideOutline) -> int:
    if slide.slide_type in ("title", "closing"):
        return 1  # 템플릿 배경, 단순 레이아웃
    base = COMPONENT_HINT_COMPLEXITY.get(slide.component_hint, 2)
    content_bonus = min(len(slide.content_summary) // 200, 3)
    return base + content_bonus  # 범위: 1~13
```

- `title`/`closing` 슬라이드: 고정 1점 (템플릿 배경, 단순 레이아웃)
- `content_summary` 길이 보너스: 200자당 +1 (최대 +3)
- 알 수 없는 `component_hint`: 기본값 2 (`bullets`와 동일)

### 2. Longest-Job-First 스케줄링

thread pool에 슬라이드를 제출할 때 복잡도 내림차순으로 정렬한다.

```python
parallel_indices = sorted(
    indices,
    key=lambda i: estimate_slide_complexity(outline.slides[i]),
    reverse=True,
)
```

이 방식은 스케줄링 이론의 **LPT(Longest Processing Time first)** 규칙에 해당하며, 동일 수의 워커에서 makespan(전체 완료 시간)을 최소화하는 근사 전략이다.

### 3. 복잡도 기반 Adaptive Thinking Effort

복잡도 점수에 따라 LLM의 thinking effort를 동적으로 조절한다.

| 복잡도 범위 | thinking_effort | 대상 |
|------------|-----------------|------|
| 7~13 (high) | `high` | arch_diagram, process_flow, pipeline 등 |
| 4~6 (medium) | `medium` | step_cards, code_block, two_column 등 |
| 1~3 (low) | `low` | title, closing, bullets, quote, agenda 등 |

```python
def complexity_to_thinking_effort(complexity: int) -> str:
    if complexity >= 7:
        return "high"
    elif complexity >= 4:
        return "medium"
    else:
        return "low"
```

`DIContainer.create_design_service(thinking_effort)` 팩토리가 effort를 필수 인자로 받아 해당 effort 설정의 Agent를 생성한다. `generate_slides_design_spec`과 `modify_design_spec` 모두에서 `design_service_factory(effort)`를 통해 adaptive effort가 적용되며, 싱글톤 `design_service`와 환경변수 `DESIGN_THINKING_EFFORT`는 제거되었다.

### 4. 도메인 모델 변경 없음

복잡도는 `SlideOutline` 등 도메인 모델에 추가하지 않고, 스케줄링 시점에 on-the-fly로 계산한다. 프롬프트, JSON 스키마, LLM 출력 모델 등은 변경하지 않는다.

## Consequences

### Positive

- **Wall-clock time 단축**: 복잡한 슬라이드가 먼저 시작되어 워커 idle time 감소
- **토큰 비용 절감**: 단순 슬라이드에 `low` effort를 사용하여 thinking 토큰 절약
- **품질 유지**: 복잡한 슬라이드는 여전히 `high` effort로 충분한 추론 수행
- **비침습적**: 프롬프트, 스키마, 도메인 모델 변경 없음. 기존 동작과 완전 호환

### Negative

- **복잡도 추정 오차**: `component_hint` 기반 정적 매핑이므로, 같은 hint라도 실제 내용에 따라 난이도가 다를 수 있음. `content_summary` 길이 보너스로 일부 보완
- **Effort 차이에 따른 품질 편차**: `low` effort 슬라이드의 품질이 `high`보다 낮을 수 있으나, 단순 레이아웃에서는 충분

### Risks

- thinking effort `low`가 단순 슬라이드에서도 품질 저하를 유발하면 매핑 테이블 조정이 필요 (코드 변경만으로 조절 가능, LLM 재학습 불필요)

## References

- 복잡도 매핑: `src/ppt_generator/interfaces/constants.py` — `COMPONENT_HINT_COMPLEXITY`
- 복잡도 추정/변환 함수: `src/ppt_generator/interfaces/utils.py` — `estimate_slide_complexity()`, `complexity_to_thinking_effort()`
- 팩토리 시그니처: `src/ppt_generator/di/container.py` — `create_design_service(thinking_effort)`
- 스케줄링 적용: `src/ppt_generator/tools/design/controller.py` — `parallel_indices` 정렬, `_generate_slide()` effort 전달
- 테스트: `tests/test_complexity.py`
- 관련 ADR: [0018-parallel-design-spec-and-prompt-caching](./0018-parallel-design-spec-and-prompt-caching.md)
