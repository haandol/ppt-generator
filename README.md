# PPT Generator

주제를 입력하면 AI가 자동으로 프레젠테이션을 생성하고, 사용자의 수정 요청을 반영한 뒤 편집 가능한 PPTX로 내보내는 MCP 서버입니다.

Claude LLM으로 콘텐츠를 생성하고, 디자인 스펙(PptxSlideSpec JSON)을 중간 표현으로 사용하여 HTML 미리보기와 편집 가능한 PPTX를 각각 결정론적으로 생성합니다.

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

디자인 스펙(PptxSlideSpec JSON)을 중간 표현으로 사용하여, 단일 소스에서 HTML과 PPTX를 각각 결정론적으로 생성합니다. LLM이 각 요소의 좌표/크기/서식을 JSON으로 정밀하게 설계하고, 이를 기반으로 HTML 미리보기(position:absolute 변환)와 PPTX(SlideBuilder 직접 호출)를 생성합니다.

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
    디자인 스펙 생성 (슬라이드별)
    ↓
    for i in 0..N-1:
      generate_slide_design_spec(slide[i], slide_index=i, total=N)
      ⏸ 사용자 검토
      (선택) modify_design_spec(action="update", slide_index=i)
    ↓
    ├→ generate_slides(project_id=...)       → 디자인 스펙 자동 로드 → HTML 변환 (결정론적)
    │
    └→ export_pptx(project_id=...)          → 디자인 스펙 자동 로드 → PPTX 생성 (결정론적)
    ↓
출력: 편집 가능한 .pptx 파일

* project_id 기반 체이닝 (권장): generate_slide_design_spec → generate_slides/export_pptx(project_id=...)
* 모든 도구가 project_id를 자동 생성하여 ~/.ppt-generator/<UUID>/에 결과물을 저장
* generate_slide_design_spec은 첫 슬라이드에서 design_summary.json를 생성하여 후속 슬라이드의 테마 일관성 유지
```

모든 도구는 `project_id`를 자동 생성하여 `~/.ppt-generator/<UUID>/`에 결과물을 저장합니다. `load_*` 도구에 `project_id`를 전달하면 저장된 결과물을 불러와 중간 단계부터 재개할 수 있습니다.

### 프로젝트 디렉토리 구조

```
~/.ppt-generator/<UUID>/
  project.json            # 메타데이터 (주제, 슬라이드 수, 단계 완료 상태)
  outline.json            # F1 출력
  script.json             # F2 출력
  design_spec/            # 디자인 스펙 출력 (슬라이드별 개별 파일)
    slide_01.json         # 슬라이드별 PptxSlideSpec JSON
    slide_02.json
    ...
    design_summary.json   # 디자인 테마 요약 (슬라이드별 생성 시)
  slides/                 # HTML 슬라이드 출력 (슬라이드별 개별 파일)
    slide_01.html         # 슬라이드별 완전한 HTML 문서
    slide_02.html
    ...
  slides.html             # iframe 컨테이너 (각 슬라이드를 iframe으로 참조)
  slides_meta.json        # 세션 메타 (session_id)
  presentation.pptx       # PPTX 내보내기 출력
```

## 요구사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- LLM 인증 (아래 중 하나 선택):
  - **Anthropic API**: `ANTHROPIC_API_KEY` 환경변수 설정
  - **AWS Bedrock**: `~/.aws/credentials` 또는 `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` 환경변수
    - Amazon Bedrock 모델 접근 권한 필요 (Claude Opus 4.6, Claude Sonnet 4.6)
    - 리전: `us-east-1` (기본값)

## 시작하기

```bash
# 의존성 설치
uv sync

# 서버 실행 (stdio 모드)
uv run ppt-generator

