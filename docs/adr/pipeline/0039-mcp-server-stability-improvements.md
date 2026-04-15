# ADR-0039: MCP Server Stability Improvements

**Status**: Proposed  
**Date**: 2026-04-15

## Context

MCP 서버(stdio transport)가 도구 실행 중 반복적으로 연결 해제(disconnect)되는 문제가 발생한다. 주요 원인 분석 결과 다음 5가지 취약점이 확인되었다:

1. **Event Loop 동기화 문제**: `_make_progress_reporter()`에서 `asyncio.get_running_loop()`으로 캡처한 loop 참조를 worker thread에서 `call_soon_threadsafe`로 사용하는데, task 생성 실패 시 예외가 전파되지 않고 서버가 불안정해짐
2. **서버 예외 처리 부재**: `server.py`의 `mcp.run()`에 top-level 예외 처리가 없어 초기화 실패 시 조용히 종료됨
3. **ThreadPoolExecutor 타임아웃 부재**: 병렬 디자인 생성 및 Visual QA에서 LLM 호출이 hang되면 stdio 통신이 블로킹됨
4. **Playwright 리소스 누수**: Visual QA에서 예외 발생 시 `future.result()` 호출에 타임아웃이 없어 스레드가 무한 대기할 수 있음
5. **Graceful shutdown 부재**: SIGTERM/SIGINT 처리가 없어 비정상 종료 시 리소스가 정리되지 않음

## Decision

### 1. Progress Reporter 안전성 강화 (`generation.py`)

`_make_progress_reporter()`에서 `loop.call_soon_threadsafe(loop.create_task, ...)`를 try/except로 감싸 loop가 이미 닫힌 경우 예외를 무시하도록 한다. RuntimeError를 잡아 로그만 남기고 서버 크래시를 방지한다.

### 2. 서버 메인 루프 예외 처리 (`server.py`)

`main()`에서 `mcp.run()` 호출을 try/except로 감싸고, 예상치 못한 예외를 로깅한 후 정상 종료되도록 한다.

### 3. ThreadPoolExecutor future에 타임아웃 추가

- `parallel_runner.py`: `future.result(timeout=DESIGN_SPEC_TIMEOUT)`으로 개별 슬라이드 생성에 타임아웃을 건다 (기본 300초).
- `screenshot.py`: `future.result(timeout=SCREENSHOT_TIMEOUT)`으로 스크린샷 캡처에 타임아웃을 건다 (기본 60초).
- `service.py` (Visual QA): `asyncio.to_thread` 호출을 `asyncio.wait_for()`로 감싸 전체 phase별 타임아웃을 건다.

### 4. Graceful shutdown 시그널 핸들링 (`server.py`)

SIGTERM/SIGINT에 대한 핸들러를 등록하여 `mcp.run()` 루프를 안전하게 종료하도록 한다.

### 5. 타임아웃 상수 추가 (`constants.py`)

새로운 타임아웃 상수를 `constants.py`에 추가:
- `DESIGN_SPEC_TIMEOUT`: 300초 (개별 슬라이드 디자인 생성)
- `SCREENSHOT_TIMEOUT`: 60초 (개별 스크린샷 캡처)
- `VISUAL_QA_PHASE_TIMEOUT`: 600초 (Visual QA 전체 phase)

## Consequences

- 개별 슬라이드 생성이나 스크린샷 캡처가 hang되어도 서버가 정상 동작을 유지
- event loop 닫힌 후의 progress report 시도가 서버 크래시를 유발하지 않음
- 시그널 핸들링으로 프로세스 종료 시 리소스가 정리됨
- 타임아웃 초과 시 해당 슬라이드만 에러로 처리되고 나머지는 정상 진행
