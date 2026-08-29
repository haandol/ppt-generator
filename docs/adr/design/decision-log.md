# Decision Log: design

This document is the **major decision-change history** of the design category. Each
ADR body describes only the current state, while the timeline of "what changed and why"
accumulates here, newest first. Git preserves the individual diffs.

## 2026-08-29 — title·closing 고정 레이아웃을 ingest 계약으로 승격

- **Current ADR**: [슬라이드 타입별 생성 계약](./0004-slide-type-specific-prompts.md)
- **Change type**: requirement rule change
- **What**: 프롬프트 전용 고정 레이아웃 규칙 → 슬라이드 타입별 Pydantic ingest 검증 계약
- **Why**: 절대 프롬프트 지시는 저장 전에 검증되는 계약과 대응해야 하며, 공통 단순
  모델은 필수 요소와 고정 좌표 위반을 허용했다.

<!-- adr-writer:rules-version 0.8.9 — seeded by /adr-new. `adr-structure-lint` warns when this trails the installed plugin; refresh with /adr-new (it re-seeds a stale doc set). Keep this line on re-seed. -->
