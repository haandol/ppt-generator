# Environment & Configuration

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저

**모델 자격 증명이 필요 없습니다.** 이 서버는 LLM 을 직접 호출하지 않고, 토큰 생성은 MCP 클라이언트(Claude Code 등)가 이미 가진 모델로 수행합니다. 서버는 프롬프트·출력 스키마·결정론적 후처리(검증, lint, HTML/PPTX 렌더)만 담당하므로 AWS Bedrock 접근권이나 Anthropic API 키를 요구하지 않습니다. (설계 배경: [offload/0001](../adr/offload/0001-client-llm-offload-plugin.md))

## 환경변수

서버가 인식하는 환경변수는 모두 결정론적 동작(스크린샷 캡처, Visual QA 루프 상한, 로깅)에 대한 것입니다. 아래는 `interfaces/constants.py` / `server.py` 에 실제로 정의된 변수입니다.

| 환경변수                   | 값                    | 설명                                                                                                     |
| -------------------------- | --------------------- | -------------------------------------------------------------------------------------------------------- |
| `VISUAL_QA_PARALLEL`       | 정수 (기본: 8)        | Visual QA 스크린샷 캡처 병렬 워커 수 (Playwright, 서버측). 분석·수정 생성은 클라이언트 담당              |
| `VISUAL_QA_MAX_ITERATIONS` | 정수 (기본: 2)        | Visual QA 최대 수정 반복 횟수 (클라이언트가 오케스트레이션하는 루프의 상한 힌트)                          |
| `SCREENSHOT_TIMEOUT`       | 정수(초) (기본: 60)   | 슬라이드 스크린샷 캡처 타임아웃 (초)                                                                     |
| `PPT_LOG_DIR`              | 디렉토리 경로 문자열  | 세션별 로그 파일 디렉토리 (권장, 예: `/tmp/ppt-generator`). 서버 전역 로그(`_server.log`) 포함, 10MB 회전·백업 2개 |
| `PPT_LOG_FILE`             | 파일 경로 문자열      | 단일 로그 파일 경로 (레거시, `PPT_LOG_DIR` 우선). 10MB 회전·백업 2개                                     |

> `PPT_LOG_DIR` 이 설정되면 프로젝트별 동적 로그 핸들러가 붙고, 서버 전역 로그(`_server.log`)에 MCP stdio 통신 에러 등을 기록합니다. `PPT_LOG_DIR` 과 `PPT_LOG_FILE` 이 모두 설정되면 `PPT_LOG_DIR` 이 우선합니다.

## MCP Client Configuration

서버는 자격 증명 없이 `uv --directory ... run ppt-generator` 형태로 stdio MCP 로 실행합니다.

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

`env` 블록은 선택 사항입니다. 로깅이 필요 없으면 통째로 생략할 수 있습니다.

## Claude Code 플러그인

이 저장소는 Claude Code 플러그인(`.claude-plugin/plugin.json`)으로도 배포됩니다. 플러그인 매니페스트는 위와 동일하게 서버를 stdio 로 실행하되, 경로를 `${CLAUDE_PLUGIN_ROOT}` 로 지정합니다:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}", "run", "ppt-generator"]
    }
  }
}
```

플러그인은 `skills/` 아래에 워크플로우별 스킬을 포함합니다:

- `skills/ppt-outline/` — 아웃라인 (prepare_outline → 생성 → ingest_outline)
- `skills/ppt-design/` — DESIGN.md 초안 + 슬라이드별 디자인 스펙 생성 (병렬)
- `skills/ppt-modify/` — 슬라이드 add/update/move/delete + 단일 컴포넌트 수정
- `skills/ppt-visual-qa/` — 캡처 → 분석 → 수정 iteration 루프

각 스킬은 클라이언트가 prepare → 생성 → ingest 순서와 병렬화·확인 규칙을 따르도록 안내합니다.

## Kiro / Codex

Claude Code 외의 하니스에서도 동일한 워크플로우를 스킬처럼 쓸 수 있습니다. Kiro 는
`.kiro/steering/ppt-generator.md` steering 과 `.kiro/settings/mcp.json` 을, Codex 는
`AGENTS.md` 와 `~/.codex/config.toml` 의 `[mcp_servers]` 를 씁니다. 설정 방법은
[kiro-codex.md](kiro-codex.md) 를 참조하세요.

## Visual QA (선택)

Visual QA 를 사용하려면 Playwright 브라우저 바이너리가 필요합니다:

```bash
uv sync
uv run playwright install chromium
```

스크린샷 캡처만 서버에서 이뤄지고, 이미지에 대한 비전 분석·수정 JSON 생성은 클라이언트가 담당합니다. Playwright 미설치 시 나머지 기능에는 영향이 없습니다.
