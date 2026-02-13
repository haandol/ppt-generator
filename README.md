# PPT Generator

주제를 입력하면 AI가 자동으로 프레젠테이션을 생성하고, 사용자의 수정 요청을 반영한 뒤 편집 가능한 PPTX로 내보내는 MCP 서버입니다.

Amazon Bedrock Claude로 콘텐츠를 생성하고, 두 가지 경로로 슬라이드를 생성합니다:
- **디자인 스펙 경로 (신규)**: LLM이 PptxSlideSpec JSON으로 정밀한 레이아웃을 설계하고, 단일 소스에서 HTML 미리보기와 PPTX를 각각 결정론적으로 생성
- **HTML 경로 (기존)**: LLM이 자유 형식 HTML/CSS 슬라이드를 생성하고, HTML 역분석 폴백 체인으로 PPTX 변환

Claude Desktop, Kiro 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

## 처리 파이프라인

### 설계 철학: 점진적 구체화 (Progressive Refinement)

파이프라인은 **추상에서 구체로** 단계적으로 변환하면서, 각 단계에서 디자인 자유도를 최대한 보존하도록 설계되었습니다.

```
텍스트 (가장 추상적)       — 사용자가 주제만 입력
  → 아웃라인 (구조화)      — 슬라이드 구성·요점·레이아웃을 JSON으로 정리
    → 스크립트 (구체적)     — 발표 내용(speaker_notes)을 채움
      → 디자인 스펙         — PptxSlideSpec JSON으로 정밀한 레이아웃 설계
        ├→ HTML 슬라이드    — 결정론적 변환, 브라우저 미리보기용
        └→ PPTX             — SlideBuilder 직접 사용, 편집 가능한 포맷
```

디자인 스펙(PptxSlideSpec JSON)을 중간 표현으로 사용하여, 단일 소스에서 HTML과 PPTX를 각각 결정론적으로 생성합니다. LLM이 각 요소의 좌표/크기/서식을 JSON으로 정밀하게 설계하고, 이를 기반으로 HTML 미리보기(position:absolute 변환)와 PPTX(SlideBuilder 직접 호출)를 생성합니다. 기존 HTML 경로(LLM이 자유 형식 HTML/CSS 생성 → HTML 역분석 PPTX 변환)도 하위 호환을 위해 유지됩니다.

### 파이프라인 흐름

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: generate_outline       → 슬라이드 아웃라인 JSON 생성
    ↓
    ⏸ 사용자 확인           → 아웃라인 구조 검토 및 승인 (수정 시 F1 재호출)
    ↓
F2: generate_script        → 아웃라인 기반 발표 스크립트 생성 (speaker_notes 채움)
    ↓
    ┌─────────────────────── 디자인 스펙 경로 (신규, 권장) ───────────────────────┐
    │ generate_design_spec   → PptxSlideSpec JSON 디자인 스펙 생성               │
    │     ↓                                                                       │
    │ F3: generate_slides    → 디자인 스펙 → HTML 결정론적 변환 (미리보기)        │
    │     ↓ (선택)                                                                │
    │ F4: modify_slides      → 사용자 수정 요청 반영                              │
    │     ↓                                                                       │
    │ F5: export_pptx        → 디자인 스펙 → PPTX 직접 생성 (SlideBuilder)       │
    └─────────────────────────────────────────────────────────────────────────────┘
    ┌─────────────────────── HTML 경로 (기존, 하위 호환) ─────────────────────────┐
    │ F3: generate_slides    → 아웃라인 → HTML 슬라이드 생성 (LLM)               │
    │     ↓ (선택)                                                                │
    │ F4: modify_slides      → 사용자 수정 요청 반영                              │
    │     ↓                                                                       │
    │ F5: export_pptx        → HTML → PPTX 변환 (DOM추출/LLM변환/룰기반 폴백)    │
    └─────────────────────────────────────────────────────────────────────────────┘
    ↓
출력: .pptx 파일 경로
```

모든 도구는 `project_id`를 자동 생성하여 `~/.ppt-generator/<UUID>/`에 결과물을 저장합니다. `load_*` 도구에 `project_id`를 전달하면 저장된 결과물을 불러와 중간 단계부터 재개할 수 있습니다.

### 프로젝트 디렉토리 구조

```
~/.ppt-generator/<UUID>/
  project.json         # 메타데이터 (주제, 슬라이드 수, 단계 완료 상태)
  outline.json         # F1 출력
  script.json          # F2 출력
  design_spec.json     # 디자인 스펙 출력 (PptxSlideSpec JSON)
  slides.html          # F3/F4 출력
  slides_meta.json     # 세션 메타 (session_id)
  presentation.pptx    # F5 출력
```

## 요구사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- AWS 자격 증명 (`~/.aws/credentials` 또는 환경 변수)
  - Amazon Bedrock 모델 접근 권한 (Claude Opus 4.6, Claude Sonnet 4.5)

## 시작하기

```bash
# 의존성 설치
uv sync

# 서버 실행 (stdio 모드)
uv run ppt-generator

