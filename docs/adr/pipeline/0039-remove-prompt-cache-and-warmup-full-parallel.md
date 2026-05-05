# 39. Prompt 캐시 제거 및 워밍업 없이 전체 병렬 실행

Date: 2026-05-05

## Status

Accepted

- Supersedes: [ADR-0018: 디자인 스펙 병렬 생성, 프롬프트 캐싱 및 Adaptive Effort](./0018-parallel-design-spec-and-prompt-caching.md) 중 "프롬프트 캐싱", "캐시 워밍업", "복잡도 기반 Adaptive Thinking Effort" 섹션
- Depends on: ADR-0018 의 ThreadPoolExecutor 기반 병렬 생성 구조는 그대로 유지

## Context

ADR-0018 이 채택한 prompt 캐싱 + 워밍업 구조가 실측에서 의도대로 동작하지 않는 것을 확인했다. Sonnet 4.6 으로 디자인 모델을 전환한 뒤 여러 차례 전체 생성(7 슬라이드)을 돌린 결과:

| 호출 | cacheWriteInputTokens | cacheReadInputTokens |
|------|----------------------|----------------------|
| 1차  | 81,103               | **0**                |
| 2차(실패 슬라이드만 재시도) | 36,895 | **0**                |
| 3차  | 118,255              | **0**                |

매 호출 쓰기 비용은 발생하지만 읽기 히트는 전혀 관측되지 않는다. 캐시 재사용이 이루어지지 않는 이유로 다음이 유력하다.

- Bedrock `CacheConfig(strategy="auto")` 의 cache key 가 `additionalModelRequestFields` 전체를 포함하는데, 같은 slide_type 이라도 병렬 생성 시점의 순서나 내부 agent 인스턴스 식별자로 인해 동일 prefix 로 인식되지 않을 가능성
- "첫 요청 완료 → 캐시 기록 → 이후 요청 재사용" 순서를 보장하기 위한 워밍업(slide_type 별 순차 실행)이 있지만, 실제로는 워밍업 직후에도 `cacheRead` 가 0 으로 찍힘 → 워밍업이 실효적이지 않음
- 워밍업이 실효적이지 않은 상태에서 **워밍업 슬라이드 수만큼 순차 대기 비용만 지불** 하고 있음

쓰기만 발생하고 읽기는 0 인 상황에서 캐싱을 유지하는 것은 비용(cache_write 는 input 대비 1.25× 단가)과 wall time(워밍업 순차 실행) 양쪽에서 손해다.

## Decision

캐시 관련 설정과 워밍업 로직을 모두 제거하고, 첫 요청부터 모든 슬라이드를 병렬 실행한다.

### 1. Bedrock 캐시 설정 제거

`BedrockModel` 생성자에서 `cache_config=CacheConfig(strategy="auto")` 인자를 모두 제거한다. 대상: design / outline / review / visual_qa / visual_qa_analysis 모델 5종.

```python
def create_bedrock_design_model() -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_DESIGN_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        temperature=1.0,
        max_tokens=BEDROCK_DESIGN_MAX_TOKENS,
        additional_request_fields={"thinking": {"type": "adaptive"}},
    )
```

### 2. Anthropic 쪽 `CachingAnthropicModel` 서브클래스 삭제

system prompt 를 `content block list` 로 감싸 `cache_control: {"type": "ephemeral"}` 를 주입하던 `CachingAnthropicModel` 래퍼를 삭제하고, 순수 `AnthropicModel` 을 직접 사용한다.

### 3. slide_type 별 워밍업 로직 제거

`parallel_runner.run_parallel_generation` 에서 워밍업 슬라이드를 뽑아 순차 실행하던 단계를 삭제한다. 첫 요청부터 `parallel_indices` 전체를 `ThreadPoolExecutor` 에 제출한다.

```python
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_idx = {
        executor.submit(_generate_slide, i): i for i in parallel_indices
    }
```

### 4. 관련 dead code 삭제

- `complexity_to_thinking_effort` 함수 (ADR-0018 의 "복잡도 기반 Adaptive Thinking Effort" 가 ADR-0038 커밋 이후 이미 제거되어, 남은 헬퍼도 정리)
- `CachingAnthropicModel` 전용 테스트 (`tests/test_caching_anthropic_model.py`)

`estimate_slide_complexity` 는 로깅용으로 유지한다.

## Consequences

### Positive

- **쓰기 비용 제거**: `cacheWriteInputTokens` 가 0 이 되어 input 대비 1.25× 단가로 과금되던 비용이 사라짐 (Sonnet 기준 직전 호출에서 약 $0.44 절감)
- **워밍업 순차 대기 제거**: 전체 슬라이드가 처음부터 병렬 실행되어 wall time 단축 (워밍업 슬라이드 개수 × 슬라이드 1개 생성 시간만큼)
- **구조 단순화**: `CacheConfig`, `CachingAnthropicModel`, `complexity_to_thinking_effort`, slide_type 별 워밍업 그룹핑 로직이 모두 사라져 유지보수 포인트 감소

### Negative

- **이론적 캐시 재사용 기회 포기**: Bedrock/Anthropic 의 prompt 캐시가 실제로 재사용되는 환경(예: 동일 세션 내 반복 호출, 더 긴 system prompt) 에서는 일부 토큰 비용을 놓칠 수 있음. 그러나 현재 워크로드에선 `cacheRead=0` 이 재현되었으므로 실효 손해는 없음
- **Anthropic 직접 API 에서 ephemeral 캐시 재활성화가 필요해지면** `CachingAnthropicModel` 을 git history 에서 복원해야 함

### 재도입 조건

아래 중 하나가 재현 가능하게 관측되면 재도입을 검토한다.

- 같은 프로젝트 내 반복 생성(`modify_design_spec` 등)에서 동일 system prompt 로 `cacheRead > 0` 이 일관되게 찍힘
- `strands` / Bedrock SDK 업데이트로 "cache key 가 `additionalModelRequestFields` 전체가 아닌 system prompt + model_id 만"으로 바뀜
- Sonnet 4.6 이상에서 adaptive thinking 과 prompt 캐시가 함께 동작하는 공식 가이드/샘플이 제공됨

## References

- 삭제된 구현:
  - `src/ppt_generator/di/model_factory.py` — `CachingAnthropicModel` 서브클래스 및 모든 `cache_config=CacheConfig(strategy="auto")` 인자
  - `src/ppt_generator/tools/design/parallel_runner.py` — warmup_indices 생성 / 순차 실행 블록
  - `src/ppt_generator/interfaces/utils.py` — `complexity_to_thinking_effort`
  - `tests/test_caching_anthropic_model.py`
- 관련 ADR: [0018-parallel-design-spec-and-prompt-caching](./0018-parallel-design-spec-and-prompt-caching.md), [0020-token-usage-tracking-and-cost-estimation](./0020-token-usage-tracking-and-cost-estimation.md)
