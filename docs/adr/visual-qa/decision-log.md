# Decision Log: visual-qa

## 2026-09-09 — 분석 준비 시점부터 입력 문맥을 검증

- **Current ADR**: [Visual QA pipeline](./0001-visual-qa-pipeline.md)
- **Change type**: requirement rule change
- **What**: 분석 수신 시 현재 입력으로 승인 문맥을 만들던 방식에서, 준비 단계의
  명세·의도·이미지를 검증한 뒤에만 수정 권한을 발급하는 방식으로 바꾼다.
  문맥이 없는 진행 중 분석은 준비부터 다시 실행한다.
- **Why**: 오래된 분석으로 새 슬라이드를 수정하는 경합을 막기 위해.

## 2026-09-09 — QA 분석과 수정에 디자인 의도 전달

- **Current ADR**: [Visual QA pipeline](./0001-visual-qa-pipeline.md)
- **Change type**: requirement rule change
- **What**: 화면·명세만 보던 검사에 전역 의도와 페이지 요청을 포함한다. 의도된 여백과
  비대칭은 차이 자체만으로 평준화하지 않는다.
- **Why**: 품질 수정이 발표의 강조와 전환을 지우지 않도록 하기 위해.

## 2026-09-08 — opt-in 전체 spec 수정에서 기본 저위험 patch QA로 전환

- **Current ADRs**: [Visual QA pipeline](./0001-visual-qa-pipeline.md),
  [브라우저 캡처 폴백](./0002-browser-tool-fallback.md)
- **Change type**: permission and data contract
- **What**: 완성 요청은 read-only 분석과 저위험 patch 수정을 포함한다. 수정은 허용 필드
  replace operation만 사용하며 Playwright가 없으면 검증된 클라이언트 PNG를 받는다.
- **Why**: 콘텐츠 의미는 보존하면서 실제 렌더 결함을 자동으로 끝까지 해결하기 위해.
