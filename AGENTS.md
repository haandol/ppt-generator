# PPT Generator MCP Server Guide

## Overview

사용자가 주제를 입력하면 AI가 자동으로 HTML 기반 프레젠테이션을 생성하고, 사용자의 수정 요청을 반영한 뒤 최종적으로 편집 가능한 PPTX로 내보내는 Python MCP 서버입니다.
Amazon Bedrock LLM으로 콘텐츠를 생성하고, Titan Image Generator v2로 시각 자료를 생성하여, HTML/CSS 기반 슬라이드로 자유로운 디자인을 구현한 뒤 최종 PPTX로 변환합니다.
Claude Desktop, Kiro 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

> 📄 **ALPS 설계 문서**: 피쳐 목록, 기능 명세, 인수 기준 등 구현에 필요한 세부 사항은 [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md) (또는 원본 [`docs/ppt-generator.alps.xml`](docs/ppt-generator.alps.xml))를 반드시 확인하세요.
>
> ALPS 문서에 포함된 내용:
> - **Section 1~3**: 프로젝트 개요, MVP 목표, 데모 시나리오
> - **Section 4~5**: 아키텍처, 설계 명세
> - **Section 6**: 요구사항 요약
> - **Section 7**: 피쳐별 상세 명세 (F1~F7) — 사용자 스토리, 흐름, 기술 설명, 엣지 케이스, 인수 기준
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
│   │   ├── images/                # 이미지 생성 도구 (F3)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   ├── pptx/                  # PPTX 내보내기 도구 (F6)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   ├── project/               # 프로젝트 저장/로드 도구 (F7)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   └── slides/                # HTML 슬라이드 생성/수정 도구 (F4/F5)
│   │       ├── controller.py
│   │       └── service.py
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 프롬프트, 상수
│   │   └── schemas.py             # 데이터클래스 (Request/Response)
│   └── templates/
│       └── layout_mapping.py      # 레이아웃 타입 → 슬라이드 레이아웃 매핑
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
- **LLM**: Amazon Bedrock - Claude Opus 4 (`us.anthropic.claude-opus-4-20250514-v1:0`)
- **Image Generation**: Amazon Bedrock - Titan Image Generator v2 (`amazon.titan-image-generator-v2:0`)
- **HTML Parsing**: BeautifulSoup4 (HTML → PPTX 변환용 파싱)
- **PPTX Export**: python-pptx (HTML 세션 → PPTX 변환)

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- AWS 자격 증명 (`~/.aws/credentials` 또는 환경 변수)
  - Amazon Bedrock 모델 접근 권한 필요 (Claude Opus 4, Titan Image Generator v2)
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
  → 아웃라인 (구조화된 JSON — 슬라이드 구성, 요점, 레이아웃)
    → 스크립트 (구체적 — 발표 내용이 채워진 아웃라인)
      → HTML 슬라이드 (코드로 디자인 자유도 최대화 — CSS position:absolute 자유 배치)
        → PPTX (디자인 자유도를 최대한 유지하면서 편집 가능한 포맷으로 변환)
```

**왜 이런 구조인가?**

- **아웃라인 → 스크립트 분리**: 아웃라인은 슬라이드의 뼈대(구조)이고, 스크립트는 살(발표 내용)입니다. 분리하면 구조를 먼저 확정한 뒤 내용을 채울 수 있고, LLM이 각 단계에 집중할 수 있습니다.
- **HTML을 중간 표현으로 사용**: python-pptx로 직접 생성하면 고정 플레이스홀더와 제한된 스타일링으로 디자인 자유도가 크게 떨어집니다. HTML/CSS는 LLM이 코드로 자유롭게 디자인할 수 있는 최적의 중간 표현입니다.
- **HTML → PPTX 변환**: HTML의 자유로운 디자인을 PPTX의 개별 편집 가능한 객체(텍스트박스, 이미지, 도형)로 매핑하여, 디자인 자유도를 최대한 유지하면서도 실무에서 편집할 수 있는 최종 산출물을 제공합니다.

> 관련 ADR: [0011-progressive-refinement-pipeline](../docs/adr/pipeline/0011-progressive-refinement-pipeline.md)

### Processing Pipeline

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: generate_outline   → 슬라이드 아웃라인 JSON 생성 (Bedrock LLM, freeform 기본, speaker_notes 비어있음)
    ↓
F2: generate_script    → 아웃라인 기반 슬라이드별 스크립트 생성 (speaker_notes 채움)
    ↓
F3: generate_images    → 슬라이드별 이미지 생성 (Titan Image Generator v2)
    ↓
F4: generate_slides    → 아웃라인 + 이미지 → HTML/CSS 슬라이드 생성 (세션 기반)
    ↓ (선택)
F5: modify_slides      → HTML 슬라이드 수정 (사용자 요청 반영)
    ↓
F6: export_pptx        → HTML 세션 → 편집 가능한 PPTX 파일 내보내기
    ↓
출력: 편집 가능한 .pptx 파일

* 모든 도구가 project_id를 자동 생성하여 ~/.ppt-generator/<UUID>/에 결과물을 저장
* F7: load_* 도구에 project_id를 전달하여 저장된 결과물을 로드, 중간 단계부터 재개 가능
```

