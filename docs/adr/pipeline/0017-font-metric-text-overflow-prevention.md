# 17. 폰트 메트릭 기반 텍스트 오버플로우 방지

Date: 2026-05-26

## Status

Accepted

## Context

LLM 이 생성한 디자인 스펙은 텍스트가 박스보다 커서 두 가지 시각 결함을 일으키기 쉽다.

1. **세로 오버플로우** — 박스 너비 안에서 텍스트가 몇 줄로 줄바꿈되는지 사전에 모르면 박스 높이가 텍스트를 다 담지 못한다. 한글은 Latin 대비 글자당 폭이 ~1.6 배 넓어 동일 글자 수에서 줄바꿈이 훨씬 자주 일어나 회귀가 잦다.
2. **가로 오버플로우** — PPT 시스템 폰트(맑은 고딕/Consolas) 메트릭과 브라우저 웹 폰트(Noto Sans KR/Source Code Pro) 메트릭이 다르다. 박스에 *거의* 들어맞는 라벨은 한 줄 강제 시 브라우저에서 박스 좌우를 뚫고, 두 줄 wrap 허용 시 박스 height 가 늘어 옆/아래 요소 좌표를 어긋나게 한다.

두 결함은 *반대 방향* 으로 작용한다. 한 줄 강제(nowrap)를 후하게 적용하면 가로 오버플로우가, 좁게 적용하면 세로 wrap 회귀가 늘어난다. 정확도 게임 (단일 tolerance 값) 으로는 양쪽 모두를 만족시킬 수 없다.

## Decision

폰트 파일을 직접 로드하지 않고 `unicodedata` 만 사용한 **추정 기반 측정 모듈** 을 둔다. 측정 결과를 spec 단계와 렌더링 단계 양쪽에서 활용해 두 오버플로우를 분리해 다룬다.

### 측정 모듈

`interfaces/text_measurement.py` 가 외부 의존성 없는 순수 함수로 다음을 제공한다.

- 글자별 폭 추정: 한글·전각 0.9, Latin 0.55, monospace 0.6 비율 (font_size_pt × 1.333 × ratio).
- run/paragraph 단위 폭 합산.
- paragraph 의 줄바꿈 수 → 필요 height 산출.
- shape 의 padding 차감 후 가용 폭으로 wrap 계산.

추정 비율은 *보수적* 으로 잡는다 — 추정값이 실제값보다 작게 나올 가능성을 가로 오버플로우 차단으로 흡수하지 않고, 안전 마진(아래)으로 흡수한다.

### 세로 오버플로우 — spec 단계 검증

디자인 스펙 lint 가 `text-overflow` 규칙으로 paragraph 의 줄바꿈 수 × line height 합산값과 박스 height 를 비교한다 (15% 여유 허용). shape 가 `autofit_mode="shrink_text"` 인 경우 (ADR-0049 결정 14) 폰트 자동 축소가 height 부족을 자연 흡수하므로 검사 대상에서 제외한다.

### 가로 오버플로우 — 렌더링 단계 nowrap 보정 + lint 안전망

렌더러는 paragraph 단위로 `should_apply_nowrap_to_paragraph` 를 호출해, 추정 폭이 박스 가용 폭의 `TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO = 0.95` 이하일 때만 `white-space:nowrap` 을 적용한다. 즉 **5% 안전 마진**을 명시적으로 남긴다. 이 값은 다음 두 부작용 중 더 치명적인 *가로 오버플로우* 를 0 에 가깝게 누르는 쪽으로 정한 결정이다.

- nowrap 후하게 (예: 1.15) → 짧은 라벨이 한 줄로 잘 보이지만 박스를 뚫는 케이스가 누적.
- nowrap 좁게 (0.95) → 95~115% 구간 paragraph 가 두 줄로 wrap (박스 height 가 expand_height 로 늘어나 콘텐츠 자체는 보존).

운영 노트: 메트릭 차이로 *짧은* 라벨이 wrap 되는 케이스가 드물게 있으면 spec 단계에서 박스 폭을 살짝 키워 해결한다. tolerance 를 다시 키워 정확도 게임으로 돌아가지 않는다.

bullet(`<li>`) 항목에는 nowrap 을 적용하지 않는다 — bullet 본문은 wrap 이 자연스럽고, 다이어그램 라벨에서 bullet 을 쓰는 사례가 없기 때문이다.

추가 안전망으로 lint 규칙 `nowrap-overflow` 가 paragraph 마다 `should_apply_nowrap_to_paragraph` 결과를 시뮬레이션해, nowrap 이 적용될 paragraph 의 추정 폭이 가용 폭을 초과하면 warning 을 발행한다. 향후 tolerance 가 다시 느슨해지거나 다른 경로로 nowrap 이 적용되는 회귀를 사전에 잡는다.

### 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| 프롬프트만으로 줄바꿈 정확화 | LLM 의 글자 단위 폭/wrap 계산 정확도 한계, 보장 안 됨 |
| 한국어 20 자·영어 40 자 같은 고정 라인 한도 | 폰트 크기·박스 폭 조합을 반영 못함 |
| 1.05 같은 중간 tolerance | 가로 오버플로우와 세로 wrap 회귀를 *모두* 일부 허용해 양쪽 다 못 막음 |
| 실제 폰트 파일 로드한 정밀 메트릭 | OS/환경 의존성 발생, 측정 모듈의 휴대성을 깸 |

## Consequences

### Positive

- 한글 등 CJK 텍스트의 세로 오버플로우가 줄바꿈 수 반영으로 사전 방지.
- 가로 오버플로우(박스를 뚫고 좌우로 글자 튀어나감) 가 0.95 안전 마진으로 차단.
- spec 단계 (lint) + 렌더링 단계 (nowrap 게이트) + 사후 검증 (nowrap-overflow lint) 의 삼중 안전망.
- 외부 의존성 0 — `unicodedata` 표준 라이브러리만 사용.

### Negative / Risks

- 폰트 메트릭이 *추정치* 라 실제 렌더링과 차이가 발생할 수 있음 (보수 추정 + 5% 안전 마진으로 완화).
- 박스 폭 95~115% 구간 paragraph 는 두 줄로 wrap 된다. PPT 와 브라우저에서 줄 수가 다를 수 있으나 콘텐츠 자체는 보존되며, 좌우 오버플로우 대비 시각 충격이 훨씬 작다.
- 다이어그램 노드 라벨처럼 한 줄을 강하게 원하는 경우 LLM 이 박스 폭을 넉넉히 잡거나 폰트를 줄여 자율 조정해야 한다 — 프롬프트에 강제 규칙으로 박지 않는다.

## References

- [ADR-0013](./0013-design-spec-pipeline.md) — 디자인 스펙 파이프라인에서 lint 의 위치
- [ADR-0023](./0023-design-spec-validator.md) (Superseded by 0041) → [ADR-0041](./0041-validator-to-lint.md) — Lint 의 일반 정책
- [ADR-0049](./0049-five-layer-design-spec-hierarchy.md) 결정 14 — autofit shrink_text 기본값
