# ADR-0043: 디자인 스펙 생성 thinking을 adaptive에서 고정 budget으로 전환

Date: 2026-04-27

## Status

Accepted

## Context

디자인 스펙 생성 시 `thinking: {type: "adaptive"}`를 사용하고 있었다. `max_tokens=16384` (Sonnet 4.6 최대치)로 설정되어 있음에도, adaptive thinking이 예측 불가능하게 토큰을 소비하여 실제 JSON 출력에 할당 가능한 공간이 부족해지는 문제가 발생했다.

14개 슬라이드 생성 시 10개가 `MaxTokensReachedException`으로 실패한 사례가 확인되었다. Strands 에이전트가 `structured_output` (tool use 기반)으로 JSON을 출력하는데, thinking + JSON 합산이 16K를 초과하면 tool call이 잘리고 복구 시도 루프를 거쳐 최종 실패한다.

대안으로 고려한 방안들:
- **Opus 모델 사용 (max_output 32K)**: 실패 확률은 줄지만 비용이 5배 증가 ($2.85 → $14.22/프레젠테이션). 실패 시 손실도 5배.
- **thinking 완전 제거**: 디자인 품질 저하 우려.
- **thinking budget 고정**: thinking 토큰을 예측 가능하게 제한하여 JSON 출력 공간을 안정적으로 확보.

## Decision

`thinking: {type: "adaptive"}`를 `thinking: {type: "enabled", budget_tokens: N}`으로 전환한다. budget_tokens는 슬라이드 complexity에 따라 차등 적용한다.

| Complexity | 슬라이드 유형 예시 | budget_tokens | JSON 출력 여유 |
|---|---|---|---|
| Low (1-2) | title, closing, agenda | 1,024 | ~15K |
| Medium (3-4) | 일반 content | 2,048 | ~14K |
| High (5) | 복잡한 다이어그램/차트 | 4,096 | ~12K |

기존 `estimate_slide_complexity()` 함수와 `complexity_to_budget_tokens()` 함수를 재활용한다.

## Changes

- `src/ppt_generator/interfaces/utils.py`: `complexity_to_budget_tokens()` 값을 10240/5120/1024 → 4096/2048/1024로 변경.
- `src/ppt_generator/di/model_factory.py`: `create_bedrock_design_model()`, `create_anthropic_design_model()`에 `budget_tokens` 파라미터 추가. thinking type을 `adaptive` → `enabled`으로 전환.
- `src/ppt_generator/di/container.py`: `_create_design_agent()`, `create_design_service()`에 `budget_tokens` 파라미터 전달.
- `src/ppt_generator/interfaces/protocols.py`: `DesignServiceFactory` 프로토콜에 `budget_tokens` 파라미터 추가.
- `src/ppt_generator/tools/design/parallel_runner.py`: 슬라이드별 complexity 계산 후 `budget_tokens`를 팩토리에 전달.
- `src/ppt_generator/tools/design/handlers/modification.py`: 단일 슬라이드 생성/재생성 시 complexity 기반 budget_tokens 적용.
- `src/ppt_generator/tools/design/handlers/review.py`: 리뷰 후 재생성 시 complexity 기반 budget_tokens 적용.

## Consequences

- thinking 토큰 사용량이 예측 가능해져 `max_tokens` 초과로 인한 실패가 방지된다.
- 비용은 Sonnet 그대로 유지된다 (~$2.85/프레젠테이션).
- 복잡한 슬라이드에서 thinking 품질이 adaptive 대비 약간 저하될 수 있으나, 4096 budget이면 충분한 수준.
- 단순한 슬라이드는 thinking budget을 적게 할당하여 토큰 효율이 개선된다.
