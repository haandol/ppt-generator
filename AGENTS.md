# PPT Generator MCP Server Guide

## Overview

사용자가 주제를 입력하면 AI가 자동으로 HTML 기반 프레젠테이션을 생성하고, 사용자의 수정 요청을 반영한 뒤 최종적으로 편집 가능한 PPTX로 내보내는 Python MCP 서버입니다.
Amazon Bedrock LLM으로 콘텐츠를 생성하고, HTML 프레임워크 기반 슬라이드로 자유로운 디자인을 구현한 뒤 최종 PPTX로 변환합니다.
Claude Desktop, Kiro 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

> 📄 **ALPS 설계 문서**: 피쳐 목록, 기능 명세, 인수 기준 등 구현에 필요한 세부 사항은 [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md) (또는 원본 [`docs/ppt-generator.alps.xml`](docs/ppt-generator.alps.xml))를 반드시 확인하세요.
>
> ALPS 문서에 포함된 내용:
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
│   │   │   └── service.py         # Bedrock LLM 호출 로직
│   │   ├── script/                # 발표 스크립트 생성 도구 (F2)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   ├── design/                # 디자인 스펙 생성 도구
│   │   │   ├── controller.py      # MCP 인터페이스
│   │   │   └── service.py         # LLM 기반 디자인 스펙 생성
│   │   ├── pptx/                  # PPTX 내보내기 도구 (F5)
│   │   │   ├── controller.py      # MCP 인터페이스
│   │   │   ├── service.py         # 오케스트레이션 (ExportService)
│   │   │   ├── slide_builder.py   # PptxSlideSpec → python-pptx 변환
│   │   │   ├── llm_converter.py   # HTML → PptxSlideSpec LLM 변환 (기존 경로)
│   │   │   ├── dom_extractor.py   # Playwright DOM 추출 (기존 경로)
│   │   │   ├── html_parser.py     # HTML 파싱 유틸리티
│   │   │   └── style_utils.py     # 폰트/스타일 변환 유틸리티
│   │   ├── project/               # 프로젝트 저장/로드 도구 (F6)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   └── slides/                # HTML 슬라이드 생성/수정 도구 (F3/F4)
│   │       ├── controller.py
│   │       ├── css_inliner.py     # CSS 클래스 → inline style 병합 유틸리티
│   │       └── service.py
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 수치 상수, 프롬프트 re-export
│   │   ├── schemas.py             # 데이터클래스 (Request/Response)
│   │   ├── spec_utils.py          # PptxSlideSpec 파싱/검증/직렬화 공유 유틸리티
│   │   ├── utils.py               # parse_outline_json 등 공용 파싱 유틸리티
│   │   └── prompts/               # 프롬프트 템플릿 모듈
│   │       ├── __init__.py        # 전체 프롬프트 상수 re-export
│   │       ├── design_prompts.py  # 디자인 스펙 생성 프롬프트
│   │       ├── outline_prompts.py # 아웃라인 생성 프롬프트
│   │       ├── pptx_prompts.py    # PPTX 변환 프롬프트
│   │       ├── script_prompts.py  # 스크립트 생성 프롬프트
│   │       └── slides_prompts.py  # 슬라이드 생성/수정 프롬프트
│   └── templates/
│       ├── slides.html            # HTML 슬라이드 템플릿 (TailwindCSS + 인라인 CSS, 수직 스크롤)
│       └── layout_mapping.py      # layout_index → 슬라이드 레이아웃 매핑 (97종)
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
- **LLM (슬라이드 생성/수정)**: Amazon Bedrock - Claude Opus 4.6 (`us.anthropic.claude-opus-4-6-v1`, 32K tokens)
- **LLM (아웃라인/스크립트)**: Amazon Bedrock - Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`, 16K tokens)
- **LLM (PPTX 변환)**: Amazon Bedrock - Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`, 8K tokens) — 기존 HTML 경로에서만 사용
- **Slide Framework**: 순수 HTML/CSS (TailwindCSS + 인라인 스타일, JavaScript 없음, `templates/slides.html` 템플릿)
- **HTML Parsing**: BeautifulSoup4 (HTML → PPTX 변환용 파싱, 기존 경로)
- **Screenshot**: Playwright (HTML → 이미지 캡처, 기존 PPTX 변환 시 활용)
- **PPTX Export**: python-pptx (디자인 스펙 직접 생성 또는 HTML 세션 → PPTX 변환)

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- AWS 자격 증명 (`~/.aws/credentials` 또는 환경 변수)
  - Amazon Bedrock 모델 접근 권한 필요 (Claude Opus 4.6, Claude Sonnet 4.5)
  - 리전: `us-east-1`

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
- **DIContainer** (`di/container.py`): Bedrock 모델, Agent, Service 인스턴스를 생성하고 연결합니다. 지연 초기화(lazy init) 패턴을 사용합니다.

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
> HTML과 PPTX를 각각 결정론적으로 생성합니다. 기존의 HTML → PPTX 역변환(DOM 추출/LLM 변환) 없이
> 단일 소스에서 두 출력을 생성하므로 정확도가 높습니다.

