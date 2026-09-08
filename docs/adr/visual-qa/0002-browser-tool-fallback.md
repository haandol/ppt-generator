# Visual QA 브라우저 캡처 폴백

Date: 2026-04-03

## Status

Accepted (2026-09-08)

## Context

Visual QA의 기본 캡처는 Playwright를 사용하지만 선택 의존성이므로 사용할 수 없는
클라이언트가 있다. 이 경우 QA를 포기하면 완성 요청의 품질 경계가 실행 환경에 따라
달라진다.

ppt-generator 서버는 다른 브라우저 도구를 직접 호출하지 않는다. 대신 클라이언트는
자신이 사용할 수 있는 브라우저나 캡처 도구로 PNG를 만들 수 있다.

## Decision Drivers

- Playwright 부재가 Visual QA 전체 생략으로 이어지지 않아야 한다.
- 서버가 외부 브라우저 MCP에 직접 의존하지 않아야 한다.
- 외부 스크린샷은 현재 프로젝트와 슬라이드를 명시적으로 지정해야 한다.
- 읽을 수 없거나 존재하지 않는 경로는 조용히 무시하지 않아야 한다.

## Decision

Visual QA 분석 준비 도구는 서버 캡처 결과 외에 클라이언트가 제공한 스크린샷 경로를
선택적으로 받는다.

- Playwright 캡처가 가능하면 서버 캡처를 우선한다.
- 캡처가 불가능하면 클라이언트는 사용 가능한 브라우저 도구로 PNG를 만들고 그 경로를
  분석 준비 도구에 전달한다.
- 서버는 파일 존재, PNG 형식과 요청한 프로젝트·슬라이드 문맥을 검증한다.
- 두 경로 모두 사용할 수 없으면 lint와 deck review 결과를 반환하고 Visual QA 미실행을
  명시한다.
- 도구 설명, 스킬과 서버 instructions는 같은 fallback 순서를 안내한다.

## Alternatives Considered

- **시스템 Chrome 직접 호출**: subprocess로 Chrome/Chromium 바이너리를 `--headless --screenshot`으로 실행하는 방안. 플랫폼별 바이너리 경로 탐색이 복잡하고 유지보수 부담이 큼.
- **MCP client 내장**: ppt-generator 내부에 Chrome DevTools MCP 클라이언트를 내장하는 방안. 구현 복잡도가 높고 의존성 증가.
- **클라이언트 제공 PNG 경로**: 서버의 브라우저 독립성을 유지하면서 사용 가능한 캡처
  능력을 재사용할 수 있어 채택.

## Acceptance Criteria

- 분석 준비 도구가 외부 PNG 경로를 선택적으로 받는다.
- 존재하지 않거나 PNG가 아닌 파일은 명확히 거부된다.
- Playwright 미설치 시 스킬이 클라이언트 브라우저 캡처를 안내한다.
- 서버 instructions와 스킬의 fallback 순서가 계약 테스트로 일치한다.

## Consequences

- **긍정적**: Playwright가 없어도 클라이언트 능력으로 Visual QA를 계속할 수 있다.
- **긍정적**: 서버는 특정 외부 브라우저나 MCP에 결합되지 않는다.
- **부정적**: 클라이언트가 PNG를 로컬 경로로 제공할 수 있어야 한다.

## References

- 0001: Visual QA Pipeline
