# Decision Log: visual-qa

## 2026-09-08 — opt-in 전체 spec 수정에서 기본 저위험 patch QA로 전환

- **Current ADRs**: [Visual QA pipeline](./0001-visual-qa-pipeline.md),
  [브라우저 캡처 폴백](./0002-browser-tool-fallback.md)
- **Change type**: permission and data contract
- **What**: 완성 요청은 read-only 분석과 저위험 patch 수정을 포함한다. 수정은 허용 필드
  replace operation만 사용하며 Playwright가 없으면 검증된 클라이언트 PNG를 받는다.
- **Why**: 콘텐츠 의미는 보존하면서 실제 렌더 결함을 자동으로 끝까지 해결하기 위해.