**핵심 원칙:**

- **파일 기반 통신**: 모든 도구는 결과를 파일로 저장하고 파일 경로를 반환합니다. `project_id`만으로 도구를 체이닝할 수 있어 인라인 JSON 전달이 불필요하며, MCP 클라이언트의 컨텍스트 윈도우 토큰 사용을 최적화합니다.
- **슬라이드 단위 세분화**: `modify_design_spec` 도구로 중간 산출물(디자인 스펙)의 개별 슬라이드를 추가/수정/삭제할 수 있어, 전체 재생성 없이 반복적 개선이 가능합니다.

**왜 이런 구조인가?**

- **아웃라인 → 스크립트 분리**: 아웃라인은 슬라이드의 뼈대(구조)이고, 스크립트는 살(발표 내용)입니다. 분리하면 구조를 먼저 확정한 뒤 내용을 채울 수 있고, LLM이 각 단계에 집중할 수 있습니다.
- **HTML을 중간 표현으로 사용**: python-pptx로 직접 생성하면 고정 플레이스홀더와 제한된 스타일링으로 디자인 자유도가 크게 떨어집니다. HTML/CSS (인라인 스타일)를 사용하면 LLM이 `<section>` 요소만 생성하고, 서비스가 템플릿(`slides.html`)에 삽입하여 일관된 구조의 슬라이드를 만들 수 있습니다. 브라우저에서 수직 스크롤로 디자인을 확인할 수 있습니다.
- **자유 형식 HTML 슬라이드 생성**: LLM이 아웃라인(title, content_summary, component_hint)을 기반으로 `<section>` 요소의 전체 HTML을 자유롭게 생성합니다. 스켈레톤이나 고정 좌표 제약 없이, 시스템 프롬프트의 디자인 가이드라인을 따라 1280x720px 규격의 슬라이드를 작성합니다.
- **HTML → PPTX 변환**: `<section>` 태그 내 HTML 요소를 PPTX의 개별 편집 가능한 객체(텍스트박스, 이미지, 도형)로 매핑하여, 디자인 자유도를 최대한 유지하면서도 실무에서 편집할 수 있는 최종 산출물을 제공합니다.

> 관련 ADR: [0011-progressive-refinement-pipeline](../docs/adr/pipeline/0011-progressive-refinement-pipeline.md)

### Processing Pipeline

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: generate_outline       → 슬라이드 아웃라인 JSON 생성 (Bedrock LLM, title/content_summary/component_hint)
    ↓
    ⏸ 사용자 확인           → 아웃라인 구조 검토 및 승인 (수정 시 F1 재호출)
    ↓
F2: generate_script        → 아웃라인 기반 슬라이드별 발표 스크립트 생성
    ↓
    generate_design_spec   → 스크립트 아웃라인 → PptxSlideSpec JSON 디자인 스펙 생성 (LLM)
    ↓
    ⏸ (선택) modify_design_spec → 개별 슬라이드 추가/수정/삭제 (project_id로 참조)
    ↓
    ├→ generate_slides(project_id=...)       → project_id로 디자인 스펙 자동 로드 → HTML 변환 (권장)
    │    ↓ (선택)
    │   modify_slides      → HTML 슬라이드 수정 (사용자 요청 반영)
    │
    └→ export_pptx(project_id=...)          → project_id로 디자인 스펙 자동 로드 → PPTX 생성 (권장)
    ↓
출력: 편집 가능한 .pptx 파일

