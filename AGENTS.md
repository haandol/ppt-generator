# PPT Generator MCP Server Guide

## Overview

사용자가 주제를 입력하면 AI가 자동으로 프레젠테이션을 생성하는 Python MCP 서버입니다.
Claude LLM(Anthropic API 또는 AWS Bedrock)으로 아웃라인/스크립트/디자인 스펙을 생성하고, 디자인 스펙(PptxSlideSpec JSON)에서 HTML 미리보기와 편집 가능한 PPTX를 결정론적으로 변환합니다.
Claude Desktop, Kiro 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

> ALPS 설계 문서: 피쳐 목록, 기능 명세, 인수 기준 등 구현에 필요한 세부 사항은 [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md) (또는 원본 [`docs/ppt-generator.alps.xml`](docs/ppt-generator.alps.xml))를 반드시 확인하세요.
>
> ALPS 문서에 포함된 내용:
>
> - **Section 1~3**: 프로젝트 개요, MVP 목표, 데모 시나리오
> - **Section 4~5**: 아키텍처, 설계 명세
> - **Section 6**: 요구사항 요약
> - **Section 7**: 피쳐별 상세 명세 (F1~F6) — 사용자 스토리, 흐름, 기술 설명, 엣지 케이스, 인수 기준
> - **Section 8~9**: MVP 메트릭, 범위 외 항목

## Directory Structure

```
ppt-generator/
├── src/ppt_generator/
│   ├── server.py                  # MCP 서버 진입점 + 도구 등록
│   ├── di/
│   │   └── container.py           # 의존성 주입 컨테이너
│   ├── tools/
│   │   ├── outline/               # 슬라이드 아웃라인 생성 도구 (F1)
│   │   │   ├── controller.py      # MCP 인터페이스
│   │   │   └── service.py         # LLM 호출 로직 (Anthropic/Bedrock)
│   │   ├── script/                # 발표 스크립트 생성 도구 (F2)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   ├── design/                # 디자인 스펙 생성 도구
│   │   │   ├── controller.py      # MCP 인터페이스
│   │   │   └── service.py         # LLM 기반 디자인 스펙 생성
│   │   ├── pptx/                  # PPTX 내보내기 도구 (F5)
│   │   │   ├── controller.py      # MCP 인터페이스
│   │   │   ├── service.py         # ExportService (디자인 스펙 → PPTX)
│   │   │   ├── slide_builder.py   # PptxSlideSpec → python-pptx 변환
│   │   │   └── text_formatter.py  # run/paragraph 포매팅 공통 함수
│   │   ├── project/               # 프로젝트 저장/로드 도구 (F6)
│   │   │   ├── controller.py
│   │   │   ├── service.py         # 프로젝트 코어 관리 (파일 I/O, 메타데이터)
│   │   │   └── design_spec_store.py # 디자인 스펙 파일 CRUD 전담 저장소
│   │   └── slides/                # HTML 슬라이드 생성 도구 (디자인 스펙 → HTML)
│   │       ├── controller.py
│   │       ├── service.py         # 오케스트레이션 (세션 관리, 템플릿 조합)
│   │       └── html_renderer.py   # PptxSlideSpec → HTML 변환 렌더러
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 수치 상수, 프롬프트 re-export
│   │   ├── schemas.py             # 내부 도메인 모델 (dataclass)
│   │   ├── llm_output_models.py   # LLM structured_output용 Pydantic 모델
│   │   ├── spec_utils.py          # PptxSlideSpec 파싱/검증/직렬화 공유 유틸리티
│   │   ├── text_measurement.py    # 폰트 메트릭 기반 텍스트 크기 추정 (줄바꿈/높이 계산)
│   │   ├── bg_image_utils.py      # 배경 이미지 유틸리티
│   │   ├── utils.py               # parse_outline_json 등 공용 파싱 유틸리티
│   │   └── prompts/                      # 프롬프트 템플릿 모듈
│   │       ├── __init__.py               # .prompt.md 파일 로딩 + 상수 re-export
│   │       ├── design_system.prompt.md   # 디자인 스펙 시스템 프롬프트
│   │       ├── design_user.prompt.md     # 디자인 스펙 사용자 프롬프트 (첫 슬라이드용)
│   │       ├── design_batch_user.prompt.md # 디자인 스펙 배치 사용자 프롬프트 (design_summary 참조)
│   │       ├── design_summary_user.prompt.md # design_summary 사전 생성 프롬프트
│   │       ├── outline_system.prompt.md  # 아웃라인 시스템 프롬프트
│   │       ├── outline_user.prompt.md    # 아웃라인 사용자 프롬프트
│   │       ├── script_system.prompt.md   # 스크립트 시스템 프롬프트
│   │       └── script_user.prompt.md     # 스크립트 사용자 프롬프트
│   └── templates/
│       ├── slide.html             # 개별 슬라이드 HTML 템플릿 (완전한 HTML 문서)
│       ├── slides.html            # 레거시 단일 HTML 템플릿 (하위 호환)
│       ├── slides_container.html  # iframe 컨테이너 템플릿
│       ├── layout_mapping.py      # layout_index → 슬라이드 레이아웃 매핑 (97종)
│       └── template_bg_images/    # 배경 이미지 리소스
├── env/
│   └── local.env                  # 샘플 환경변수 파일
├── docs/
│   ├── adr/                       # Architecture Decision Records
│   ├── ppt-generator.alps.xml     # ALPS 설계 문서
│   └── ppt-generator.alps.md      # ALPS 마크다운 내보내기
├── tests/
└── pyproject.toml
```

