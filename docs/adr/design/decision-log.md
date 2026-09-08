# Decision Log: design

This document is the **major decision-change history** of the design category. Each
ADR body describes only the current state, while the timeline of "what changed and why"
accumulates here, newest first. Git preserves the individual diffs.

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