# 테스트 실행
uv run pytest
```

## LLM 프로바이더 설정

Anthropic API와 AWS Bedrock 두 가지 프로바이더를 지원합니다. 환경변수로 선택할 수 있으며, 미설정 시 자동 감지됩니다.

### Auto-detect 로직

1. `LLM_PROVIDER` 환경변수가 `anthropic` 또는 `bedrock`로 설정되어 있으면 해당 프로바이더 사용
2. `LLM_PROVIDER` 미설정 시, `ANTHROPIC_API_KEY` 환경변수가 존재하면 `anthropic` 사용
3. 그 외의 경우 `bedrock`으로 폴백

### 환경변수

| 환경변수 | 값 | 설명 |
|----------|-----|------|
| `LLM_PROVIDER` | `anthropic` / `bedrock` | 명시적 프로바이더 선택 (미설정 시 auto-detect) |
| `ANTHROPIC_API_KEY` | API Key 문자열 | Anthropic 직접 API 인증 (auto-detect 트리거) |
| `AWS_ACCESS_KEY_ID` | AWS Access Key | Bedrock 인증 |
| `AWS_SECRET_ACCESS_KEY` | AWS Secret Key | Bedrock 인증 |
| `AWS_REGION` | AWS 리전 | Bedrock 리전 (기본: `us-east-1`) |

> 샘플 환경변수 파일은 [`env/local.env`](env/local.env)를 참고하세요.

### 사용 모델

| 용도 | Bedrock 모델 ID | Anthropic 모델 ID | Max Tokens |
|------|-----------------|-------------------|------------|
| 디자인 스펙 생성 | `us.anthropic.claude-opus-4-6-v1` | `claude-opus-4-6` | 48,000 |
| 아웃라인/스크립트 | `us.anthropic.claude-sonnet-4-6` | `claude-sonnet-4-6` | 16,000 |

## MCP 클라이언트 설정

`claude_desktop_config.json` 또는 MCP 클라이언트 설정에 추가합니다.

### Anthropic API 사용 시

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
      ],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

### AWS Bedrock 사용 시

AWS 자격 증명이 `~/.aws/credentials`에 설정되어 있으면 `env` 없이 사용 가능합니다:

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

AWS 환경변수를 직접 지정하는 경우:

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
      ],
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

### Claude Code 설정 (`.mcp.json`)

프로젝트 루트에 `.mcp.json` 파일로도 설정할 수 있습니다:

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
      ],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

## MCP 도구

### 생성 도구

| 도구 | 설명 | 입력 | 출력 |
|------|------|------|------|
| `generate_outline` | 슬라이드 아웃라인 생성 | 주제, 슬라이드 수, audience, minutes, [project_id] | 아웃라인 JSON + project_id |
| `generate_script` | 발표 스크립트 생성 | 아웃라인 JSON, [project_id] | speaker_notes 포함 아웃라인 JSON + project_id |
| `generate_slide_design_spec` | 슬라이드별 디자인 스펙 생성 | 아웃라인 JSON, slide_index, total_slides, [project_id] | slide_file + project_id |
| `modify_design_spec` | 디자인 스펙 슬라이드 CRUD | project_id, action, [slide_index], [outline_json] | slide_count + project_id |
| `generate_slides` | HTML 슬라이드 생성 | [design_spec_json], [project_id] | session_id + slides_html_path + project_id |
| `export_pptx` | PPTX 내보내기 | [design_spec_json], [project_id] | project_id + .pptx 파일 경로 |

### 프로젝트 관리 도구

| 도구 | 설명 | 입력 | 출력 |
|------|------|------|------|
| `list_projects` | 프로젝트 목록 조회 | (없음) | 프로젝트 목록 JSON |
| `load_project_status` | 프로젝트 상태 로드 | project_id | 메타데이터 JSON |
| `load_outline` | 저장된 아웃라인 로드 | project_id | 아웃라인 JSON |
| `load_script` | 저장된 스크립트 로드 | project_id | speaker_notes 포함 아웃라인 JSON |
| `load_design_spec` | 저장된 디자인 스펙 로드 | project_id | design_spec_dir + slide_count + slide_files |

## 프로젝트 구조

```
ppt-generator/
├── src/ppt_generator/
│   ├── server.py                  # MCP 서버 진입점
│   ├── di/
│   │   └── container.py           # 의존성 주입 컨테이너 (Anthropic/Bedrock 듀얼 프로바이더)
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 수치 상수, 프롬프트 re-export
│   │   ├── schemas.py             # 내부 도메인 모델 (dataclass)
│   │   ├── llm_output_models.py   # LLM structured_output용 Pydantic 모델
│   │   ├── spec_utils.py          # PptxSlideSpec 파싱/검증/직렬화 유틸리티
│   │   ├── text_measurement.py    # 폰트 메트릭 기반 텍스트 크기 추정
│   │   ├── bg_image_utils.py      # 배경 이미지 유틸리티
│   │   ├── utils.py               # parse_outline_json 등 공용 파싱 유틸리티
│   │   └── prompts/               # 프롬프트 템플릿 모듈
│   ├── templates/
│   │   ├── slide.html             # 개별 슬라이드 HTML 템플릿
│   │   ├── slides_container.html  # iframe 컨테이너 템플릿
│   │   ├── layout_mapping.py      # layout_index → 슬라이드 레이아웃 매핑 (97종)
│   │   └── template_bg_images/    # 배경 이미지 리소스
│   └── tools/
│       ├── outline/               # F1: 아웃라인 생성
│       ├── script/                # F2: 발표 스크립트 생성
│       ├── design/                # 디자인 스펙 생성 (PptxSlideSpec JSON)
│       ├── slides/                # HTML 슬라이드 생성 (디자인 스펙 → HTML 결정론적 변환)
│       │   ├── controller.py
│       │   ├── service.py         # 오케스트레이션 (세션 관리, 템플릿 조합)
│       │   └── html_renderer.py   # PptxSlideSpec → HTML 변환 렌더러
│       ├── pptx/                  # PPTX 내보내기 (디자인 스펙 → SlideBuilder 직접 변환)
│       │   ├── controller.py
│       │   ├── service.py
│       │   ├── slide_builder.py   # PptxSlideSpec → python-pptx 변환
│       │   └── text_formatter.py  # run/paragraph 포매팅 공통 함수
│       └── project/               # F6: 프로젝트 목록/저장/로드
│           ├── controller.py
│           ├── service.py         # 프로젝트 코어 관리
│           └── design_spec_store.py # 디자인 스펙 파일 CRUD 전담 저장소
├── env/
│   └── local.env                  # 샘플 환경변수 파일
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
| 에이전트 프레임워크 | AWS Strands SDK (`strands-agents`) |
| LLM (디자인 스펙) | Claude Opus 4.6 (Bedrock: `us.anthropic.claude-opus-4-6-v1` / Anthropic: `claude-opus-4-6`) |
| LLM (아웃라인/스크립트) | Claude Sonnet 4.6 (Bedrock: `us.anthropic.claude-sonnet-4-6` / Anthropic: `claude-sonnet-4-6`) |
| 슬라이드 프레임워크 | 순수 HTML/CSS (인라인 스타일, JavaScript 없음, 수직 스크롤) |
| PPTX 내보내기 | python-pptx (디자인 스펙 → SlideBuilder 직접 변환) |
| 패키지 관리 | uv + hatchling |