## Technology Stack

- **Protocol**: Model Context Protocol (MCP)
- **Language**: Python 3.13+
- **Package Manager**: uv
- **Build System**: hatchling
- **Agent Framework**: AWS Strands SDK (`strands-agents`)
- **LLM (디자인 스펙 생성)**: Claude Sonnet 4.6 (Bedrock: `global.anthropic.claude-sonnet-4-6` / Anthropic: `claude-sonnet-4-6`, 48K tokens, effort: high)
- **LLM (아웃라인/스크립트)**: Claude Sonnet 4.6 (Bedrock: `global.anthropic.claude-sonnet-4-6` / Anthropic: `claude-sonnet-4-6`, 16K tokens, effort: medium)
- **Slide Framework**: 순수 HTML/CSS (인라인 스타일, 슬라이드별 개별 HTML + iframe 컨테이너)
- **PPTX Export**: python-pptx (디자인 스펙 → SlideBuilder 직접 변환)

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- LLM 인증 (아래 중 하나 선택):
  - **Anthropic API** (권장): `ANTHROPIC_API_KEY` 환경변수 설정
  - **AWS Bedrock (기본)**: 별도 설정 없이 기본 AWS credential chain 사용 (`~/.aws/credentials`, 환경변수, IAM role 등)
    - Amazon Bedrock 모델 접근 권한 필요 (Claude Sonnet 4.6)
    - 리전: `us-east-1` (기본값)
  - **AWS Bedrock (API key)**: `AWS_BEARER_TOKEN_BEDROCK` 환경변수로 bearer token 설정 시 SigV4 대신 bearer token 인증 사용
    - 리전: `us-east-1` (기본값)

### 환경변수

