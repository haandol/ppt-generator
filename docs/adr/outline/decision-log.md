# Decision Log: outline

## 2026-09-08 — 필수 발표 골격과 목적 기반 기본값을 결합

- **Current ADRs**: [아웃라인 생성](./0001-outline-generation.md),
  [레이아웃 계획](./0004-layout-planning-phase.md)
- **Change type**: requirement and permission
- **What**: 슬라이드 수는 4~20장으로 유지하고 Title → Agenda → 최소 1개 Body →
  Closing을 필수로 둔다. 누락된 무해한 발표 조건은 기본값이나 가정으로 보완하며
  레이아웃 계획은 기본 의도로 취급한다.
- **Why**: 사용자가 요구한 발표 골격을 보장하면서 불필요한 사전 질문과 픽셀 레시피
  제약을 줄이기 위해.
