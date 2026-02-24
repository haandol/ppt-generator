# PPT Generator

> **Cost & Time Warning**: 20장 분량의 PPT를 처음부터 끝까지 생성하는 데 약 **18분**, API 비용 약 **$9 USD**가 소요됩니다. 디자인 스펙 생성에 Claude Opus 4.6 Extended Thinking을 사용하기 때문이며, 슬라이드 수에 비례하여 시간과 비용이 증가합니다. 또한 디자인 스펙 생성 시 슬라이드 복잡도에 따라 thinking effort를 동적으로 조절(high/medium/low)하므로, 슬라이드 내용이 복잡할수록 비용이 더 높아질 수 있습니다. **사용 전 반드시 Anthropic/Bedrock 콘솔에서 토큰 비용 체계를 확인하세요.** 예상치 못한 과금이 발생할 수 있습니다.

주제를 입력하면 AI가 자동으로 프레젠테이션을 생성하는 MCP(Model Context Protocol) 서버입니다. Claude LLM으로 아웃라인·스크립트·디자인 스펙을 생성하고, HTML 미리보기와 편집 가능한 PPTX로 내보냅니다.

## 주요 기능

- **아웃라인 생성** — 주제와 슬라이드 수를 입력하면 구조화된 아웃라인 JSON을 생성
- **발표 스크립트 생성** — 아웃라인 기반으로 슬라이드별 발표 스크립트(speaker notes) 작성
- **디자인 스펙 생성** — 슬라이드별 정밀한 레이아웃을 PptxSlideSpec JSON으로 설계
- **슬라이드별 수정** — 개별 슬라이드의 디자인 스펙을 추가/수정/삭제 (전체 재생성 불필요)
- **HTML 미리보기** — 디자인 스펙에서 결정론적으로 HTML 변환
- **PPTX 내보내기** — 디자인 스펙에서 편집 가능한 PPTX로 결정론적 변환
- **프로젝트 관리** — `project_id` 기반으로 중간 결과물 저장/로드, 중간 단계부터 재개 가능

## 빠른 시작

### 설치

```bash
uv sync
```

### MCP 클라이언트에 서버 추가

`claude_desktop_config.json` (Claude Desktop) 또는 `.mcp.json` (Claude Code)에 추가:

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

> `/path/to/ppt-generator`를 실제 프로젝트 경로로 변경하세요.

## 설정

### LLM 프로바이더

Anthropic API와 AWS Bedrock을 지원합니다. `LLM_PROVIDER` 환경변수로 선택하거나, 미설정 시 자동 감지됩니다.

**Auto-detect 로직**: `LLM_PROVIDER` 미설정 시, `ANTHROPIC_API_KEY`가 있으면 `anthropic`, 없으면 `bedrock`으로 자동 선택됩니다.

### 환경변수

| 환경변수                   | 값                      | 설명                                                                                                     |
| -------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| `LLM_PROVIDER`             | `anthropic` / `bedrock` | 명시적 프로바이더 선택 (미설정 시 auto-detect)                                                           |
| `ANTHROPIC_API_KEY`        | API Key 문자열          | Anthropic 직접 API 인증 (auto-detect 트리거)                                                             |
| `AWS_ACCESS_KEY_ID`        | AWS Access Key          | Bedrock IAM 인증                                                                                         |
| `AWS_SECRET_ACCESS_KEY`    | AWS Secret Key          | Bedrock IAM 인증                                                                                         |
| `AWS_REGION`               | AWS 리전                | Bedrock 리전 (기본: `us-east-1`)                                                                         |
| `AWS_BEARER_TOKEN_BEDROCK` | Bearer Token 문자열     | Bedrock API key (bearer token) 인증. 설정 시 bearer token 우선, 미설정 시 기본 AWS credential chain 사용 |
| `DESIGN_SPEC_PARALLEL`     | 정수 (기본: `8`)        | 디자인 스펙 생성 시 슬라이드별 병렬 워커 수. API rate limit에 맞게 조절                                  |

> 샘플 환경변수 파일은 [`env/local.env`](env/local.env)를 참고하세요.

### 사용 모델

모든 LLM 호출은 Claude Extended Thinking을 사용합니다. 디자인 스펙 생성에는 Opus 4.6, 아웃라인/스크립트에는 Sonnet 4.6을 사용합니다.

| 용도              | Bedrock 모델 ID                          | Anthropic 모델 ID   | Max Tokens | Thinking Effort                          |
| ----------------- | ---------------------------------------- | ------------------- | ---------- | ---------------------------------------- |
| 디자인 스펙 생성  | `global.anthropic.claude-opus-4-6-v1`    | `claude-opus-4-6`   | 64,000     | adaptive (슬라이드 복잡도 기반 high/medium/low) |
| 아웃라인/스크립트 | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 32,000     | medium (기본, `OUTLINE_THINKING_EFFORT`로 변경 가능) |

### 클라이언트별 설정 예시

<details>
<summary><strong>Claude Desktop</strong></summary>

`claude_desktop_config.json`에 추가:

**Anthropic API 사용 시:**

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

**AWS Bedrock 사용 시** (`~/.aws/credentials` 설정 완료 가정):

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

**AWS 환경변수를 직접 지정하는 경우:**

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

**Bedrock API key (bearer token) 사용 시:**

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

</details>

<details>
<summary><strong>Claude Code (.mcp.json)</strong></summary>

프로젝트 루트에 `.mcp.json` 파일 생성:

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