| 환경변수                   | 값                      | 설명                                                                                                     |
| -------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| `LLM_PROVIDER`             | `anthropic` / `bedrock` | 명시적 provider 선택 (미설정시 auto-detect)                                                              |
| `ANTHROPIC_API_KEY`        | API Key 문자열          | Anthropic 직접 API 인증 (auto-detect 트리거)                                                             |
| `AWS_ACCESS_KEY_ID`        | AWS Access Key          | Bedrock IAM 인증                                                                                         |
| `AWS_SECRET_ACCESS_KEY`    | AWS Secret Key          | Bedrock IAM 인증                                                                                         |
| `AWS_REGION`               | AWS 리전                | Bedrock 리전 (기본: us-east-1)                                                                           |
| `AWS_BEARER_TOKEN_BEDROCK` | Bearer Token 문자열     | Bedrock API key (bearer token) 인증. 설정 시 bearer token 우선, 미설정 시 기본 AWS credential chain 사용 |
| `BEDROCK_DESIGN_MODEL_ID`  | 모델 ID 문자열          | 디자인 스펙 생성 Bedrock 모델 (기본: `global.anthropic.claude-sonnet-4-6`)                                |
| `ANTHROPIC_DESIGN_MODEL_ID`| 모델 ID 문자열          | 디자인 스펙 생성 Anthropic 모델 (기본: `claude-sonnet-4-6`)                                              |
| `BEDROCK_DESIGN_MAX_TOKENS`| 정수 (기본: 64000)      | 디자인 스펙 생성 max tokens                                                                              |
| `DESIGN_THINKING_EFFORT`   | `high`/`medium`/`low`   | 디자인 스펙 생성 thinking effort (기본: high)                                                            |
| `BEDROCK_OUTLINE_MODEL_ID` | 모델 ID 문자열          | 아웃라인/스크립트 Bedrock 모델 (기본: `global.anthropic.claude-sonnet-4-6`)                               |
| `ANTHROPIC_OUTLINE_MODEL_ID`| 모델 ID 문자열         | 아웃라인/스크립트 Anthropic 모델 (기본: `claude-sonnet-4-6`)                                             |
| `OUTLINE_THINKING_EFFORT`  | `high`/`medium`/`low`   | 아웃라인/스크립트 thinking effort (기본: medium)                                                         |
| `DESIGN_SPEC_PARALLEL`     | 정수 (기본: 4)          | `generate_slides_design_spec` 도구의 병렬 워커 수 제어                                                   |

> **Auto-detect 로직**: `LLM_PROVIDER` 미설정 시, `ANTHROPIC_API_KEY`가 있으면 `anthropic`, 없으면 `bedrock`으로 자동 선택됩니다.

## Development Commands

```bash
# 의존성 설치
uv sync

# 서버 실행
uv run ppt-generator

# 테스트 실행
uv run pytest
```

## Architecture

Controller-Service 패턴 + 의존성 주입(DI)을 사용합니다:

- **Controller** (`controller.py`): MCP 도구 인터페이스. `register_*_tools(mcp, service, project_service)` 함수로 도구를 등록하며, 내부에 `@mcp.tool()` 데코레이터가 적용된 함수를 정의합니다. docstring이 MCP 클라이언트에 도구 설명으로 노출됩니다.
- **Service** (`service.py`): 비즈니스 로직. Request 데이터클래스를 받아 Response 데이터클래스를 반환합니다.
- **DIContainer** (`di/container.py`): 프로바이더 자동 감지(Anthropic/Bedrock), 모델, Agent, Service 인스턴스를 생성하고 연결합니다. 지연 초기화(lazy init) 패턴을 사용합니다.

### Pipeline Design Philosophy: Progressive Refinement

파이프라인은 **추상에서 구체로의 점진적 구체화(Progressive Refinement)** 원칙으로 설계되었습니다. 각 단계는 이전 단계의 출력을 더 구체적인 형태로 변환하며, 디자인 자유도를 최대한 보존합니다.

```
텍스트 (가장 추상적)
  → 아웃라인 (구조화된 JSON — 제목, 내용 요약, 레이아웃 인덱스)
    → 스크립트 (구체적 — 아웃라인 기반 발표 스크립트)
      → 디자인 스펙 (PptxSlideSpec JSON — LLM이 정밀한 레이아웃 설계)
        ├→ HTML 슬라이드 (결정론적 변환, 브라우저 미리보기용)
        └→ PPTX (SlideBuilder 직접 사용, 편집 가능한 포맷으로 변환)
```

