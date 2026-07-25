# Contributing Guide

이 문서는 ppt-generator 프로젝트에 기여할 때 따라야 하는 규칙을 정의합니다.

## 목차

- [커밋 메시지 규칙](#커밋-메시지-규칙)
- [브랜치 전략](#브랜치-전략)
- [코드 스타일](#코드-스타일)
- [테스트](#테스트)
- [Git 훅](#git-훅)
- [Pull Request](#pull-request)

---

## 커밋 메시지 규칙

[Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) 스펙을 따릅니다.

### 형식

```
<type>(<scope>): <subject>

[body]

[footer(s)]
```

### Type (필수)

| Type       | 용도                                          | SemVer 영향 |
| ---------- | --------------------------------------------- | ------------ |
| `feat`     | 새로운 기능 추가                              | MINOR        |
| `fix`      | 버그 수정                                     | PATCH        |
| `refactor` | 기능 변경 없는 코드 리팩토링                  | -            |
| `docs`     | 문서 변경                                     | -            |
| `test`     | 테스트 추가/수정                              | -            |
| `chore`    | 빌드 설정, 의존성 업데이트 등 유지보수        | -            |
| `style`    | 코드 포매팅, 세미콜론 등 (로직 변경 없음)     | -            |
| `perf`     | 성능 개선                                     | -            |
| `ci`       | CI/CD 설정 변경                               | -            |
| `build`    | 빌드 시스템, 외부 의존성 변경                 | -            |

### Scope (선택)

변경 대상 모듈을 괄호 안에 명시합니다. 이 프로젝트의 주요 scope:

| Scope      | 대상                                        |
| ---------- | ------------------------------------------- |
| `outline`  | 아웃라인 생성 (`tools/outline/`)            |
| `script`   | 스크립트 생성 (`tools/script/`)             |
| `design`   | 디자인 스펙 생성 (`tools/design/`)          |
| `pptx`     | PPTX 내보내기 (`tools/pptx/`)              |
| `slides`   | HTML 슬라이드 생성 (`tools/slides/`)        |
| `project`  | 프로젝트 관리 (`tools/project/`)            |
| `di`       | 의존성 주입 (`di/container.py`)             |
| `server`   | MCP 서버 진입점 (`server.py`)               |
| `schemas`  | 데이터 모델 (`interfaces/`)                 |
| `prompts`  | 프롬프트 템플릿 (`interfaces/prompts/`)     |
| `templates`| HTML/레이아웃 템플릿 (`templates/`)          |
| `deps`     | 의존성 관리 (`pyproject.toml`, `uv.lock`)   |

### Subject (필수)

- 영문 소문자로 시작
- 명령형(imperative mood) 사용: "add", "fix", "change" (O) / "added", "fixes", "changed" (X)
- 마침표 생략
- 50자 이내 권장 (72자 이내 필수)

### Body (선택)

- subject에서 설명이 부족할 때 **왜(why)** 변경했는지 작성
- 빈 줄로 subject와 구분
- 한 줄 72자 이내로 줄바꿈

### Footer (선택)

- `BREAKING CHANGE: <설명>` — 하위 호환성 깨지는 변경 (SemVer MAJOR)
- `Refs: #<이슈번호>` — 관련 이슈 참조
- `Co-Authored-By: Name <email>` — 공동 작성자

### Breaking Change 표기

타입 뒤에 `!`를 붙이거나 footer에 `BREAKING CHANGE:`를 사용합니다:

```
feat(schemas)!: remove legacy SlideData dataclass

BREAKING CHANGE: SlideData가 제거되었습니다.
PptxSlideSpec으로 마이그레이션하세요.
```

### 좋은 예시

```
feat(design): add complexity-based adaptive thinking effort

슬라이드 복잡도 점수(1~13)에 따라 high/medium/low effort를
동적으로 적용하여 단순 슬라이드의 토큰을 절약합니다.

Refs: #42
```

```
fix(outline): handle empty slide list in ingest_outline
```

```
refactor(design): extract design summary generation into separate method
```

```
docs: clarify prepare/ingest handshake in environment guide
```

```
chore(deps): bump python-pptx to 1.0.2
```

```
perf(design): parallelize slide design spec generation with ThreadPoolExecutor
```

```
test(design): add unit tests for adjacent context section generation
```

### 나쁜 예시

```
# type 없음
Update DESIGN_SPEC_PARALLEL default value from 4 to 8

# 과거형 사용
feat: Added support for parallel generation

# 대문자 시작
feat: Add support for ...  (O)
feat: add support for ...  (O)
feat: Added support for ... (X — 과거형)

# 너무 모호함
update model and thinking effort
bump deps up
revert thinking

# 여러 변경을 한 커밋에 섞음
Enhance design spec prompts: slide type sections, color theme, page design rules
```

### 원자적 커밋 (Atomic Commits)

하나의 커밋에는 하나의 논리적 변경만 포함합니다:

- 기능 추가와 버그 수정을 같은 커밋에 넣지 않습니다
- 리팩토링과 기능 변경을 같은 커밋에 넣지 않습니다
- 변경이 크면 여러 커밋으로 나눕니다

```
# 나쁜 예 — 두 가지 변경을 한 커밋에 섞음
feat(design): add batch processing and fix progress reporting

# 좋은 예 — 분리
feat(design): add batch processing for slide generation
fix(design): correct progress percentage calculation
```

---

## 브랜치 전략

### 브랜치 명명 규칙

```
<type>/<short-description>
```

| 접두사       | 용도             | 예시                             |
| ------------ | ---------------- | -------------------------------- |
| `feat/`      | 새 기능 개발     | `feat/parallel-design-spec`      |
| `fix/`       | 버그 수정        | `fix/outline-empty-slides`       |
| `refactor/`  | 리팩토링         | `refactor/di-container-cleanup`  |
| `docs/`      | 문서 작업        | `docs/contributing-guide`        |
| `chore/`     | 유지보수         | `chore/update-dependencies`      |
| `test/`      | 테스트 추가/수정 | `test/design-service-coverage`   |

### 워크플로우

1. `main`에서 새 브랜치 생성
2. 작업 후 커밋 (위 커밋 규칙 준수)
3. Pull Request 생성
4. 리뷰 후 `main`에 머지

```bash
git checkout main
git pull origin main
git checkout -b feat/my-feature
# ... 작업 ...
git add <files>
git commit -m "feat(scope): add my feature"
git push -u origin feat/my-feature
```

---

## 코드 스타일

### Python

- **Python 버전**: 3.13+
- **타입 힌트**: 모든 함수에 반환 타입 명시 (`-> None`, `-> str` 등)
- **상수**: `interfaces/constants.py`에 정의
- **프롬프트 템플릿**: `interfaces/prompts/*.prompt.md`로 관리
- **MCP 도구 함수**: 영문 docstring (MCP 클라이언트에 도구 설명으로 노출 — 영문 서버
  instructions·스킬 description 과 통일). 내부 헬퍼는 한국어 docstring 유지

### 프로젝트 구조 규칙

새 도구 추가 시 Controller-Service 패턴을 따릅니다:

1. `tools/<module>/` 디렉토리 생성 (`__init__.py`, `controller.py`, `service.py`)
2. `service.py` — Request → Response 비즈니스 로직
3. `controller.py` — `register_*_tools(mcp, service, project_service)` 함수
4. `interfaces/schemas.py`에 Request/Response 데이터클래스 추가
5. `di/container.py`에 Service 프로퍼티 추가 (지연 초기화)
6. `server.py`에서 `register_*_tools()` 호출

---

## 테스트

```bash
# 전체 테스트
uv run pytest

# 개별 테스트 파일
uv run pytest tests/test_xxx.py

# 특정 테스트 함수
uv run pytest tests/test_xxx.py::test_function_name -v
```

### 테스트 규칙

- 이 서버는 LLM 을 직접 호출하지 않는다(생성은 MCP 클라이언트 담당). 남는 외부 API 호출이 있다면 반드시 mock 처리
- 새 기능 추가 시 관련 테스트 파일 작성
- 테스트 파일명: `tests/test_<모듈명>.py`

### 계약 테스트

`src/` 밖의 사용자 표면도 테스트로 고정한다 — 문서·스킬이 코드보다 뒤처져도
`uv run pytest` 가 잡는다.

- 스킬(`skills/*/SKILL.md`)이 서술하는 MCP 도구명·파라미터명 ↔ 실제 등록 도구 시그니처
- 프롬프트가 열거한 값(`component_hint`, lint rule id 등) ↔ 문서 표·응답 모델

도구 시그니처나 프롬프트를 바꿔 이 테스트가 깨지면, 테스트를 고치지 말고 뒤처진
문서·스킬을 갱신한다 (코드가 정본).

---

## Git 훅

`.git/hooks/` 는 git 추적 대상이 아니라 **클론한 사람에게 전파되지 않는다.** 저장소를
새로 클론했으면 훅이 없는 상태이므로, 커밋 전 검사를 로컬에서 직접 돌려야 한다.

```bash
uv run ruff format .   # 포매팅
uv run ruff check .    # 린트
uv run pytest          # 전체 테스트
```

기존 훅이 설치돼 있으면 `src/` `tests/` `skills/` `scripts/` `.claude-plugin/` 변경 시
위 검사를 자동 수행하고, `pyproject.toml` 버전 변경 시 `uv.lock` 과
`.claude-plugin/plugin.json` 의 버전을 함께 동기화한다.

---

## Pull Request

### PR 제목

커밋 메시지와 동일한 Conventional Commits 형식을 사용합니다:

```
feat(design): add complexity-based adaptive thinking effort
```

### PR 본문 템플릿

```markdown
## Summary

변경 사항을 1~3개 bullet point로 요약합니다.

## Motivation

왜 이 변경이 필요한지 설명합니다.

## Changes

- 주요 변경 사항 상세 목록

## Test Plan

- [ ] 기존 테스트 통과 확인 (`uv run pytest`)
- [ ] 새 테스트 추가 (해당 시)
- [ ] 수동 테스트 시나리오 설명
```

### 머지 규칙

- Squash merge를 기본으로 사용합니다
- 머지 커밋 메시지는 Conventional Commits 형식을 따릅니다
- `main` 브랜치에 직접 push하지 않습니다
