# 토큰 사용량 추적 및 비용 추정

Date: 2026-02-23

## Status

Accepted

## Context

슬라이드 생성 파이프라인은 여러 LLM 호출(아웃라인, 스크립트, 디자인 요약, 슬라이드별 디자인 스펙)을 수행하며, 각 호출의 토큰 소비량과 전체 비용을 파악할 수 없었다. 사용자가 프레젠테이션 생성에 들어가는 비용을 사전에 인지하지 못하는 문제가 있었다.

### 해결해야 할 문제

1. **가시성 부족**: 각 도구 호출에서 몇 토큰이 소비되었는지 확인할 수 없음
2. **비용 추정 불가**: 디자인 스펙 생성 완료 후 전체 파이프라인에 소요된 예상 비용을 알 수 없음
3. **캐시 효율 확인 불가**: 프롬프트 캐싱이 실제로 작동하는지 확인할 방법이 없음

## Decision

### 1. 서비스 레이어: `last_token_usage` 프로퍼티

모든 LLM 호출 서비스(`OutlineService`, `ScriptService`, `DesignService`)에 `last_token_usage: dict[str, int]` 프로퍼티를 추가한다. `log_token_usage()` 헬퍼가 strands SDK의 `result.metrics.accumulated_usage`에서 토큰 정보를 추출하여 INFO 로깅과 동시에 서비스 인스턴스에 저장한다.

### 2. 컨트롤러 레이어: 응답에 `token_usage` 포함

- `generate_outline`, `generate_script`: 응답 JSON에 `token_usage` 필드 포함
- `generate_slides_design_spec`: 모든 슬라이드의 토큰을 합산하여 `token_usage` + `estimated_cost` 포함

### 3. 가격 계산: `estimate_cost()`

`interfaces/utils.py`에 모델별 가격표(`_MODEL_PRICING`)와 Bedrock 모델 ID 별칭(`_MODEL_ID_ALIASES`)을 정의하여, 토큰 사용량과 모델 ID로 예상 비용(USD)을 계산한다. `inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheWriteInputTokens` 각각 별도 단가를 적용한다.

## Consequences

### 장점

- 각 도구 호출의 토큰 소비량이 응답에 포함되어 MCP 클라이언트에서 바로 확인 가능
- 디자인 스펙 생성 완료 시 전체 비용이 표시되어 사용자가 비용을 인지할 수 있음
- 캐시 토큰(cache_read, cache_write)이 별도 추적되어 캐싱 효율을 확인 가능
- 가격 테이블이 코드에 내장되어 있어 별도 API 호출 없이 즉시 계산

### 단점

- 가격 변경 시 `_MODEL_PRICING` 딕셔너리를 수동으로 업데이트해야 함
- 새 모델 추가 시 `_MODEL_ID_ALIASES` 매핑도 함께 추가 필요

## Related

- [design/0003 (design): 병렬 디자인 스펙 생성 및 프롬프트 캐싱](../design/0003-parallel-design-spec.md)
- [design/0003 (design): 디자인 스펙 병렬 생성, 프롬프트 캐싱 및 Adaptive Effort](../design/0003-parallel-design-spec.md) (복잡도 기반 스케줄링 및 Adaptive Thinking Effort 포함)
