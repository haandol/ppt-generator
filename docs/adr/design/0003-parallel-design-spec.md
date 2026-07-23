# 디자인 스펙 병렬 생성 — Worker 스케줄링 + Thinking Budget

Date: 2026-05-26

## Status

Superseded by [ADR offload/0001](../offload/0001-client-llm-offload-plugin.md)

디자인 스펙 생성의 LLM 호출이 클라이언트로 오프로딩되면서 서버측 ThreadPoolExecutor
병렬 생성·워커 스케줄링·고정 thinking budget 강제는 제거되었다. 서버 API 는 슬라이드
단위 prepare/ingest 로 stateless 해졌고, 여러 슬라이드를 동시에 진행하는 병렬성은
클라이언트가 담당한다. thinking budget 은 이제 강제값이 아니라 prepare 응답에 실리는
힌트다. 아래 내용은 오프로딩 이전의 기록이다.

## Context

디자인 스펙 생성은 슬라이드당 1 회 LLM 호출(Claude Sonnet 4.6) 이 필요하다. 10 장 기준 순차 처리는 수 분이 걸려 사용자 대기 시간이 크다. 또한 LLM 호출에는 다음 두 가지 제약이 동시에 작용한다.

1. **각 호출의 토큰 예산** — Strands 의 structured_output (tool use 기반) 은 JSON tool call 생성 도중 `max_tokens` 에 도달하면 tool call 이 잘려 복구 불가 상태(MaxTokensReachedException) 가 된다. thinking 토큰을 *예측 가능*하게 둬야 JSON 출력 공간이 보장된다.
2. **호출 간 wall time** — 단순 슬라이드(`bullets`/`agenda`/`title`/`closing`) 와 복잡 슬라이드(`arch_diagram`/`process_flow`) 의 처리 시간이 크게 차이 나, 짧은 작업이 먼저 끝난 워커가 idle 로 남으면 전체 makespan 이 늘어난다.

과거에는 prompt 캐싱(Bedrock `CacheConfig(strategy="auto")` + Anthropic ephemeral cache_control) 과 캐시 워밍업(slide_type 별 첫 호출을 순차 선행) 으로 wall time 단축을 시도했으나, 운영 실측에서 `cacheWriteInputTokens` 만 발생하고 `cacheRead = 0` 이 일관되게 재현됐다 (Sonnet 4.6 이후 cache key 가 `additionalModelRequestFields` 전체를 반영). 쓰기 비용(input 단가의 1.25×) + 워밍업의 순차 대기 비용만 누적돼 실효 손해. 또 thinking 을 `adaptive` 로 두니 JSON 출력 공간이 들쭉날쭉해 MaxTokensReached 가 반복 발생.

## Decision

**전체 슬라이드를 첫 호출부터 병렬 실행**하고, 워커 스케줄링은 **결정론적 복잡도 추정 + LPT** 로, thinking 은 **고정 budget** 으로 둔다. prompt 캐싱과 워밍업은 사용하지 않는다.

### 1. ThreadPoolExecutor 기반 전체 병렬 생성

`generate_slides_design_spec` 도구가 슬라이드 전체 인덱스를 첫 요청부터 ThreadPoolExecutor 에 한 번에 제출한다. 환경변수 `DESIGN_SPEC_PARALLEL` (기본 8) 로 동시 워커 수를 조절하고, 실제 워커 수는 `min(DESIGN_SPEC_PARALLEL, 대상 슬라이드 수)`. 부분 실패 허용 — 일부 슬라이드가 실패해도 나머지는 정상 저장되며, 실패 슬라이드는 `slide_indices` 파라미터로 재시도.

### 2. 워커별 독립 Agent 인스턴스

Strands `Agent` 는 내부에 대화 히스토리 등 상태를 가져 스레드 간 공유가 안전하지 않다. DI 컨테이너의 design_service 팩토리가 호출될 때마다 새 `Agent` + `DesignService` 인스턴스를 생성하고, 각 워커가 호출하여 독립 인스턴스를 사용한다.

### 3. 메타데이터 동시 쓰기 보호

프로젝트 메타데이터(`project.json`) 는 read-modify-write 패턴이라 `threading.Lock` 으로 보호한다. 슬라이드 spec 파일은 슬라이드 인덱스별로 독립이라 별도 Lock 불필요.

### 4. 결정론적 복잡도 추정 + Longest-Job-First (LPT)