</details>

<details>
<summary><strong>Kiro</strong></summary>

Kiro의 MCP 서버 설정에서 동일한 JSON 형식으로 추가합니다.

</details>

## MCP 도구

### 생성 도구

| 도구                         | 설명                                                      |
| ---------------------------- | --------------------------------------------------------- |
| `generate_outline`           | 주제와 슬라이드 수를 기반으로 아웃라인 JSON 생성          |
| `generate_script`            | 아웃라인 기반 슬라이드별 발표 스크립트 생성               |
| `generate_slides_design_spec` | 슬라이드 디자인 스펙 생성 (전체 또는 선택적, 서버 내부 병렬 처리) |
| `modify_design_spec`         | 디자인 스펙의 개별 슬라이드 추가/수정/삭제                |
| `generate_slides`            | 디자인 스펙에서 HTML 슬라이드 생성 (결정론적 변환)        |
| `export_pptx`                | 디자인 스펙에서 편집 가능한 PPTX 내보내기 (결정론적 변환) |

#### 디자인 스펙 병렬 생성

`generate_slides_design_spec`은 슬라이드별 독립 LLM 호출을 `ThreadPoolExecutor`로 병렬 처리합니다.

- **병렬 워커 수**: `DESIGN_SPEC_PARALLEL` 환경변수로 제어 (기본 `8`). API rate limit에 맞게 조절 가능
- **Longest-job-first 스케줄링**: 슬라이드 복잡도 점수(1~13)를 산출하여 복잡한 슬라이드부터 먼저 처리 → wall-clock time 단축
- **Adaptive thinking effort**: 복잡도에 따라 `high`(7~13) / `medium`(4~6) / `low`(1~3) effort를 동적 적용 → 단순 슬라이드 토큰 절약, 복잡한 슬라이드 품질 유지

### 프로젝트 관리 도구

| 도구                  | 설명                             |
| --------------------- | -------------------------------- |
| `list_projects`       | 기존 프로젝트 목록 조회          |
| `load_project_status` | 프로젝트 상태 및 메타데이터 로드 |
| `load_outline`        | 저장된 아웃라인 JSON 로드        |
| `load_script`         | 저장된 스크립트 JSON 로드        |
| `load_design_spec`    | 저장된 디자인 스펙 로드          |

## 사용 워크플로우

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
1. generate_outline       → 아웃라인 JSON 생성
    ↓
    ⏸ 아웃라인 검토/수정
    ↓
2. generate_script        → 발표 스크립트 생성
    ↓
3. generate_slides_design_spec (전체 또는 slide_indices로 선택적 생성)
    ↓
    ⏸ 검토 → (선택) modify_design_spec으로 개별 수정
    ↓
4. export_pptx            → 편집 가능한 .pptx 파일 출력
   generate_slides        → HTML 미리보기 (선택)
```

- 모든 도구는 `project_id`를 자동 생성하여 `~/.ppt-generator/<UUID>/`에 결과물을 저장합니다
- `load_*` 도구에 `project_id`를 전달하면 중간 단계부터 재개할 수 있습니다
- 첫 슬라이드 생성 시 디자인 테마를 추출하여 후속 슬라이드의 시각적 일관성을 유지합니다

## 프로젝트 구조

```
ppt-generator/
├── src/ppt_generator/
│   ├── server.py                  # MCP 서버 진입점
│   ├── di/
│   │   └── container.py           # 의존성 주입 컨테이너
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 수치 상수
│   │   ├── schemas.py             # 내부 도메인 모델 (dataclass)
│   │   ├── llm_output_models.py   # LLM structured_output용 Pydantic 모델
│   │   └── prompts/               # 프롬프트 템플릿 (.prompt.md)
│   ├── templates/
│   │   ├── slide.html             # 개별 슬라이드 HTML 템플릿
│   │   ├── slides_container.html  # iframe 컨테이너 템플릿
│   │   └── layout_mapping.py      # layout_index → 슬라이드 레이아웃 매핑
│   └── tools/
│       ├── outline/               # 아웃라인 생성
│       ├── script/                # 발표 스크립트 생성
│       ├── design/                # 디자인 스펙 생성/수정
│       ├── slides/                # HTML 슬라이드 생성
│       ├── pptx/                  # PPTX 내보내기
│       └── project/               # 프로젝트 관리
├── env/
│   └── local.env                  # 샘플 환경변수 파일
├── docs/
│   ├── adr/                       # Architecture Decision Records
│   └── ppt-generator.alps.md     # ALPS 설계 문서
├── tests/
└── pyproject.toml
```

## 기술 스택

| 구성 요소               | 기술                               |
| ----------------------- | ---------------------------------- |
| 프로토콜                | Model Context Protocol (MCP)       |
| 언어                    | Python 3.13+                       |
| 패키지 관리             | uv + hatchling                     |
| 에이전트 프레임워크     | AWS Strands SDK (`strands-agents`) |
| LLM                     | Claude Opus 4.6 / Sonnet 4.6 Extended Thinking |
| 슬라이드 프레임워크     | 순수 HTML/CSS (인라인 스타일)      |
| PPTX 내보내기           | python-pptx                        |

## 개발

```bash
# 의존성 설치
uv sync

# 서버 실행 (stdio 모드)
uv run ppt-generator

# 테스트 실행
uv run pytest
```

## 기여하기

커밋 메시지, 브랜치 전략, 코드 스타일, PR 규칙 등은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.
