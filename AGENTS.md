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
│   │   ├── pptx/                  # PPTX 내보내기 도구 (F5)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   ├── project/               # 프로젝트 저장/로드 도구 (F6)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   └── slides/                # HTML 슬라이드 생성/수정 도구 (F3/F4)
│   │       ├── controller.py
│   │       └── service.py
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 프롬프트, 상수
│   │   └── schemas.py             # 데이터클래스 (Request/Response)
│   └── templates/
│       ├── slides.html     # HTML 슬라이드 템플릿 (인라인 CSS, 수직 스크롤)
│       └── layout_mapping.py      # 레이아웃 인덱스 → 슬라이드 레이아웃 매핑
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
- **LLM**: Amazon Bedrock - Claude Opus 4.6 (`us.anthropic.claude-opus-4-6-v1`)
- **Outline LLM**: Amazon Bedrock - Claude Sonnet 4.5 (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- **Slide Framework**: 순수 HTML/CSS (인라인 스타일, JavaScript 없음, `templates/slides.html` 템플릿)
- **HTML Parsing**: BeautifulSoup4 (HTML → PPTX 변환용 파싱)
- **PPTX Export**: python-pptx (HTML 세션 → PPTX 변환)

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
      → HTML 슬라이드 (LLM이 <section> 요소 생성 → 템플릿에 삽입)
        → PPTX (디자인 자유도를 최대한 유지하면서 편집 가능한 포맷으로 변환)
```

**왜 이런 구조인가?**

- **아웃라인 → 스크립트 분리**: 아웃라인은 슬라이드의 뼈대(구조)이고, 스크립트는 살(발표 내용)입니다. 분리하면 구조를 먼저 확정한 뒤 내용을 채울 수 있고, LLM이 각 단계에 집중할 수 있습니다.
- **HTML을 중간 표현으로 사용**: python-pptx로 직접 생성하면 고정 플레이스홀더와 제한된 스타일링으로 디자인 자유도가 크게 떨어집니다. HTML/CSS (인라인 스타일)를 사용하면 LLM이 `<section>` 요소만 생성하고, 서비스가 템플릿(`slides.html`)에 삽입하여 일관된 구조의 슬라이드를 만들 수 있습니다. 브라우저에서 수직 스크롤로 디자인을 확인할 수 있습니다.
- **레이아웃 골격(Skeleton) 기반 위치 강제**: `LAYOUT_REGIONS` 좌표를 사용하여 `position:absolute` div 골격을 코드로 생성하고, LLM은 각 `data-region` div 내부 컨텐츠만 채웁니다. 후처리에서 `_validate_region_styles()`로 좌표를 검증/복원하여, LLM이 좌표를 변경하더라도 원래 위치가 보장됩니다. PPTX 변환 시 `data-region` div의 좌표를 직접 사용하여 정확한 위치에 요소를 배치합니다.
- **HTML → PPTX 변환**: `<section>` 태그 내 HTML 요소를 PPTX의 개별 편집 가능한 객체(텍스트박스, 이미지, 도형)로 매핑하여, 디자인 자유도를 최대한 유지하면서도 실무에서 편집할 수 있는 최종 산출물을 제공합니다.

> 관련 ADR: [0011-progressive-refinement-pipeline](../docs/adr/pipeline/0011-progressive-refinement-pipeline.md)

### Processing Pipeline

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: generate_outline   → 슬라이드 아웃라인 JSON 생성 (Bedrock LLM, title/content_summary/layout_index)
    ↓
F2: generate_script    → 아웃라인 기반 슬라이드별 발표 스크립트 생성
    ↓
F3: generate_slides    → 아웃라인 → HTML 슬라이드 생성 (레이아웃 골격 생성 → LLM이 영역 내부 컨텐츠 생성 → 좌표 검증 → 템플릿 삽입)
    ↓ (선택)
F4: modify_slides      → HTML 슬라이드 수정 (사용자 요청 반영)
    ↓
F5: export_pptx        → HTML 세션 → 편집 가능한 PPTX 파일 내보내기
    ↓
출력: 편집 가능한 .pptx 파일

* 모든 도구가 project_id를 자동 생성하여 ~/.ppt-generator/<UUID>/에 결과물을 저장
* F6: load_* 도구에 project_id를 전달하여 저장된 결과물을 로드, 중간 단계부터 재개 가능
```

## Available Tools

| Tool | Module | Description |
|------|--------|-------------|
| `generate_outline` | `tools/outline/` | 주제와 슬라이드 수를 기반으로 슬라이드 아웃라인 JSON 생성 (title, content_summary, layout_index) |
| `generate_script` | `tools/script/` | 아웃라인 JSON을 기반으로 슬라이드별 발표 스크립트 생성 |
| `generate_slides` | `tools/slides/` | 아웃라인 기반 HTML 슬라이드 생성 (LLM이 section 생성 → 템플릿 삽입, 세션 반환) |
| `modify_slides` | `tools/slides/` | 기존 HTML 슬라이드를 사용자 요청에 따라 수정 |
| `export_pptx` | `tools/pptx/` | 세션의 HTML 슬라이드를 편집 가능한 PPTX 파일로 내보내기 |
| `load_project_status` | `tools/project/` | 프로젝트 상태 및 메타데이터 로드 |
| `load_outline` | `tools/project/` | 저장된 아웃라인 JSON 로드 |
| `load_script` | `tools/project/` | 저장된 스크립트 JSON 로드 |
| `load_slides_html` | `tools/project/` | 저장된 HTML 슬라이드 로드 및 세션 복원 |

## Key Data Schemas

`interfaces/schemas.py`에 `@dataclass`로 정의되어 있습니다.

| Schema | 용도 |
|--------|------|
| `OutlineRequest` / `OutlineResponse` | 아웃라인 생성 입출력 (topic, num_slides → slides) |
| `ScriptRequest` / `ScriptResponse` | 스크립트 생성 입출력 (outline → slides) |
| `SlideOutline` | 개별 슬라이드 아웃라인 (title, content_summary, layout_index) |
| `SlidesRequest` / `SlidesResponse` | HTML 슬라이드 생성 입출력 (slides → session_id, html) |
| `ExportPptxRequest` / `ExportPptxResponse` | PPTX 내보내기 입출력 (session_id → pptx_path) |
| `ProjectMetadata` | 프로젝트 메타데이터 (topic, num_slides, steps_completed) |

### 슬라이드 아웃라인 JSON

```json
{
  "slides": [
    {
      "title": "슬라이드 제목",
      "content_summary": "슬라이드에 담길 핵심 내용 요약",
      "layout_index": 0
    }
  ]
}
```

### 레이아웃 인덱스

| layout_index | 설명                      | 비고                     |
| ------------ | ------------------------- | ------------------------ |
| `0`          | 제목 슬라이드             | 첫 번째 슬라이드, 위치 구조적 강제 |
| `22`         | 전체 텍스트               | 알 수 없는 인덱스의 폴백, 위치 구조적 강제 |
| `21`         | 차트 중심                 | 위치 구조적 강제         |
| `87`         | 마무리 슬라이드           | 마지막 슬라이드, 위치 구조적 강제 |
| `88`         | 자유 배치 (Blank)         | 특수 레이아웃, 위치 구조적 강제 |

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
- 프롬프트 템플릿은 `constants.py`에 문자열 상수로 관리
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
- **알 수 없는 layout_index** → `text_only`(22) 레이아웃으로 폴백

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
- PPTX 변환 로직 (`tools/pptx/service.py` - section 파싱, 좌표 변환, 스타일 매핑)
- HTML 템플릿 구조 (`templates/slides.html` - 인라인 CSS, placeholder 구조)