> **디자인 스펙 기반 파이프라인**: 디자인 스펙(PptxSlideSpec JSON)을 중간 표현으로 사용하여
> HTML과 PPTX를 각각 결정론적으로 생성합니다. LLM 호출은 디자인 스펙 생성 단계에서만 발생하며,
> 이후 HTML/PPTX 변환은 모두 결정론적입니다.

**핵심 원칙:**

- **파일 기반 통신**: 모든 도구는 결과를 파일로 저장하고 파일 경로를 반환합니다. `project_id`만으로 도구를 체이닝할 수 있어 인라인 JSON 전달이 불필요하며, MCP 클라이언트의 컨텍스트 윈도우 토큰 사용을 최적화합니다.
- **슬라이드 단위 세분화**: `modify_design_spec` 도구로 중간 산출물(디자인 스펙)의 개별 슬라이드를 추가/수정/삭제할 수 있어, 전체 재생성 없이 반복적 개선이 가능합니다. 디자인 스펙은 `design_spec/slide_NN.json`, HTML은 `slides/slide_NN.html` 형식으로 슬라이드별 개별 파일에 저장됩니다.

### Processing Pipeline

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: generate_outline       → 슬라이드 아웃라인 JSON 생성 (LLM, title/content_summary/component_hint)
    ↓
    ⏸ 사용자 확인           → 아웃라인 구조 검토 및 승인 (수정 시 F1 재호출)
    ↓
F2: generate_script        → 아웃라인 기반 슬라이드별 발표 스크립트 생성
    ↓
    디자인 스펙 생성:
      generate_slides_design_spec(project_id=..., total_slides=N)
        → 전체 생성 (기본) 또는 slide_indices="0,2,4"로 선택적 생성
        → design_summary가 없으면 LLM으로 사전 생성 (전체 아웃라인 기반)
        → 모든 슬라이드를 서버 내부 병렬 생성 (DESIGN_SPEC_PARALLEL 워커)
        → content 슬라이드의 배경색을 design_summary 값으로 강제 보정
        → 완료 시 slides.html (iframe 컨테이너) 자동 생성
    ↓
    ⏸ (선택) modify_design_spec → 개별 슬라이드 추가/수정/삭제 (project_id로 참조)
    ↓
    ├→ generate_slides(project_id=...)       → 디자인 스펙 자동 로드 → HTML 변환 (결정론적)
    │
    └→ export_pptx(project_id=...)          → 디자인 스펙 자동 로드 → PPTX 생성 (결정론적)
    ↓
출력: 편집 가능한 .pptx 파일

