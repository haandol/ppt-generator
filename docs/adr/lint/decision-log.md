# Decision Log: lint

This document is the **major decision-change history** of the lint category. Each
ADR body describes only the current state, while the timeline of "what changed and why"
accumulates here, newest first. Git preserves the individual diffs.

## 2026-08-29 — 품질 게이트를 계약 검증·lint·생성 권고로 분리

- **Current ADR**: [디자인 스펙 품질 게이트](./0003-validator-to-lint.md)
- **Change type**: architecture
- **What**: 모든 디자인 문제를 lint 리포트로 다루는 경계 → 해석 불가능한 계약 위반은
  ingest에서 거부하고, 유효한 대안이 있는 품질 위험은 비차단 lint 또는 생성 권고로 처리
- **Why**: 필수 데이터 계약을 보존하면서 휴리스틱 오탐과 사용자 동의 없는 품질 수정
  실행을 방지해야 했다.

<!-- adr-writer:rules-version 0.8.9 — seeded by /adr-new. `adr-structure-lint` warns when this trails the installed plugin; refresh with /adr-new (it re-seeds a stale doc set). Keep this line on re-seed. -->
