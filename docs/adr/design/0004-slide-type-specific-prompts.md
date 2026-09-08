# 슬라이드 타입별 생성 계약

Date: 2026-02-25

## Status

Accepted (2026-09-08)

## Context

content 슬라이드의 반복 좌표와 예시는 title·closing 슬라이드의 중앙 배치보다 훨씬
많다. 모든 타입이 하나의 프롬프트와 응답 계약을 공유하면 클라이언트 모델은 content
패턴을 title·closing에도 적용하기 쉽다.

title·closing은 Layout과 Section 계층을 생략할 수 있지만 덱의 첫인상과 마무리를
담당하므로 DESIGN.md의 미학과 목적에 따라 여러 구성이 가능해야 한다. 반면 content는
Layout, Section, Content 계층의 연결을 제공해야 한다. 타입별로 필요한 의미 역할과
데이터 계약은 검증하되 특정 좌표 레시피를 저장 조건으로 만들면 유효한 디자인을
거부하게 된다.

## Decision Drivers

- title·closing과 content는 필수 계층과 레이아웃 자유도가 다르다.
- prepare가 반환한 응답 스키마와 ingest 검증은 같은 슬라이드 타입 계약을 사용해야 한다.
- title·closing의 의미 역할은 순서나 좌표와 독립적으로 식별되어야 한다.
- 발표자 정보가 없을 때 가짜 placeholder를 만들지 않아야 한다.
- 좌표, 타이포그래피와 장식은 렌더 안전 범위 안에서 DESIGN.md가 결정해야 한다.
- 슬라이드 타입별 분리는 content 예시가 특수 슬라이드 배치를 압도하는 문제를 줄여야 한다.

## Decision

디자인 스펙 생성 계약을 공통 베이스와 `content`, `title`, `closing` 타입별 계약으로
분리한다. prepare는 슬라이드 타입에 맞는 프롬프트와 응답 스키마를 반환하고, ingest는
같은 타입의 모델로 검증한다.

content는 Layout, Section, Content 연결 계약을 유지한다. title과 closing은 Layout과
Section을 생략할 수 있으며 의미 역할 기반 계약을 사용한다. 타입별 모델은 필수 역할,
역할 식별자의 유일성, 비어 있지 않은 필수 텍스트와 렌더 가능한 좌표 단위를 검증한다.
좌표·크기·정렬·글꼴 범위와 장식은 품질 guidance와 lint로 다룬다.

### Requirement contract

- 모든 좌표와 크기의 단위는 px이고, 글꼴 크기의 단위는 pt다.
- title은 비어 있지 않은 `title.main` 역할의 텍스트박스를 정확히 하나 포함한다.
- title은 `title.subtitle`과 `title.presenter` 역할을 각각 최대 하나 포함할 수 있다.
- 발표자 정보가 제공되지 않았으면 `title.presenter`를 생략하며 placeholder를 만들지 않는다.
- closing은 비어 있지 않은 `closing.message` 역할의 텍스트박스를 정확히 하나 포함한다.
- closing은 `closing.action`과 `closing.contact` 역할을 각각 최대 하나 포함할 수 있다.
- 역할은 element의 `component_id`로 표현하며 배열 순서는 의미를 결정하지 않는다.
- title·closing의 `grid_layout`, `cell_assignment`, `design_doc`은 선택 사항이다.
- 배경색은 null 또는 명시 색상을 허용하며 DESIGN.md의 배경 정책이 최종 선택을 지배한다.
- 모든 일반 요소는 캔버스 안에 있어야 한다. 로고 안전영역, 글꼴 크기, 정렬과 간격은
  lint 또는 Visual QA로 검토하며 ingest 거부 조건이 아니다.

Observable evidence: 역할이 다른 순서로 제공되거나 기존 고정 좌표와 다른 유효한 구성이
ingest를 통과한다. 필수 역할 누락, 역할 중복과 비어 있는 필수 텍스트는 저장 전에 거부된다.

## 대안 검토

| 대안 | 판단 |
|---|---|
| 모든 타입이 하나의 프롬프트와 응답 모델을 공유 | 계약은 단순하지만 content 패턴이 특수 슬라이드를 압도하고 타입별 필수 요소를 검증할 수 없어 제외 |
| 정확한 좌표와 요소 순서를 타입 계약으로 유지 | 재현성은 높지만 DESIGN.md의 시그니처와 유효한 구성을 거부해 제외 |
| 타입 구분 없이 공통 모델만 사용 | 역할 누락과 content 패턴 침투를 검증하기 어려워 제외 |
| 공통 베이스 + 타입별 역할 계약 | 타입별 의미를 보존하면서 좌표와 스타일 자율성을 유지해 채택 |

## Consequences

### Positive

- title·closing의 필수 의미 역할이 실행 가능한 계약이 된다.
- prepare와 ingest가 같은 슬라이드 타입 모델을 선택하므로 스키마 드리프트를 방지한다.
- 배열 순서와 좌표가 자유로워 DESIGN.md의 시그니처를 첫 장과 마지막 장에 적용할 수 있다.
- 발표자 정보가 없는 덱에 가짜 인적 정보가 나타나지 않는다.
- content 응답 모델은 특수 슬라이드 규칙과 분리되어 기존 계층 계약을 유지한다.

### Negative / Risks

- 역할 식별자를 누락한 기존 title·closing 생성 응답은 새 prepare schema에 맞춰 재생성해야 한다.
- 좌표 다양성이 늘어 실제 렌더 결함은 lint와 Visual QA가 더 중요해진다.
- 타입별 응답 모델이 늘어나므로 prepare/ingest 모델 선택의 일치 여부를 회귀 테스트로
  유지해야 한다.

## Related

- [디자인 스펙 품질 게이트](../lint/0003-validator-to-lint.md)
- [타이틀 슬라이드 긴 제목 텍스트 잘림 수정](./0005-title-long-title-overflow-fix.md)
- [5단 디자인 스펙 계층](./0011-five-layer-design-spec-hierarchy.md)
