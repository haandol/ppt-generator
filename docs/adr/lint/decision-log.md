# Decision Log: lint

This document is the **major decision-change history** of the lint category. Each
ADR body describes only the current state, while the timeline of "what changed and why"
accumulates here, newest first. Git preserves the individual diffs.

## 2026-09-08 — 저위험 시각 수정과 의미 변경의 권한 경계 분리

- **Current ADRs**: [디자인 스펙 품질 게이트](./0003-validator-to-lint.md),
  [5단 lint 정책](./0005-five-layer-lint-policy.md)
- **Change type**: permission and validation policy
- **What**: end-to-end 요청은 read-only QA와 저위험 시각 수정을 포함하고, 콘텐츠·구조
  변경만 사용자 확인 대상으로 둔다. 누락된 의미 링크와 파생 bbox 회귀는 거부하되
  의도 가능한 형제 영역 겹침은 warning으로 내린다.
- **Why**: 필수 데이터 계약을 유지하면서 품질 수정 왕복과 표현 과잉 제약을 줄이기 위해.

## 2026-08-29 — 품질 게이트를 계약 검증·lint·생성 권고로 분리

- **Current ADR**: [디자인 스펙 품질 게이트](./0003-validator-to-lint.md)
- **Change type**: architecture
- **What**: 모든 디자인 문제를 lint 리포트로 다루는 경계 → 해석 불가능한 계약 위반은
  ingest에서 거부하고, 유효한 대안이 있는 품질 위험은 비차단 lint 또는 생성 권고로 처리
- **Why**: 필수 데이터 계약을 보존하면서 휴리스틱 오탐과 사용자 동의 없는 품질 수정
  실행을 방지해야 했다.

<!-- adr-writer:rules-version 0.8.9 — seeded by /adr-new. `adr-structure-lint` warns when this trails the installed plugin; refresh with /adr-new (it re-seeds a stale doc set). Keep this line on re-seed. -->