## Available Tools

| Tool | Module | Description |
|------|--------|-------------|
| `generate_outline` | `tools/outline/` | 주제와 슬라이드 수를 기반으로 슬라이드 아웃라인 JSON 생성 (기본 freeform 모드, speaker_notes 비어있음) |
| `generate_script` | `tools/script/` | 아웃라인 JSON을 기반으로 슬라이드별 발표자 노트(speaker_notes) 생성 |
| `generate_images` | `tools/images/` | 아웃라인의 image_idea를 기반으로 Titan Image v2로 슬라이드별 이미지 생성 |
| `generate_slides` | `tools/slides/` | 아웃라인과 이미지를 결합하여 HTML/CSS 슬라이드 생성 (세션 반환) |
| `modify_slides` | `tools/slides/` | 기존 HTML 슬라이드를 사용자 요청에 따라 수정 |
| `export_pptx` | `tools/pptx/` | 세션의 HTML 슬라이드를 편집 가능한 PPTX 파일로 내보내기 |
| `load_project_status` | `tools/project/` | 프로젝트 상태 및 메타데이터 로드 |
| `load_outline` | `tools/project/` | 저장된 아웃라인 JSON 로드 |
| `load_script` | `tools/project/` | 저장된 스크립트 JSON 로드 |
| `load_images` | `tools/project/` | 저장된 이미지 메타 JSON 로드 |
| `load_slides_html` | `tools/project/` | 저장된 HTML 슬라이드 로드 및 세션 복원 |

## Key Data Schemas

`interfaces/schemas.py`에 `@dataclass`로 정의되어 있습니다.

| Schema | 용도 |
|--------|------|
| `OutlineRequest` / `OutlineResponse` | 아웃라인 생성 입출력 (topic, num_slides → slides) |
| `ScriptRequest` / `ScriptResponse` | 스크립트 생성 입출력 (outline → slides with speaker_notes) |
| `SlideOutline` | 개별 슬라이드 아웃라인 (title, bullets, image_idea, layout_type, speaker_notes, elements) |
| `SlideElement` | freeform 레이아웃의 개별 요소 (type, left, top, width, height, content, font_size_pt, bold) |
| `ImageRequest` / `ImageResult` / `ImageResponse` | 이미지 생성 입출력 |
| `SlidesRequest` / `SlidesResponse` | HTML 슬라이드 생성 입출력 (slides, image_paths → session_id, html) |
| `ExportPptxRequest` / `ExportPptxResponse` | PPTX 내보내기 입출력 (session_id → pptx_path) |
| `ProjectMetadata` | 프로젝트 메타데이터 (topic, num_slides, steps_completed) |

### 슬라이드 아웃라인 JSON

```json
{
  "slides": [
    {
      "title": "슬라이드 제목",
      "bullets": ["요점 1", "요점 2"],
      "image_idea": "이미지 설명 (영어 프롬프트로 변환됨)",
      "layout_type": "freeform (기본) | title | text_image | text_only | chart | closing",
      "speaker_notes": "발표자 노트 (스크립트 내용)",
      "elements": []
    }
  ]
}
```

### 레이아웃 타입

| layout_type  | 설명                      | 비고                     |
| ------------ | ------------------------- | ------------------------ |
| `title`      | 제목 슬라이드             | 첫 번째 슬라이드         |
| `text_image` | 좌측 텍스트 + 우측 이미지 | -                        |
| `text_only`  | 전체 텍스트               | 알 수 없는 타입의 폴백   |
| `chart`      | 차트 중심                 | -                        |
| `closing`    | 마무리 슬라이드           | 마지막 슬라이드          |
| `freeform`   | 자유 배치 (좌표 기반)     | **기본 모드**, elements 배열 사용 |

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
- **알 수 없는 layout_type** → `text_only` 레이아웃으로 폴백
- **image_idea 없는 슬라이드** → 이미지 생성 건너뜀 (`SKIP_IMAGE_LAYOUT_TYPES`에 정의)
- **Titan Image API 호출 실패** → 해당 슬라이드는 이미지 없이 진행, 에러 로그 기록
- **이미지 파일 누락** → 텍스트만으로 슬라이드 구성
- **이미지 base64 디코딩 실패** → 해당 이미지 건너뛰고 텍스트만 배치

## Agent-specific Instructions

### Safe to Modify

- `src/ppt_generator/templates/` - 레이아웃 매핑 로직 수정
- `src/ppt_generator/interfaces/` - 상수, 스키마 수정
- 새로운 도구 추가 (`tools/` 하위에 새 모듈 생성)

### Approach with Caution

- `server.py` - 도구 등록 로직
- `di/container.py` - 의존성 주입 설정
- 기존 도구 시그니처 변경 (MCP 클라이언트 호환성에 영향)
- Bedrock API 호출 파라미터 변경 (비용 및 품질에 영향)
- PPTX 변환 로직 (`tools/pptx/service.py` - 좌표 변환, 스타일 매핑)
