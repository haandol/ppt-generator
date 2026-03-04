# PPT Generator

주제를 입력하면 AI가 자동으로 프레젠테이션을 생성하는 MCP(Model Context Protocol) 서버입니다.

### Cost & Time

> Claude Sonnet 4.6 기준, 슬라이드 수와 복잡도에 비례하여 시간·비용이 증가합니다.

**Visual QA 없이 (디자인 스펙 생성까지)**

| 슬라이드 | 소요 시간 | Input tokens | Output tokens | 비용 (USD) |
| --- | --- | --- | --- | --- |
| 10장 | ~9 min | ~136K | ~108K | **~$2.0** |
| 20장 | ~15 min | ~295K | ~466K | **~$7.7** |

**Visual QA (max_iterations=2)**

| 슬라이드 | Input tokens | Output tokens | 비용 (USD) |
| --- | --- | --- | --- |
| 20장 | ~573K | ~226K | **~$5.1** |

**합산 (디자인 스펙 + Visual QA)**

| 슬라이드 | Input tokens | Output tokens | 비용 (USD) |
| --- | --- | --- | --- |
| 20장 | ~868K | ~692K | **~$12.8** |

Visual QA는 자동으로 실행되지 않으며, 사용자가 명시적으로 요청해야 합니다. 비용을 절감하려면 `max_iterations=1`로 설정하거나 문제가 있는 슬라이드만 별도로 Visual QA를 요청하세요.

## Prerequisites

