# 생성 모델 Sonnet 5 전환 + adaptive thinking

Date: 2026-07-01

## Status

Accepted (verified 2026-07-01: 789 테스트 통과 + 실제 LLM end-to-end —
outline 3회 생성 성공, design spec complexity=5→effort=high 슬라이드 생성 성공.
outline native structured-output(400 회귀) 제거 후 프롬프트+수동 파싱으로 안정화.)

## Context

디자인 스펙 생성, outline 생성, Visual QA 수정(fix) 단계는 Sonnet 4.6을
extended thinking(`thinking: {type: "enabled", budget_tokens: N}`)으로 호출한다.
complexity(1-5)를 budget_tokens(4096/8192/12288)로 매핑해 슬라이드 난이도에 따라
thinking 예산을 조절하고, Visual QA fix는 고정 2048을 쓴다.

Sonnet 5로 올리려는 이유:
1. 코딩/에이전트 작업 품질이 Sonnet 4.6 대비 크게 향상됐고, 디자인 스펙은 정밀한
   좌표·레이아웃 설계라 이 향상의 수혜를 직접 받는다.
2. 도입 프로모션 가격(2026-08-31까지 $2/$10 per MTok)으로 비용 부담이 낮다.

단, Sonnet 5는 thinking·sampling API가 바뀌었다:
- `thinking: {type: "enabled", budget_tokens: N}`은 **400 에러**로 거부된다.
  budget_tokens는 완전히 제거됐다.
- 대신 `thinking: {type: "adaptive"}` + `output_config.effort`(low/medium/high/xhigh/max)로
  thinking 깊이를 제어한다. 모델이 작업 복잡도에 맞춰 thinking 양을 스스로 조절한다.
- `thinking` 필드를 생략하면 adaptive가 기본 적용된다(4.6은 thinking-off였음).
  따라서 thinking을 원치 않는 단계는 `thinking: {type: "disabled"}`를 명시해야 한다.
- non-default `temperature`/`top_p`/`top_k`도 **400 에러**로 거부된다. 기존 호출은
  `temperature=1.0`을 넘기고 있어 제거가 필요하다.

또한 outline 생성은 그동안 Bedrock Converse의 native structured-output 필드
(`outputConfig.textFormat` / Anthropic `output_config.format`)를 직접 주입해 JSON
스키마를 강제해왔다. Sonnet 5는 이 필드를 400(`output_config.format: Extra inputs
are not permitted`)으로 거부한다. 반면 design/review/visual-qa fix는 이미 strands의
tool-forcing 경로를 쓰거나 프롬프트+수동 파싱으로 JSON을 받으므로 영향이 없다.
Sonnet 5는 스키마 강제 없이도 프롬프트만으로 유효한 outline JSON을 안정적으로 생성한다.

따라서 단순 모델 ID 교체가 아니라, budget_tokens 기반 제어를 effort 기반 제어로
전환하고, outline의 native structured-output 주입을 제거하는 동작 변경이 필요하다.

## Decision

디자인 스펙·outline·Visual QA fix 생성 모델을 **Sonnet 5로 교체**하고,
extended thinking을 **adaptive thinking + effort**로 전환한다.
Bedrock·Anthropic 양쪽 프로바이더 모두 적용한다.

### complexity → effort 매핑

기존 complexity(1-5) → budget_tokens 매핑을 complexity → effort 매핑으로 대체한다.
슬라이드 난이도에 따라 thinking 깊이를 조절한다는 의도는 유지한다.

| complexity | 기존 budget_tokens | 신규 effort |
|---|---|---|
| 1-2 | 4096 | low |
| 3-4 | 8192 | medium |
| 5 | 12288 | high |

Visual QA fix는 기존 고정 2048(가장 낮은 예산)에 대응해 effort `low`로 고정한다.

### outline structured output