## 아키텍처

Controller-Service 패턴 + 의존성 주입(DI):

- **Controller** (`controller.py`): MCP 도구 인터페이스, 입력 검증
- **Service** (`service.py`): 비즈니스 로직 오케스트레이션
- **전용 모듈**: 각 서비스의 핵심 로직을 단일 책임 모듈로 분리
  - `html_renderer.py`: PptxSlideSpec → HTML 변환 렌더러
  - `text_formatter.py`: python-pptx run/paragraph 포매팅 공통 함수
  - `design_spec_store.py`: 디자인 스펙 파일 CRUD 전담 저장소
  - `llm_output_models.py`: LLM structured_output용 Pydantic 모델
- **DIContainer** (`container.py`): 프로바이더 자동 감지, 모델/Agent/Service 생성 및 연결

## 슬라이드 생성 방식

디자인 스펙(PptxSlideSpec JSON)을 중간 표현으로 사용합니다:

- LLM(Opus 4.6)이 아웃라인을 기반으로 슬라이드별 PptxSlideSpec JSON을 생성합니다
- 디자인 스펙에서 position:absolute HTML로 결정론적 변환하여 미리보기를 제공합니다
- PPTX는 SlideBuilder가 디자인 스펙에서 직접 생성합니다
- 첫 슬라이드 생성 시 디자인 테마를 추출하여, 후속 슬라이드의 시각적 일관성을 유지합니다