# 테스트 실행
uv run pytest
```

## MCP 클라이언트 설정

`claude_desktop_config.json` 또는 MCP 클라이언트 설정에 추가:

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

## MCP 도구

### 생성 도구

| 도구 | 설명 | 입력 | 출력 |
|------|------|------|------|
| `generate_outline` | 슬라이드 아웃라인 생성 | 주제, 슬라이드 수, [project_id] | 아웃라인 JSON + project_id |
| `generate_script` | 발표 스크립트 생성 | 아웃라인 JSON, [project_id] | speaker_notes 포함 아웃라인 JSON + project_id |
| `generate_design_spec` | 디자인 스펙 생성 | 아웃라인 JSON, [project_id] | PptxSlideSpec JSON + project_id |
| `generate_slides` | HTML 슬라이드 생성 | 아웃라인 JSON 또는 design_spec_json, [project_id] | session_id + HTML + project_id |
| `modify_slides` | 슬라이드 수정 | 세션 ID, 수정 요청, [slide_index], [project_id] | session_id + 수정된 HTML + project_id |
| `export_pptx` | PPTX 내보내기 | 세션 ID 또는 design_spec_json, [project_id] | project_id + .pptx 파일 경로 |

### 프로젝트 관리 도구

| 도구 | 설명 | 입력 | 출력 |
|------|------|------|------|
| `list_projects` | 프로젝트 목록 조회 | (없음) | 프로젝트 목록 JSON |
| `load_project_status` | 프로젝트 상태 로드 | project_id | 메타데이터 JSON |
| `load_outline` | 저장된 아웃라인 로드 | project_id | 아웃라인 JSON |
| `load_script` | 저장된 스크립트 로드 | project_id | speaker_notes 포함 아웃라인 JSON |
| `load_design_spec` | 저장된 디자인 스펙 로드 | project_id | PptxSlideSpec JSON |
| `load_slides_html` | 저장된 슬라이드 로드 + 세션 복원 | project_id | session_id + HTML |

## 프로젝트 구조

```
ppt-generator/
├── src/ppt_generator/
│   ├── server.py                  # MCP 서버 진입점
│   ├── di/
│   │   └── container.py           # 의존성 주입 컨테이너
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 수치 상수, 프롬프트 re-export
│   │   ├── schemas.py             # 데이터클래스 (Request/Response)
│   │   ├── spec_utils.py          # PptxSlideSpec 파싱/검증/직렬화 유틸리티
│   │   ├── utils.py               # parse_outline_json 등 공용 파싱 유틸리티
│   │   └── prompts/               # 프롬프트 템플릿 모듈
│   ├── templates/
│   │   ├── slides.html            # HTML 슬라이드 템플릿 (TailwindCSS, 수직 스크롤)
│   │   └── layout_mapping.py      # layout_index → 슬라이드 레이아웃 매핑
│   └── tools/
│       ├── outline/               # F1: 아웃라인 생성
│       ├── script/                # F2: 발표 스크립트 생성
│       ├── design/                # 디자인 스펙 생성 (PptxSlideSpec JSON)
│       ├── slides/                # F3/F4: HTML 슬라이드 생성 + 수정 (css_inliner.py 포함)
│       ├── pptx/                  # F5: PPTX 내보내기 (slide_builder, llm_converter, dom_extractor 등)
│       └── project/               # F6: 프로젝트 목록/저장/로드
├── docs/
│   ├── adr/                       # Architecture Decision Records
│   ├── ppt-generator.alps.xml     # ALPS 설계 문서
│   └── ppt-generator.alps.md      # ALPS 마크다운 내보내기
├── tests/
└── pyproject.toml
```

## 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| 프로토콜 | Model Context Protocol (MCP) |
| 에이전트 프레임워크 | AWS Strands SDK |
| LLM | Amazon Bedrock - Claude Opus 4.6 (슬라이드/디자인 스펙), Sonnet 4.5 (아웃라인/스크립트/PPTX 변환) |
| 슬라이드 프레임워크 | 순수 HTML/CSS (TailwindCSS + 인라인 스타일, JavaScript 없음, 수직 스크롤) |
| PPTX 내보내기 | python-pptx (디자인 스펙 직접 생성 또는 HTML → PPTX 변환) |
| HTML 파싱 | BeautifulSoup (`<section>` 기반 슬라이드 파싱) |
| 스크린샷 | Playwright (HTML → 이미지 캡처, PPTX 변환 시 활용) |
| 패키지 관리 | uv + hatchling |

## 아키텍처

Controller-Service 패턴 + 의존성 주입(DI):

- **Controller** (`controller.py`): MCP 도구 인터페이스, 입력 검증
- **Service** (`service.py`): 비즈니스 로직 (API 호출, HTML 생성/수정, PPTX 변환)
- **DIContainer** (`container.py`): Bedrock 모델, Agent, Service 생성 및 연결

## 슬라이드 생성 방식

두 가지 슬라이드 생성 경로를 지원합니다:

- **디자인 스펙 경로 (권장)**: LLM(Opus 4.6)이 아웃라인을 기반으로 PptxSlideSpec JSON을 생성하고, 이를 position:absolute HTML로 결정론적 변환하여 미리보기를 제공합니다. PPTX는 SlideBuilder가 디자인 스펙에서 직접 생성합니다.
- **HTML 경로 (기존)**: LLM이 아웃라인(title, content_summary, component_hint)을 기반으로 자유 형식 HTML/CSS 슬라이드를 생성합니다. PPTX 변환 시 DOM 추출/LLM 변환/룰 기반 폴백 체인을 사용합니다.