* project_id 기반 체이닝 (권장): generate_slides_design_spec → generate_slides/export_pptx(project_id=...)
* 모든 도구가 project_id를 자동 생성하여 ~/.ppt-generator/<UUID>/에 결과물을 저장
* load_* 도구에 project_id를 전달하여 저장된 결과물을 로드, 중간 단계부터 재개 가능
* generate_slides_design_spec은 전체 아웃라인 기반으로 design_summary.json을 LLM으로 사전 생성하여 모든 슬라이드의 테마 일관성 유지
* content 슬라이드의 배경색은 design_summary의 background_color로 강제 보정 (title/closing 슬라이드는 null 유지)
* 디자인 스펙 생성 완료 시 slides.html (iframe 컨테이너)도 자동 생성하여 별도 generate_slides 호출 없이 미리보기 가능
```

## Available Tools

| Tool                         | Module           | Description                                                                                        |
| ---------------------------- | ---------------- | -------------------------------------------------------------------------------------------------- |
| `generate_outline`           | `tools/outline/` | 주제와 슬라이드 수를 기반으로 슬라이드 아웃라인 JSON 생성 (title, content_summary, component_hint) |
| `generate_script`            | `tools/script/`  | 아웃라인 JSON을 기반으로 슬라이드별 발표 스크립트 생성                                             |
| `generate_slides_design_spec` | `tools/design/`  | 슬라이드 디자인 스펙 생성 — 전체 또는 slide_indices로 선택적 생성 (서버 내부 병렬 처리)            |
| `modify_design_spec`          | `tools/design/`  | 디자인 스펙의 개별 슬라이드 추가/수정/삭제 (CRUD)                                                  |
| `generate_slides`            | `tools/slides/`  | 디자인 스펙 또는 project_id 기반 HTML 슬라이드 생성 (결정론적 변환)                                |
| `export_pptx`                | `tools/pptx/`    | 디자인 스펙 또는 project_id 기반 편집 가능한 PPTX 내보내기 (결정론적 변환)                         |
| `list_projects`              | `tools/project/` | 기존 프로젝트 목록 조회 (파이프라인 시작 전 호출 권장)                                             |
| `load_project_status`        | `tools/project/` | 프로젝트 상태 및 메타데이터 로드                                                                   |
| `load_outline`               | `tools/project/` | 저장된 아웃라인 JSON 로드                                                                          |
| `load_script`                | `tools/project/` | 저장된 스크립트 JSON 로드                                                                          |
| `load_design_spec`           | `tools/project/` | 저장된 디자인 스펙 로드 (design_spec_dir, slide_count, slide_files)                                |

## Key Data Schemas

내부 도메인 모델은 `interfaces/schemas.py`에 `@dataclass`로, LLM 출력 모델은 `interfaces/llm_output_models.py`에 Pydantic `BaseModel`로 정의되어 있습니다.

### 내부 도메인 모델 (`schemas.py`)

| Schema                                          | 용도                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| `OutlineRequest` / `OutlineResponse`            | 아웃라인 생성 입출력 (topic, num_slides → slides)                              |
| `ScriptRequest` / `ScriptResponse`              | 스크립트 생성 입출력 (outline → slides)                                        |
| `SlideOutline`                                  | 개별 슬라이드 아웃라인 (title, content_summary, component_hint, speaker_notes) |
| `SlidesResponse`                                | HTML 슬라이드 생성 출력 (session_id, html)                                     |
| `ExportPptxResponse`                            | PPTX 내보내기 출력 (pptx_path)                                                 |
| `PptxTextRun` / `PptxParagraph` / `PptxTextBox` | PPTX 텍스트 요소                                                               |
| `PptxShape` / `PptxSlideSpec`                   | PPTX 도형/슬라이드 스펙 (speaker_notes 포함)                                   |
| `DesignSpec`                                    | 프레젠테이션 전체 디자인 스펙 (PptxSlideSpec 리스트)                           |
| `ProjectMetadata`                               | 프로젝트 메타데이터 (topic, num_slides, steps_completed)                       |

### LLM 출력 모델 (`llm_output_models.py`)

| Schema                              | 용도                                                                                           |
| ----------------------------------- | ---------------------------------------------------------------------------------------------- |
| `SlideSpecOutput`                   | strands `structured_output_model`용 Pydantic 모델. `to_dataclass()`로 `PptxSlideSpec`으로 변환 |
| `TextRunOutput` / `ParagraphOutput` | LLM 출력용 텍스트 런/단락                                                                      |
| `TextBoxOutput` / `ShapeOutput`     | LLM 출력용 텍스트박스/도형                                                                     |

### 슬라이드 아웃라인 JSON

```json
{
  "slides": [
    {
      "title": "슬라이드 제목",
      "content_summary": "슬라이드에 담길 핵심 내용 요약",
      "component_hint": "bullets",
      "speaker_notes": ""
    }
  ]
}
```

### component_hint

슬라이드 본문 영역의 시각적 구조를 결정하는 힌트:

| component_hint  | 설명                         |
| --------------- | ---------------------------- |
| `bullets`       | 기본 불릿 포인트 (기본값)    |
| `two_column`    | 2칼럼 레이아웃               |
| `vs_comparison` | VS 비교 패널 (A vs B)        |
| `step_cards`    | 단계별 카드                  |
| `code_block`    | 코드 블록 포함               |
| `arch_diagram`  | 아키텍처 다이어그램 (흐름도) |
| `pipeline`      | 파이프라인 흐름              |
| `quote`         | 인용문 강조                  |
| `summary_grid`  | 요약 그리드 (2x2)            |
| `agenda`        | 목차 섹션                    |
| `info_cards`    | 정보 카드 그리드             |
| `feature_list`  | 기능/특징 리스트             |
| `cta`           | Call-to-Action 강조          |
| `process_flow`  | 프로세스 워크스루            |
| `quote_code`    | 인용문 + 코드 블록 조합      |
| `concept_list`  | 개념 설명 리스트             |

## Coding Conventions

### 새 도구 추가 패턴

1. `tools/` 하위에 새 디렉토리 생성 (`__init__.py`, `controller.py`, `service.py`)
2. `service.py`: Request를 받아 Response를 반환하는 클래스 작성
3. `controller.py`: `register_*_tools(mcp: FastMCP, service: XxxService, project_service: ProjectService)` 함수 작성. 내부에 `@mcp.tool()` 함수 정의
4. `schemas.py`에 Request/Response 데이터클래스 추가
5. `di/container.py`에 Service 생성 프로퍼티 추가 (지연 초기화)
6. `server.py`의 `create_server()`에서 `register_*_tools()` 호출 추가

### 스타일

- 타입 힌트 필수 (`-> None`, `-> str` 등)
- 상수는 `interfaces/constants.py`에 정의
- 프롬프트 템플릿은 `interfaces/prompts/` 모듈에 `.prompt.md` 파일로 정의, `__init__.py`에서 로딩 후 `constants.py`에서 re-export
- MCP 도구 함수에는 한국어 docstring 필수 (클라이언트에 노출됨)

## Testing

- 테스트 프레임워크: pytest
- 테스트 파일: `tests/test_*.py`
- 외부 API(Bedrock/Anthropic) 호출은 mock 처리

```bash
uv run pytest                    # 전체 테스트
uv run pytest tests/test_xxx.py  # 개별 테스트
```

## MCP Client Configuration

Anthropic API 사용 시:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

AWS Bedrock 사용 시 (`~/.aws/credentials` 설정 완료 가정):

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"]
    }
  }
}
```

