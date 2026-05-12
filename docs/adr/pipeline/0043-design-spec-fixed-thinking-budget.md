# ADR-0043: 디자인 스펙 생성 thinking을 adaptive에서 고정 budget으로 전환

Date: 2026-04-27
Updated: 2026-05-12

## Status

Accepted

## Context

디자인 스펙 생성 시 `thinking: {type: "adaptive"}`를 사용하고 있었다. `max_tokens=64000` (Sonnet 4.6 최대치)로 설정되어 있음에도, adaptive thinking이 예측 불가능하게 토큰을 소비하여 실제 JSON 출력에 할당 가능한 공간이 부족해지는 문제가 발생했다.

7개 슬라이드 중 complexity=5인 슬라이드(3, 4번)에서 반복적으로 `MaxTokensReachedException`이 발생. Strands 에이전트가 `structured_output` (tool use 기반)으로 JSON을 출력하는데, thinking이 과도하게 토큰을 소비하면 tool call이 잘리고 복구 불가 상태에 빠진다.

## Decision

`thinking: {type: "adaptive"}`를 `thinking: {type: "enabled", budget_tokens: N}`으로 전환한다. budget_tokens는 슬라이드 complexity에 따라 차등 적용한다.

| Complexity | 슬라이드 유형 예시 | budget_tokens | JSON 출력 여유 |
|---|---|---|---|
| Low (1-2) | title, closing, agenda | 4,096 | ~60K |
| Medium (3-4) | 일반 content | 8,192 | ~56K |
| High (5) | 복잡한 다이어그램/차트 | 12,288 | ~52K |

기존 `estimate_slide_complexity()` 함수를 재활용하고, `complexity_to_budget_tokens()` 헬퍼로 매핑한다.

## Changes

**디자인 스펙 생성 (complexity 기반 차등):**
- `src/ppt_generator/interfaces/utils.py`: `complexity_to_budget_tokens()` 함수 추가 (4096/8192/12288 매핑).
- `src/ppt_generator/di/model_factory.py`: `create_bedrock_design_model()`, `create_anthropic_design_model()`에 `budget_tokens` 파라미터 추가. thinking type을 `adaptive` → `enabled`으로 전환.
- `src/ppt_generator/di/container.py`: `_create_design_agent()`, `create_design_service()`에 `budget_tokens` 파라미터 전달.
- `src/ppt_generator/interfaces/protocols.py`: `DesignServiceFactory` 프로토콜에 `budget_tokens` 파라미터 추가.
- `src/ppt_generator/tools/design/parallel_runner.py`: 슬라이드별 complexity 계산 후 `budget_tokens`를 팩토리에 전달.
- `src/ppt_generator/tools/design/handlers/modification.py`: 단일 슬라이드 생성/재생성 시 complexity 기반 budget_tokens 적용.

**아웃라인 생성 (고정 8K):**
- `create_bedrock_outline_model()`, `create_anthropic_outline_model()`: `adaptive` → `enabled, budget_tokens=8192`.
- 아웃라인도 JSON schema structured output을 사용하므로 동일한 문제 발생 가능.

**Visual QA fix (고정 2K):**
- `create_bedrock_visual_qa_model()`, `create_anthropic_visual_qa_model()`: `adaptive` → `enabled, budget_tokens=2048`.
- max_tokens=4096으로 작은 출력이므로 budget도 작게 설정.

## Rationale

Sonnet + structured_output (tool use 기반) 조합에서 adaptive thinking은 output 토큰을 예측 불가능하게 소비한다. Strands agent가 JSON tool call을 생성하다가 max_tokens에 도달하면 tool call이 잘리고, `_recover_message_on_max_tokens_reached` 복구를 시도하지만 결국 `MaxTokensReachedException`으로 실패한다. 이 문제는 structured output을 사용하는 모든 모델에 동일하게 적용되므로, 전체적으로 고정 budget을 사용한다.

## Consequences

- thinking 토큰 사용량이 예측 가능해져 `max_tokens` 초과로 인한 실패가 방지된다.
- 비용은 Sonnet 그대로 유지된다.
- 복잡한 슬라이드에서 thinking 품질이 adaptive 대비 약간 저하될 수 있으나, 12288 budget이면 충분한 수준.
- 단순한 슬라이드는 thinking budget을 적게 할당하여 토큰 효율이 개선된다.
