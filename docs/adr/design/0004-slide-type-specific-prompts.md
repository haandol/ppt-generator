# 슬라이드 타입별 생성 계약

Date: 2026-02-25

## Status

Accepted (2026-08-29)

## Context

content 슬라이드의 반복 좌표와 예시는 title·closing 슬라이드의 중앙 배치보다 훨씬
많다. 모든 타입이 하나의 프롬프트와 응답 계약을 공유하면 클라이언트 모델은 content
패턴을 title·closing에도 적용하기 쉽다.

title·closing은 Layout과 Section 계층을 생략할 수 있는 고정 레이아웃이다. 반면 content는
Layout, Section, Content 계층의 연결을 모두 제공해야 한다. 타입별로 다른 필수 필드와
고정 좌표를 프롬프트 지시만으로 유지하면, 클라이언트가 지시를 어긴 결과도 ingest에서
저장될 수 있다.

## Decision Drivers

- title·closing과 content는 필수 계층과 레이아웃 자유도가 다르다.
- prepare가 반환한 응답 스키마와 ingest 검증은 같은 슬라이드 타입 계약을 사용해야 한다.
- 프롬프트의 절대 좌표와 필수 요소는 ingest에서 결정론적으로 검증되어야 한다.
- title의 두 줄 제목은 높이와 후속 요소 위치가 함께 바뀌어야 한다.
- 슬라이드 타입별 분리는 content 예시가 특수 슬라이드 배치를 압도하는 문제를 줄여야 한다.

## Decision

디자인 스펙 생성 계약을 공통 베이스와 `content`, `title`, `closing` 타입별 계약으로
분리한다. prepare는 슬라이드 타입에 맞는 프롬프트와 응답 스키마를 반환하고, ingest는
같은 타입의 모델로 검증한다.

content는 Layout, Section, Content 연결 계약을 유지한다. title과 closing은 Layout과
Section을 생략할 수 있지만, 아래 고정 레이아웃 요구사항을 만족해야 한다. 타입별 모델은
필수 요소, 순서, 좌표와 글꼴 범위를 검증하고 위반 결과를 저장 전에 거부한다.

### Requirement contract

- 모든 좌표와 크기의 단위는 px이고, 글꼴 크기의 단위는 pt다.
- title은 `background_color`를 비워 두고, main title, subtitle, presenter info
  텍스트박스를 이 순서로 포함한다.
- title main title의 bbox는 `(64, 260, 1152, 80)` 또는 `(64, 260, 1152, 160)`이고,
  vertical alignment는 middle이며, 비어 있지 않은 글꼴은 40~44pt이고 굵게 표시한다.
- title divider는 rectangle이고 bbox는 main title 높이가 80px이면
  `(64, 350, 80, 4)`, 160px이면 `(64, 430, 80, 4)`다.
- title subtitle의 bbox는 main title 높이가 80px이면 `(64, 370, 1152, 100)`,
  160px이면 `(64, 450, 1152, 100)`이고, vertical alignment는 top이며,
  비어 있지 않은 글꼴은 14~18pt다.
- title presenter info의 bbox는 `(64, 560, 400, 96)`이고, 이름·직책·소속을 각각
  하나의 비어 있지 않은 문단으로 제공하며, vertical alignment는 bottom이고 모든
  글꼴은 18pt다.
- closing은 `background_color`를 비워 두고, thank-you message와 Q&A subtitle
  텍스트박스를 이 순서로 포함한다.
- closing thank-you message의 bbox는 `(64, 260, 1152, 80)`이고, 비어 있지 않은
  글꼴은 40~44pt이며 굵게 표시하고 vertical alignment는 middle이다.
- closing divider는 rectangle이고 bbox는 `(64, 350, 80, 4)`다.
- closing Q&A subtitle의 bbox는 `(64, 370, 1152, 60)`이고, 비어 있지 않은 글꼴은
  16~20pt이며 vertical alignment는 top이다.
- closing contact/summary를 포함하면 세 번째 텍스트박스로 제공하고 bbox는
  `(64, 450, 1000, 120)`, vertical alignment는 top, 비어 있지 않은 글꼴은
  14~16pt다.

Observable evidence: 각 타입의 정상 예시는 ingest를 통과한다. 필수 요소 누락, 순서 변경,
좌표·크기·글꼴 범위 위반, title presenter info의 3문단 규칙 위반은 저장 전에 거부된다.
title main title이 160px이면 divider와 subtitle도 두 줄 제목용 좌표를 사용한다.

## 대안 검토

| 대안 | 판단 |
|---|---|
| 모든 타입이 하나의 프롬프트와 응답 모델을 공유 | 계약은 단순하지만 content 패턴이 특수 슬라이드를 압도하고 타입별 필수 요소를 검증할 수 없어 제외 |
| 프롬프트만 타입별로 분리하고 공통 모델로 검증 | 생성 품질은 개선하지만 절대 좌표와 필수 요소 위반을 저장 전에 막지 못해 제외 |
| 공통 베이스 + 타입별 프롬프트 + 타입별 검증 모델 | 프롬프트와 ingest가 같은 계약을 사용하고 타입별 오류를 결정론적으로 거부하므로 채택 |

## Consequences

### Positive

- title·closing의 필수 요소와 고정 좌표가 프롬프트 권고가 아니라 실행 가능한 계약이 된다.
- prepare와 ingest가 같은 슬라이드 타입 모델을 선택하므로 스키마 드리프트를 방지한다.
- 두 줄 title에서 main title, divider와 subtitle의 상대 위치가 함께 검증된다.
- content 응답 모델은 특수 슬라이드 규칙과 분리되어 기존 계층 계약을 유지한다.

### Negative / Risks

- 기존에 고정 레이아웃을 따르지 않은 title·closing 생성 결과는 ingest에서 거부된다.
- 고정 좌표나 필수 요소를 바꾸려면 이 요구사항 계약과 검증 모델을 함께 변경해야 한다.
- 타입별 응답 모델이 늘어나므로 prepare/ingest 모델 선택의 일치 여부를 회귀 테스트로
  유지해야 한다.

## Related

- [디자인 스펙 품질 게이트](../lint/0003-validator-to-lint.md)
- [타이틀 슬라이드 긴 제목 텍스트 잘림 수정](./0005-title-long-title-overflow-fix.md)
- [5단 디자인 스펙 계층](./0011-five-layer-design-spec-hierarchy.md)
