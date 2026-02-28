# ADR-0026: Visual QA Pipeline

## Status

Accepted

## Context

디자인 스펙 생성 후 실제 렌더링 결과에서 시각적 결함(의도하지 않은 줄바꿈, 요소 겹침, 텍스트 잘림 등)이 발생할 수 있다. 기존 `validator.py`는 좌표 기반 검증만 수행하며 실제 픽셀 렌더링 결과를 검증하지 않는다. Playwright는 큰 의존성이므로 opt-in 방식으로 구현한다.

## Decision

Playwright + Claude Vision 기반의 Visual QA 파이프라인을 opt-in MCP tool로 추가한다.

- `visual_qa` MCP tool: 디자인 스펙의 시각적 품질을 검사하고 자동 수정
- Playwright를 optional dependency group(`visual-qa`)으로 추가
- 런타임에 `try: import playwright` → `except ImportError`로 graceful degradation
- 디자인 스펙 생성 완료 후 사용자에게 visual QA 실행을 제안하고, 동의 시에만 실행

## Changes

- `pyproject.toml`: `visual-qa` dependency group에 `playwright` 추가
- `interfaces/constants.py`: `VISUAL_QA_*` 상수 추가 (PARALLEL, MAX_ITERATIONS, VIEWPORT)
- `interfaces/llm_output_models.py`: `VisualQAIssue`, `VisualQAOutput` Pydantic 모델 추가
- `interfaces/prompts/visual_qa_analysis.prompt.md`: 스크린샷 분석 시스템 프롬프트
- `interfaces/prompts/visual_qa_fix.prompt.md`: 디자인 스펙 수정 시스템 프롬프트
- `tools/visual_qa/__init__.py`, `controller.py`, `service.py`: 새 모듈
- `di/model_factory.py`: visual_qa 모델 생성 함수 추가
- `di/container.py`: `create_visual_qa_service` 메서드 추가
- `server.py`: `register_visual_qa_tools` 호출 및 MCP instructions 수정
- `tools/design/controller.py`: 응답에 `visual_qa_suggestion` 추가

## QA Loop

```
for iteration in range(max_iterations):
    1. Playwright로 문제 슬라이드 스크린샷 캡처 (1280x720)
    2. Claude Vision으로 스크린샷 분석 → 이슈 목록
    3. 이슈 없으면 pass
    4. 이슈 있으면 LLM으로 디자인 스펙 수정 → 저장 → HTML 재렌더링
    5. 남은 이슈 없으면 break
    6. Progress 리포트: iteration 완료 시 per_slide 상태 기반으로 한 번 보고
```

## Scope Constraints

- **분석(analysis)**: 시각적 렌더링 이슈만 감지. 슬라이드 콘텐츠(텍스트 문구, 데이터 값, 서술 흐름, 언어 선택)는 절대 지적하지 않는다.
- **수정(fix)**: 시각적 속성(위치, 크기, 폰트 크기, 색상, 정렬)만 변경. 텍스트 내용 자체를 수정하지 않는다. `word_break`/`overflow`를 리사이징/리포지셔닝으로 해결할 수 없으면 폰트 크기를 줄인다.

## Consequences

- 디자인 스펙 생성 후 시각적 결함을 자동 감지하고 수정할 수 있다.
- Playwright 미설치 시에도 기존 기능에 영향 없음 (graceful degradation).
- 추가 LLM 호출 비용 발생 (분석 + 수정, 슬라이드당 최대 2회 반복).
- 스크린샷 파일이 `~/.ppt-generator/<project_id>/screenshots/`에 저장된다.