`component_hint` + `content_summary` 길이로 복잡도 점수를 산출 (제목·closing 슬라이드는 항상 1 점). `arch_diagram`/`process_flow`/`pipeline` 같은 다이어그램 류가 가장 높고, `bullets`/`quote` 가 가장 낮다. content_summary 길이로 200 자당 +1 보너스 (최대 +3).

LPT 전략: ThreadPool 에 제출할 때 복잡도 내림차순으로 정렬해 makespan 을 줄인다. `arch_diagram` 같은 무거운 작업이 먼저 picked-up 되어 마지막 워커가 혼자 늦게 끝나는 케이스를 방지.

### 5. Thinking 고정 Budget (complexity 차등)

`thinking: {type: "enabled", budget_tokens: N}` 을 사용한다 (adaptive 미사용). N 은 complexity 에 차등:

| Complexity | budget_tokens | JSON 여유 (max_tokens 64K 기준) |
|---|---|---|
| Low (1~2) — title/closing/agenda | 4,096 | ~60K |
| Medium (3~4) — 일반 content | 8,192 | ~56K |
| High (5+) — 복잡한 다이어그램/차트 | 12,288 | ~52K |

Outline 생성도 structured output 을 쓰므로 같은 문제가 발생 — 고정 8K. Visual QA fix 는 max_tokens 가 작아 고정 2K.

### 6. Prompt 캐싱·워밍업 미사용

Bedrock `CacheConfig` 와 Anthropic ephemeral cache_control 을 사용하지 않는다. 운영 실측에서 cacheRead 가 일관되게 0 으로 찍혀 쓰기 비용만 누적됐기 때문 (cache key 산정 정책의 문제로 추정 — Sonnet 4.6 의 `additionalModelRequestFields` 전체가 키에 포함됨). 워밍업도 마찬가지로 효과 없는 순차 대기였다.

### 재도입 조건 (캐싱)

다음 중 하나가 재현 가능하게 관측되면 prompt 캐싱 재도입을 검토한다.

- 같은 프로젝트 내 반복 호출에서 동일 system prompt 로 cacheRead > 0 가 일관되게 찍힘.
- Strands / Bedrock SDK 업데이트로 cache key 가 system prompt + model_id 만으로 좁혀짐.
- Sonnet 4.6 이상에서 adaptive thinking + prompt cache 가 함께 동작하는 공식 가이드/샘플 제공.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| Adaptive thinking 유지 | structured_output 과 결합 시 토큰 소비 예측 불가 → MaxTokensReachedException 빈발 |
| Prompt 캐싱 + 워밍업 유지 | 실측에서 cacheRead=0 재현, 쓰기 비용 + 워밍업 순차 대기만 추가 |
| 슬라이드 인덱스 순서 그대로 제출 (FIFO) | 무거운 슬라이드가 뒤에 와 마지막 워커가 혼자 오래 걸려 makespan 비효율 |
| 슬라이드 1 회 LLM 호출을 다단으로 분할 | 토큰 호출 수 증가, 지연 증가, 단일 호출의 self-conditioning 효과 손실 (점진적 추상화 출력 정책과 충돌) |

## Consequences

### Positive

- 첫 호출부터 전체 병렬 실행으로 워밍업 순차 대기 제거 → wall time 단축.
- LPT 로 makespan 균형 — 무거운 슬라이드 먼저 시작.
- 캐시 쓰기 비용 0 — Sonnet 기준 호출당 약 $0.4 절감 사례 측정.
- Thinking 토큰 예측 가능 → JSON 출력 공간 보장 → MaxTokensReached 차단.

### Negative / Risks

- 이론적 캐시 재사용 기회 포기 (현재 워크로드에서는 실효 손해 없음 — 위 재도입 조건 참조).
- Adaptive thinking 대비 복잡 슬라이드의 thinking 품질이 약간 저하 가능 (12K budget 으로 충분 검증).
- Anthropic 직접 API 에서 ephemeral 캐시 재활성화가 필요해지면 caching 모델 래퍼를 다시 추가해야 함 (git history 에서 복원).

## References

- [project/0003](../project/0003-token-usage-cost-estimation.md) — 토큰/비용 측정으로 캐시 효과를 실측한 근거
- [project/0004](../project/0004-progress-reporting-and-logging.md) — 병렬 실행 진행률 보고
- [project/0005](../project/0005-mcp-server-stability.md) — ThreadPoolExecutor + future timeout 안정성
- [0011](./0011-five-layer-design-spec-hierarchy.md) — 단일 LLM 호출 유지 결정 (점진적 추상화 + Section 계층)
