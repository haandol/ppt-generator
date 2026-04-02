# PPT Generator — Agent Guide

> AI 에이전트가 프레젠테이션을 자동 생성하는 Python MCP 서버.
> 이 파일은 **목차** 역할. 상세 내용은 `docs/` 참조.

## 프로젝트 개요

- **기술 스택**: Python 3.13+ · MCP · AWS Strands SDK · Claude Sonnet 4.6 Extended Thinking
- **패키지 매니저**: uv · 빌드: hatchling · 진입점: `ppt_generator.server:main`
- **ALPS 설계 문서**: [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md)

## 리포지터리 구조

```
src/ppt_generator/
├── server.py              # MCP 서버 진입점
├── di/                    # 의존성 주입 (container, model_factory)
├── interfaces/            # 스키마, 상수, 프롬프트, spec_utils
├── templates/             # HTML 템플릿, 레이아웃 매핑
└── tools/
    ├── outline/           # 아웃라인 생성
    ├── script/            # 발표 스크립트 생성
    ├── design/            # 디자인 스펙 생성/수정 (병렬)
    ├── slides/            # HTML 슬라이드 렌더링
    ├── visual_qa/         # Visual QA (Playwright + Vision)
    ├── pptx/              # PPTX 내보내기
    ├── pptx_import/       # PPTX 임포트
    └── project/           # 프로젝트 관리
```

## 명령어

```bash
uv sync                                          # 의존성 설치
uv run ppt-generator                             # MCP 서버 실행 (stdio)
uv run pytest                                    # 전체 테스트
uv run pytest tests/test_xxx.py::test_func -v    # 특정 테스트
```

## ADR-First 워크플로우 (필수)

기능 추가/변경이 필요한 작업에서는 **반드시 코드 작성 전에 ADR을 먼저 작성/수정**하고, 사용자의 확인을 받은 뒤에 코드를 구현해야 합니다.

1. **분석**: 코드베이스를 조사하여 변경 범위와 영향을 파악
2. **ADR 작성/수정**: Context, Decision, Technical Details, Acceptance Criteria를 정리하여 사용자에게 제시
3. **사용자 확인**: ADR 내용에 대해 사용자 승인을 받음 (수정 요청 시 ADR을 먼저 반영)
4. **코드 구현**: 승인된 ADR을 기반으로 코드 작성
5. **테스트**: 구현 완료 후 테스트 실행

이 순서를 지키지 않으면 사용자가 어떤 변경이 일어날지 사전에 파악할 수 없고, 구현 후 방향 수정 시 작업이 낭비됩니다.

### ADR 작성 규칙

- **기존 ADR 우선 업데이트**: 기존 ADR 범위에 포함되면 해당 섹션을 직접 수정. 새 ADR은 기존에 합칠 곳이 없을 때만 작성
- **파일 위치**: `docs/adr/` 하위 디렉토리 · **네이밍**: `NNNN-<kebab-case-title>.md`
- **코드 스니펫/파일 경로 금지**: ADR에 구현 코드 스니펫이나 파일 경로를 포함하지 않는다. 코드가 변경될 때마다 ADR을 수정해야 하는 상황을 방지하기 위해, ADR은 "왜(why)"와 "무엇(what)" 수준의 설계 결정만 기록하고 "어떻게(how)"의 구현 디테일은 코드에 맡긴다.
- ADR 작성 가이드: [`docs/adr/README.md`](docs/adr/README.md)

## 컨벤션

- 타입 힌트 필수 (`-> None`, `-> str` 등)
- 상수는 `interfaces/constants.py`에, 프롬프트는 `interfaces/prompts/*.prompt.md`에 정의
- MCP 도구 함수에는 한국어 docstring 필수 (클라이언트에 노출됨)
- 외부 API(Bedrock/Anthropic) 호출 테스트는 반드시 mock 처리
- Conventional Commits: `<type>(<scope>): <subject>` (상세: [CONTRIBUTING.md](CONTRIBUTING.md))

## 검증 기준

작업 완료 전 반드시 확인:

1. `uv run pytest` 통과
2. 관련 ADR이 최신 상태
3. 기존 도구 시그니처 변경 시 MCP 클라이언트 호환성 확인

## 제약 사항

- ADR 없이 주요 기능 추가/변경하지 않음 — ADR-First 워크플로우 필수
- `--no-verify`로 git hook을 우회하지 않음
- 테스트를 삭제하거나 수정하여 통과시키지 않음 — 코드를 고칠 것
- LLM API 호출 파라미터 변경 시 Anthropic/Bedrock 양쪽 확인 필수

## Approach with Caution

- `server.py` — 도구 등록 로직
- `di/container.py` — 의존성 주입 설정
- 기존 도구 시그니처 변경 (MCP 클라이언트 호환성에 영향)
- PPTX 변환 로직 (`tools/pptx/` — 좌표 변환, 스타일 매핑)
- HTML 렌더링 로직 (`tools/slides/html_renderer.py`)

## 상세 문서

| 문서                  | 경로                                     | 설명                                            |
| --------------------- | ---------------------------------------- | ----------------------------------------------- |
| 아키텍처              | [`docs/harness/architecture.md`](docs/harness/architecture.md) | 파이프라인, Controller-Service 패턴, 병렬 처리, 토큰 추적, MCP 도구 목록 |
| 스키마                | [`docs/harness/schemas.md`](docs/harness/schemas.md)     | 도메인 모델, LLM 출력 모델, component_hint 테이블 |
| 환경변수 & 설정       | [`docs/harness/environment.md`](docs/harness/environment.md) | 환경변수, 사용 모델, MCP 클라이언트 설정 예시   |
| ALPS 설계 문서        | [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md) | 피쳐 목록, 기능 명세, 인수 기준                 |
| ADR 인덱스            | [`docs/adr/README.md`](docs/adr/README.md) | 전체 ADR 목록 및 작성 가이드                    |