outline 모델에서 native structured-output 필드 주입을 제거하고, 프롬프트 지시 +
기존 수동 JSON 파싱/재시도 로직에만 의존한다. Sonnet 5가 스키마 강제 없이도 유효
JSON을 내므로 품질 손실은 없다. (더 엄격한 강제가 필요해지면 다른 서비스처럼
strands tool-forcing 경로로 통일하는 것이 후속 대안이다.)

### 모델 ID

- Bedrock: `global.anthropic.claude-sonnet-5`
- Anthropic: `claude-sonnet-5`

환경변수 오버라이드는 기존과 동일하게 유지한다.

### thinking 유지 대상

- outline: 기존 medium effort(outline/0003) 결정을 그대로 유지한다.
  budget_tokens 개념이 사라지므로 outline도 effort 기반(medium)으로 통일된다.
- Visual QA **분석(analysis)** 단계는 Haiku(visual-qa/0003)로 변경 없음.
  Haiku는 effort/adaptive를 지원하지 않으므로 thinking 미설정 유지.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| Sonnet 4.6 유지 | 요청 목적(품질 향상)에 미달 |
| Sonnet 5 + budget_tokens 유지 | Sonnet 5에서 400 에러로 불가능 |
| 모든 단계 effort 고정값 하나로 통일 | complexity별 thinking 예산 차등이라는 기존 의도(design/0003, outline/0004의 complexity 재산정) 상실 |
| Opus tier로 상향 | 비용 대비 과함. 디자인 스펙은 Sonnet 5 품질로 충분 |
| outline native structured-output 유지 | Sonnet 5가 400으로 거부 → 불가능 |
| outline을 tool-forcing으로 전환 | 견고하나, 수동 파싱이 이미 안정적이라 이번 범위엔 과함. 후속 대안으로 남김 |

## Consequences

### Positive

- 디자인 스펙 좌표·레이아웃 설계 품질 향상.
- adaptive thinking이 작업 복잡도에 맞춰 thinking 양을 자동 조절 → 단순 슬라이드는
  더 적게, 복잡한 슬라이드는 더 많이 thinking.

### Negative / 주의

- Sonnet 5는 새 토크나이저로 동일 텍스트의 토큰 수가 Sonnet 4.6 대비 ~30% 증가한다.
  토큰/비용 추적(project/0003)의 비용 추정 기준을 재보정해야 한다.
- effort 기본값은 high다. 저 complexity 슬라이드에 medium을 명시하지 않으면 latency·비용이
  기존보다 늘 수 있다 → 매핑으로 명시 제어.
- 프롬프트를 더 문자 그대로 따르므로, 기존 프롬프트가 4.6에 맞춰진 경우 출력 톤/장황함이
  달라질 수 있다. 실측 후 필요 시 별도 프롬프트 튜닝(본 ADR 범위 밖).
- thinking을 쓰지 않던 review/backfill 단계는 Sonnet 5에서 adaptive가 기본 on이 되지 않도록
  `thinking: {type: "disabled"}`를 명시한다.
- strands-agents를 adaptive thinking + output_config.effort pass-through가 검증된 최신
  버전으로 올린다. Bedrock은 additionalModelRequestFields, Anthropic은 params로 그대로 전달된다.
- adaptive thinking은 outline 응답 형식을 실행마다 흔들리게 한다(코드블록 유무, 다중 블록,
  산문 혼합). native structured-output 제거로 JSON 강제가 사라지므로, 응답에서 JSON 객체를
  뽑는 로직을 다중 후보(코드블록 → 최외곽 객체 → 전체) + slides 우선 방식으로 견고화해
  파싱 실패를 흡수한다.

## References

- outline/0003: outline medium thinking
- outline/0004: layout planning 단계의 complexity 재산정
- design/0003: 병렬 design spec 생성 (complexity → budget_tokens)
- visual-qa/0003: Visual QA 2-phase 모델 분리 (Haiku 분석 유지)
- project/0003: 토큰/비용 추정 (재보정 필요)