AWS 환경변수를 직접 지정하는 경우:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "LLM_PROVIDER": "bedrock",
        "AWS_ACCESS_KEY_ID": "AKIA...",
        "AWS_SECRET_ACCESS_KEY": "...",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

Bedrock API key (bearer token) 사용 시:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "LLM_PROVIDER": "bedrock",
        "AWS_BEARER_TOKEN_BEDROCK": "your-api-key",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

## Edge Cases & Fallback Strategies

- **빈 주제 입력** → 입력 검증 후 `ValueError` 발생
- **LLM이 유효하지 않은 JSON 반환** → 재시도 또는 에러 반환
- **알 수 없는 component_hint** → 기본값 "bullets"로 폴백

## Agent-specific Instructions

### Safe to Modify

- `src/ppt_generator/templates/` - 레이아웃 매핑 로직 수정, HTML 템플릿 수정
- `src/ppt_generator/interfaces/` - 상수, 스키마 수정
- 새로운 도구 추가 (`tools/` 하위에 새 모듈 생성)

### Approach with Caution

- `server.py` - 도구 등록 로직
- `di/container.py` - 의존성 주입 설정
- 기존 도구 시그니처 변경 (MCP 클라이언트 호환성에 영향)
- LLM API 호출 파라미터 변경 (비용 및 품질에 영향, Anthropic/Bedrock 양쪽 확인 필요)
- PPTX 변환 로직 (`tools/pptx/service.py`, `slide_builder.py`, `text_formatter.py` - 좌표 변환, 스타일 매핑)
- HTML 렌더링 로직 (`tools/slides/html_renderer.py` - PptxSlideSpec → HTML 변환)
- HTML 템플릿 구조 (`templates/slide.html`, `templates/slides_container.html` - 인라인 CSS, placeholder 구조)
