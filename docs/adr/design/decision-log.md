# Decision Log: design

This document is the **major decision-change history** of the design category. Each
ADR body describes only the current state, while the timeline of "what changed and why"
accumulates here, newest first. Git preserves the individual diffs.

## 2026-09-09 — 호환성을 보존하고 유효한 반복 구성을 허용

- **Current ADRs**: [디자인 리뷰](./0008-design-spec-post-generation-review.md),
  [DESIGN.md 단일 소스](./0015-design-md-source-of-truth.md),
  [배경 이미지 정책](./0016-design-md-background-policy.md),
  [DESIGN.md taste](./0018-design-md-taste-in-pipeline.md)
- **Change type**: requirement rule change and compatibility repair
- **What**: 동일 구성 3장의 사용을 강제 위반에서 검토 신호로 바꾸고 설명 목적이 있는
  반복을 허용한다. 기본 배경 이미지는 기존 동작을 유지하며 단색은 명시된 정책으로
  선택한다. 인라인 초안의 검증 입력을 보존하고 이동한 페이지 요청을 함께 재배치한다.
- **Why**: 정상 입력과 기존 덱 외형을 지키면서 불필요한 구성 변경과 요청 오적용을 막기 위해.

## 2026-09-09 — 덱 리뷰에 실제 구성과 디자인 의도를 연결

- **Current ADR**: [디자인 리뷰](./0008-design-spec-post-generation-review.md)
- **Change type**: requirement rule change
- **What**: 힌트·화면 문구 중심 검토에서 실제 배치·관계·발표자 노트·디자인 의도를
  함께 비교하는 검토로 확장한다. 반복 예외는 명시된 사용자 요구로 한정한다.
- **Why**: 같은 힌트와 다른 배치, 다른 힌트와 같은 배치를 구분하고 근거 없는 확신을 피하기 위해.

## 2026-09-09 — 페이지 요청의 오적용과 비어 있는 방지 원칙 차단

- **Current ADR**: [DESIGN.md 단일 소스](./0015-design-md-source-of-truth.md)
- **Change type**: requirement rule change
- **What**: 번호만 맞으면 적용하던 요청을 번호·제목 일치 또는 유일한 제목 보정으로
  연결한다. 모호한 요청은 경고하고 적용하지 않으며 생성한 방지 원칙의 공백을 거부한다.
- **Why**: 슬라이드 이동이 다른 페이지의 의도를 바꾸거나 빈 원칙이 유효한 것으로 처리되지 않게 하기 위해.

## 2026-09-09 — 디자인 초안에서 배경 이미지 정책 선택

- **Current ADR**: [배경 이미지 정책](./0016-design-md-background-policy.md)
- **Change type**: requirement rule change
- **What**: 초안이 자동 배경을 켜거나 끄는 정책을 선택하고 문서와 양쪽 출력에 전달한다.
  생략한 기존 초안의 기본 자동 배경은 유지한다.
- **Why**: 산문에만 적힌 배경 의도가 출력 단계에서 무시되는 문제를 막기 위해.

## 2026-09-08 — 디자인 계약을 의미 역할과 서버 파생 메타데이터 중심으로 전환

- **Current ADRs**: [슬라이드 타입별 생성 계약](./0004-slide-type-specific-prompts.md),
  [디자인 리뷰](./0008-design-spec-post-generation-review.md),
  [5단 디자인 스펙 계층](./0011-five-layer-design-spec-hierarchy.md),
  [데이터 무결성](./0013-five-layer-data-integrity.md),
  [DESIGN.md taste](./0018-design-md-taste-in-pipeline.md)
- **Change type**: requirement and architecture
- **What**: title·closing의 고정 좌표 계약을 의미 역할 계약으로 바꾸고, Section bbox를
  LLM 중복 출력 대신 Content 좌표에서 서버가 파생한다. 덱 전체 근거·서사 review와
  관련 archetype guidance만 주입하는 프롬프트 정책을 추가한다.
- **Why**: 렌더·참조 무결성은 유지하면서 유효한 시각 구성과 LLM 자율성을 보존하기 위해.

## 2026-09-08 — AI Slop guardrail을 DESIGN.md 정식 영역으로 추가

- **Current ADRs**: [DESIGN.md 단일 소스](./0015-design-md-source-of-truth.md),
  [DESIGN.md taste](./0018-design-md-taste-in-pipeline.md)
- **Change type**: design intent contract
- **What**: 주제 고유성, 정보 위계, 레이아웃 리듬, 장식 기능과 콘텐츠 근거를
  구조화해 모든 슬라이드에 주입한다. 같은 content archetype의 3장 연속 반복을 막는다.
- **Why**: 표면적인 anti-pattern 금지가 또 다른 획일적 템플릿이 되는 것을 피하기 위해.

## 2026-08-29 — title·closing 고정 레이아웃을 ingest 계약으로 승격

- **Current ADR**: [슬라이드 타입별 생성 계약](./0004-slide-type-specific-prompts.md)
- **Change type**: requirement rule change
- **What**: 프롬프트 전용 고정 레이아웃 규칙 → 슬라이드 타입별 Pydantic ingest 검증 계약
- **Why**: 절대 프롬프트 지시는 저장 전에 검증되는 계약과 대응해야 하며, 공통 단순
  모델은 필수 요소와 고정 좌표 위반을 허용했다.

<!-- adr-writer:rules-version 0.8.9 — seeded by /adr-new. `adr-structure-lint` warns when this trails the installed plugin; refresh with /adr-new (it re-seeds a stale doc set). Keep this line on re-seed. -->