1. Python 3.13+
2. [uv](https://docs.astral.sh/uv/) 패키지 매니저
3. AWS CLI 설정 (기본: Bedrock IAM) 또는 Anthropic API Key

## 1. 설치

```bash
git clone https://github.com/haandol/ppt-generator.git
cd ppt-generator
uv sync
```

## 2. MCP 서버 등록

MCP 클라이언트 설정 파일에 서버를 추가합니다.

**Claude Code** — 프로젝트 루트에 `.mcp.json` 생성:

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

**Kiro** — 프로젝트 루트에 `.kiro/settings/mcp.json` 생성:

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

**Claude Desktop** — `claude_desktop_config.json`에 동일한 형식으로 추가합니다.

> 기본적으로 AWS CLI 프로필의 IAM 자격 증명을 사용합니다 (Bedrock). Anthropic API를 사용하려면 `env`에 `"ANTHROPIC_API_KEY": "sk-ant-..."`를 추가하세요.

> `/path/to/ppt-generator`를 실제 프로젝트 경로로 변경하세요.

### LLM 프로바이더

Anthropic API와 AWS Bedrock을 지원합니다.

| 프로바이더             | 필요한 환경변수                                            |
| ---------------------- | ---------------------------------------------------------- |
| Bedrock IAM (기본)     | AWS CLI 프로필 또는 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` |
| Bedrock (Bearer Token) | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`                   |
| Anthropic              | `ANTHROPIC_API_KEY`                                        |

`LLM_PROVIDER` 미설정 시 `ANTHROPIC_API_KEY`가 있으면 `anthropic`, 없으면 `bedrock`으로 자동 선택됩니다.

> 전체 환경변수 목록과 클라이언트별 상세 설정은 [docs/architecture.md](docs/architecture.md)를 참고하세요.

## 3. 사용법

### Step 1 — PPT 생성 또는 임포트

**새로 생성하기** — 발표 자료로 만들 내용을 `context.md` 등의 파일에 정리한 뒤, MCP 클라이언트에서 요청합니다:

```
@context.md 를 읽고 ppt-generator 로 ppt 생성해줘.
```

**기존 PPTX 가져오기** — 이미 만들어진 PPTX 파일을 가져와서 수정할 수도 있습니다:

```
@presentation.pptx 를 import_pptx로 가져와줘.
```

임포트하면 HTML 미리보기가 자동 생성되며, 이후 Step 2를 건너뛰고 바로 슬라이드별 수정, Visual QA, 내보내기를 사용할 수 있습니다. LLM 호출 없이 결정론적으로 파싱하므로 추가 비용이 발생하지 않습니다.

### Step 2 — 프로젝트 정보 입력

아웃라인 생성 전에 다음 정보를 질문받게 됩니다:

- **발표 목적** — 예: "사내 기술 공유", "고객 제안", "컨퍼런스 발표"
- **발표 시간** — 3~60분 (기본 15분)
- **청중 유형** — `general` / `technical` / `executive`

이후 아웃라인 → 스크립트 → 디자인 스펙 순서로 자동 생성됩니다. 각 단계에서 검토/수정 기회가 주어집니다.

### Step 3 — 슬라이드별 수정 (선택)

디자인 스펙 생성(또는 PPTX 임포트) 후 개별 슬라이드를 수정할 수 있습니다. 전체를 재생성하지 않고 원하는 슬라이드만 추가/수정/삭제가 가능합니다:

```
3번 슬라이드 다이어그램 하단에 바 그래프 형태로 성능 비교 데이터를 추가해줘.
5번 슬라이드의 텍스트가 너무 많으니 핵심 키워드 중심으로 줄이고 아이콘 배치로 바꿔줘.
7번 슬라이드 뒤에 Q&A 슬라이드를 추가해줘.
```

### Step 4 — Visual QA (선택)

시각적 결함(줄바꿈, 겹침, 여백 불일치 등)을 자동 감지하고 수정할 수 있습니다. **자동으로 실행되지 않으며, 사용자가 명시적으로 요청해야 합니다.**

**사전 설치:**

```bash
uv sync --group visual-qa
playwright install chromium
```

```
visual_qa 실행해줘.
```

> Visual QA는 opt-in 도구입니다. 디자인 스펙 생성 완료 후 제안 메시지가 표시되지만, 사용자가 직접 요청하기 전까지 실행되지 않습니다. Playwright가 설치되지 않으면 건너뛸 수 있으며, 기존 기능에는 영향 없습니다.

### Step 5 — 파일 내보내기

디자인 스펙 생성이 완료되면 기본적으로 HTML 파일이 자동 내보내기됩니다. 만약 자동으로 내보내지지 않았다면 직접 요청할 수 있습니다:

```
html 로 내보내고 열어줘.
```

PPTX 형식으로 내보내려면:

```
ppt 로 내보내고 열어줘.
```

## 디버깅 로그

MCP 서버는 stdio 통신을 사용하므로 stdout 로그를 직접 확인할 수 없습니다. 파일 로그를 활성화하면 디버그 레벨 로그를 파일로 기록합니다.

### 설정 방법

MCP 서버 등록 시 `env`에 `PPT_LOG_DIR`을 추가합니다:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "PPT_LOG_DIR": "/tmp/ppt-generator"
      }
    }
  }
}
```

### 환경변수

| 변수 | 설명 |
| --- | --- |
| `VISUAL_QA_PARALLEL` | Visual QA 병렬 워커 수 (기본: 8) |
| `VISUAL_QA_MAX_ITERATIONS` | Visual QA 최대 수정 반복 횟수 (기본: 2) |
| `PPT_LOG_DIR` | 프로젝트별 로그 파일이 저장될 디렉토리 (권장). 예: `/tmp/ppt-generator` |
| `PPT_LOG_FILE` | 단일 로그 파일 경로 (레거시). `PPT_LOG_DIR` 설정 시 무시됨 |

- 로그 파일은 10MB 단위로 회전하며 백업 2개를 유지합니다.
- `PPT_LOG_DIR` 설정 시 프로젝트마다 `<project_id>.log` 파일이 생성됩니다.

### 로그 확인

```bash
# 특정 프로젝트 로그 확인
tail -f /tmp/ppt-generator/<project_id>.log

# 전체 로그 확인
tail -f /tmp/ppt-generator/*.log
```

## 개발

```bash
uv run ppt-generator          # MCP 서버 실행 (stdio 모드)
uv run pytest                  # 전체 테스트
```

## 문서

- [Architecture](docs/architecture.md) — 기능 상세, MCP 도구 목록, 워크플로우, 프로젝트 구조, 기술 스택
- [ALPS 설계 문서](docs/ppt-generator.alps.md)
- [ADR](docs/adr/) — Architecture Decision Records
- [기여 가이드](CONTRIBUTING.md)
