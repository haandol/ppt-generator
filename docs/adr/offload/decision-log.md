# Decision Log: offload

## 2026-09-08 — 하니스 완료 조건을 스킬 정본으로 통합

- **Current ADR**: [클라이언트 LLM 오프로딩](./0001-client-llm-offload-plugin.md)
- **Change type**: workflow contract
- **What**: server instructions와 하니스 진입점은 스킬의 완료 체크포인트, QA 권한,
  최종 HTML/PPTX export와 HTML 열기 규칙을 계약 테스트로 공유한다.
- **Why**: 클라이언트마다 다른 완료 결과와 누락된 export를 방지하기 위해.
