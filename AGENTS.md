# PPT Generator MCP Server Guide

## Overview

사용자가 주제를 입력하면 AI가 자동으로 HTML 기반 프레젠테이션을 생성하고, 사용자의 수정 요청을 반영한 뒤 최종적으로 편집 가능한 PPTX로 내보내는 Python MCP 서버입니다.
Amazon Bedrock LLM으로 콘텐츠를 생성하고, Titan Image Generator v2로 시각 자료를 생성하여, HTML/CSS 기반 슬라이드로 자유로운 디자인을 구현한 뒤 최종 PPTX로 변환합니다.
Claude Desktop, Kiro 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

## Directory Structure

```
ppt-generator/
├── src/ppt_generator/
│   ├── server.py                  # MCP 서버 진입점 + 도구 등록
│   ├── di/
│   │   └── container.py           # 의존성 주입 컨테이너
│   ├── tools/
│   │   ├── script/                # 발표 스크립트 생성 도구 (F1)
│   │   │   ├── controller.py      # MCP 인터페이스
│   │   │   └── service.py         # Bedrock LLM 호출 로직
│   │   ├── outline/               # 슬라이드 아웃라인 생성 도구 (F2)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   ├── images/                # 이미지 생성 도구 (F3)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   ├── slides/                # HTML 슬라이드 생성 + 수정 도구 (F4, F5)
│   │   │   ├── controller.py
│   │   │   └── service.py
│   │   └── export/                # PPTX 내보내기 도구 (F6)
│   │       ├── controller.py
│   │       └── service.py
│   ├── interfaces/
│   │   ├── constants.py           # 상수 정의
│   │   └── schemas.py             # 데이터 스키마 (아웃라인 JSON 등)
│   └── templates/
│       └── layout_mapping.py      # 레이아웃 타입 → 슬라이드 레이아웃 매핑
├── generate_images.py             # 이미지 생성 유틸리티 (standalone)
├── tests/
├── ppt-generator.alps.xml         # ALPS 설계 문서
└── pyproject.toml
```

## Technology Stack

- **Protocol**: Model Context Protocol (MCP)
- **Language**: Python 3.13+
- **Package Manager**: uv
- **Agent Framework**: AWS Strands SDK
- **LLM**: Amazon Bedrock - Claude Opus 4.6
- **Image Generation**: Amazon Bedrock - Titan Image Generator v2
- **Slide Rendering**: HTML/CSS (자유 레이아웃)
- **PPTX Export**: python-pptx (HTML → PPTX 변환)
- **HTML Parsing**: BeautifulSoup / lxml

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

Controller-Service 패턴을 사용합니다:

- **Controller**: MCP 도구 인터페이스 (docstring 포함)
- **Service**: 비즈니스 로직 (Bedrock API 호출, HTML 생성/수정, PPTX 변환 등)
- **DIContainer**: 의존성 주입을 통한 느슨한 결합

### Processing Pipeline

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: 발표 스크립트 생성 (Bedrock Claude Opus 4.6)
    ↓
F2: 슬라이드 아웃라인 생성 (Bedrock LLM)
    ↓
F3: 슬라이드별 이미지 생성 (Titan Image Generator v2)
    ↓
F4: HTML/CSS 슬라이드 생성 (Bedrock LLM)
    ↓
F5: 사용자 수정 요청 반영 (인터랙티브 수정 루프)
    ↓
F6: PPTX 내보내기 (python-pptx, HTML → PPTX 변환)
    ↓
출력: 편집 가능한 .pptx 파일
```

## Available Tools

### Script Tool (F1)

| Tool | Description |
|------|-------------|
| `generate_script` | 주제와 슬라이드 수를 기반으로 발표 스크립트 생성 |

### Outline Tool (F2)

| Tool | Description |
|------|-------------|
| `generate_outline` | 발표 스크립트를 슬라이드 아웃라인 JSON으로 변환 (제목, 본문, 이미지 아이디어, 레이아웃 타입 포함) |

### Image Tool (F3)

| Tool | Description |
|------|-------------|
| `generate_images` | 아웃라인의 image_idea를 기반으로 Titan Image v2로 슬라이드별 이미지 생성 |

### Slides Tool (F4, F5)

| Tool | Description |
|------|-------------|
| `generate_slides` | 아웃라인과 이미지를 결합하여 HTML/CSS 기반 슬라이드 생성. 세션 ID 반환 |
| `modify_slides` | 세션 ID와 자연어 수정 요청을 받아 HTML 슬라이드 업데이트 |

### Export Tool (F6)

| Tool | Description |
|------|-------------|
| `export_pptx` | 최종 확정된 HTML 슬라이드를 편집 가능한 PPTX 파일로 내보내기 |

## Key Data Schemas

### 슬라이드 아웃라인 JSON

```json
{
  "slides": [
    {
      "title": "슬라이드 제목",
      "bullets": ["요점 1", "요점 2"],
      "image_idea": "이미지 설명 (영어 프롬프트로 변환됨)",
      "layout_type": "title | text_image | text_only | chart | closing",
      "speaker_notes": "발표자 노트 (스크립트 내용)"
    }
  ]
}
```

### 레이아웃 타입 매핑

| layout_type | 설명 | 폴백 |
|-------------|------|------|
| `title` | 제목 슬라이드 레이아웃 | - |
| `text_image` | 좌측 텍스트 + 우측 이미지 | - |
| `text_only` | 전체 텍스트 레이아웃 | 알 수 없는 타입의 기본값 |
| `chart` | 차트 중심 레이아웃 | - |
| `closing` | 마무리 슬라이드 레이아웃 | - |

## MCP Client Configuration

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ppt-generator",
        "run",
        "ppt-generator"
      ]
    }
  }
}
```

## Edge Cases & Fallback Strategies

- **빈 주제 입력** → 입력 검증 후 에러 반환
- **LLM이 유효하지 않은 JSON 반환** → 재시도 또는 에러 반환
- **알 수 없는 layout_type** → `text_only` 레이아웃으로 폴백
- **image_idea 없는 슬라이드** → 이미지 생성 건너뜀
- **Titan Image API 호출 실패** → 해당 슬라이드는 이미지 없이 진행, 에러 로그 기록
- **이미지 파일 누락** → 텍스트만으로 슬라이드 구성
- **LLM이 유효하지 않은 HTML 반환** → 기본 구조로 감싸서 반환하거나 재시도
- **존재하지 않는 세션 ID** → 에러 반환
- **HTML에 복잡한 CSS (gradient, animation 등)** → PPTX에서 지원되는 범위로 근사 변환
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
- HTML → PPTX 변환 로직 (좌표 변환, 스타일 매핑)