* project_id 기반 체이닝 (권장): generate_design_spec → generate_slides(project_id=...) → export_pptx(project_id=...)
* 기존 경로 (design_spec_json 직접 전달, outline_json → session_id)도 하위 호환 유지
* 모든 도구가 project_id를 자동 생성하여 ~/.ppt-generator/<UUID>/에 결과물을 저장
* load_* 도구에 project_id를 전달하여 저장된 결과물을 로드, 중간 단계부터 재개 가능
```

## Available Tools

| Tool | Module | Description |
|------|--------|-------------|
| `generate_outline` | `tools/outline/` | 주제와 슬라이드 수를 기반으로 슬라이드 아웃라인 JSON 생성 (title, content_summary, component_hint) |
| `generate_script` | `tools/script/` | 아웃라인 JSON을 기반으로 슬라이드별 발표 스크립트 생성 |
| `generate_design_spec` | `tools/design/` | 아웃라인 → PptxSlideSpec JSON 디자인 스펙 생성 (LLM) |
| `modify_design_spec` | `tools/design/` | 디자인 스펙의 개별 슬라이드 추가/수정/삭제 (CRUD) |
| `generate_slides` | `tools/slides/` | 아웃라인, 디자인 스펙, 또는 project_id 기반 HTML 슬라이드 생성 |
| `modify_slides` | `tools/slides/` | 기존 HTML 슬라이드를 사용자 요청에 따라 수정 |
| `export_pptx` | `tools/pptx/` | 세션 HTML 또는 디자인 스펙을 편집 가능한 PPTX로 내보내기 |
| `list_projects` | `tools/project/` | 기존 프로젝트 목록 조회 (파이프라인 시작 전 호출 권장) |
| `load_project_status` | `tools/project/` | 프로젝트 상태 및 메타데이터 로드 |
| `load_outline` | `tools/project/` | 저장된 아웃라인 JSON 로드 |
| `load_script` | `tools/project/` | 저장된 스크립트 JSON 로드 |
| `load_design_spec` | `tools/project/` | 저장된 디자인 스펙 JSON 로드 |
| `load_slides_html` | `tools/project/` | 저장된 HTML 슬라이드 로드 및 세션 복원 |

## Key Data Schemas

`interfaces/schemas.py`에 `@dataclass`로 정의되어 있습니다.

| Schema | 용도 |
|--------|------|
| `OutlineRequest` / `OutlineResponse` | 아웃라인 생성 입출력 (topic, num_slides → slides) |
| `ScriptRequest` / `ScriptResponse` | 스크립트 생성 입출력 (outline → slides) |
| `SlideOutline` | 개별 슬라이드 아웃라인 (title, content_summary, component_hint, speaker_notes) |
| `SlidesRequest` / `SlidesResponse` | HTML 슬라이드 생성 입출력 (slides → session_id, html) |
| `ExportPptxRequest` / `ExportPptxResponse` | PPTX 내보내기 입출력 (session_id → pptx_path) |
| `PptxTextRun` / `PptxParagraph` / `PptxTextBox` | PPTX 텍스트 요소 |
| `PptxShape` / `PptxSlideSpec` | PPTX 도형/슬라이드 스펙 (speaker_notes 포함) |
| `DesignSpec` / `DesignSpecRequest` / `DesignSpecResponse` | 디자인 스펙 생성 입출력 |
| `ProjectMetadata` | 프로젝트 메타데이터 (topic, num_slides, steps_completed) |

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

| component_hint | 설명 |
|----------------|------|
| `bullets` | 기본 불릿 포인트 (기본값) |
| `two_column` | 2칼럼 레이아웃 |
| `vs_comparison` | VS 비교 패널 (A vs B) |
| `step_cards` | 단계별 카드 |
| `code_block` | 코드 블록 포함 |
| `arch_diagram` | 아키텍처 다이어그램 (흐름도) |
| `pipeline` | 파이프라인 흐름 |
| `quote` | 인용문 강조 |
| `summary_grid` | 요약 그리드 (2x2) |
| `agenda` | 목차/안건 리스트 |
| `info_cards` | 정보 카드 그리드 |
| `feature_list` | 기능/특징 리스트 |
| `cta` | Call-to-Action 강조 |
| `process_flow` | 프로세스 워크스루 |
| `quote_code` | 인용문 + 코드 블록 조합 |
| `concept_list` | 개념 설명 리스트 |

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
- 프롬프트 템플릿은 `interfaces/prompts/` 모듈에 정의, `constants.py`에서 re-export
- MCP 도구 함수에는 한국어 docstring 필수 (클라이언트에 노출됨)

## Testing

- 테스트 프레임워크: pytest
- 테스트 파일: `tests/test_*.py`
- 외부 API(Bedrock) 호출은 mock 처리

```bash
uv run pytest                    # 전체 테스트
uv run pytest tests/test_xxx.py  # 개별 테스트
```

## MCP Client Configuration

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
- Bedrock API 호출 파라미터 변경 (비용 및 품질에 영향)
- PPTX 변환 로직 (`tools/pptx/service.py` - section 파싱, 좌표 변환, 스타일 매핑, LLM 변환)
- HTML 템플릿 구조 (`templates/slides.html` - TailwindCSS + 인라인 CSS, placeholder 구조)
- CSS 인라이너 (`tools/slides/css_inliner.py` - 클래스 → 인라인 스타일 병합)
