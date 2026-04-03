# 35. Visual QA 브라우저 도구 안내 개선

Date: 2026-04-03

## Status

Proposed

## Context

현재 Visual QA는 스크린샷 캡처를 위해 Playwright만 지원한다. Playwright가 설치되지 않으면 RuntimeError가 발생하며, 에러 메시지에 Playwright 설치 가이드만 제공한다.

한편 사용자 환경에 Chrome DevTools MCP 서버가 설정되어 있을 수 있다. Chrome DevTools MCP의 `take_screenshot` 도구를 사용하면 Playwright 없이도 수동으로 스크린샷 캡처가 가능하다.

ppt-generator는 MCP 서버이므로 다른 MCP 서버(Chrome DevTools MCP)의 도구를 직접 호출할 수 없는 구조적 제약이 있다.

## Decision

Visual QA 도구의 설명과 에러 메시지에 Chrome DevTools MCP를 대안 도구로 안내하여, 사용자가 환경에 맞는 도구를 선택할 수 있도록 한다.

### Technical Details

1. **visual_qa 도구 docstring 업데이트**: Playwright 외에 Chrome DevTools MCP의 `take_screenshot`을 대안으로 안내한다.

2. **에러 메시지 개선**: Playwright가 없을 때 발생하는 RuntimeError에 Chrome DevTools MCP 사용 가이드를 추가한다.

3. **서버 instructions 업데이트**: MCP 서버의 instructions에서 Playwright 전용 문구를 Chrome DevTools MCP 대안 안내로 보완한다.

### Alternatives Considered

- **시스템 Chrome 직접 호출**: subprocess로 Chrome/Chromium 바이너리를 `--headless --screenshot`으로 실행하는 방안. 플랫폼별 바이너리 경로 탐색이 복잡하고 유지보수 부담이 큼.
- **MCP client 내장**: ppt-generator 내부에 Chrome DevTools MCP 클라이언트를 내장하는 방안. 구현 복잡도가 높고 의존성 증가.

### Acceptance Criteria

- visual_qa 도구 docstring에 Chrome DevTools MCP 대안이 안내된다
- Playwright 미설치 시 에러 메시지에 두 가지 옵션(Playwright 설치, Chrome DevTools MCP 사용)이 표시된다
- 서버 instructions에 대안 도구 안내가 포함된다

### Out of Scope

- Chrome DevTools MCP 자동 호출 통합
- 다른 브라우저 자동화 도구 지원

## Consequences

- **긍정적**: 사용자가 환경에 맞는 스크린샷 도구를 선택할 수 있는 정보 제공
- **긍정적**: 기존 코드 변경 최소화 (문서/메시지만 수정)
- **부정적**: Chrome DevTools MCP 경로는 자동화되지 않으므로 수동 작업 필요

## References

- ADR-0026: Visual QA Pipeline
