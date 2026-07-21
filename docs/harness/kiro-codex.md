# Kiro · Codex 에서 스킬로 쓰기

`ppt-generator` 는 Claude Code 플러그인으로 배포되지만, 워크플로우의 실체는
**MCP 서버 + `prepare_*`/`ingest_*` 핸드셰이크**다. 이 핸드셰이크는 JSON 을 생성할 수
있는 MCP 클라이언트라면 무엇이든 구동할 수 있으므로, **Kiro** 와 **Codex** 에서도
동일한 워크플로우를 쓸 수 있다.

차이는 하나뿐이다 — Claude Code 는 `skills/ppt-*/SKILL.md` 를 자동으로 로드하지만,
Kiro·Codex 는 그렇지 않다. 그래서 두 하니스에서는

1. **MCP 서버를 등록**하고 (서버가 `instructions` 로 핸드셰이크 개요를 이미 노출한다),
2. 각 하니스가 자동으로 읽는 위치에 **스킬 워크플로우 컨텍스트**를 얹어

Claude Code 의 스킬과 같은 안내를 받게 한다. 프롬프트·출력 스키마·후처리는 전부 서버
안에 있으므로 **어떤 하니스에서 돌리든 산출물은 동일**하다 (설계 배경:
[offload/0001](../adr/offload/0001-client-llm-offload-plugin.md)).

> 스킬 원문은 `skills/ppt-outline`, `skills/ppt-design`, `skills/ppt-modify`,
> `skills/ppt-visual-qa` 의 `SKILL.md` 다. 아래 진입점들은 이 파일들을 **참조**만 하고
> 복제하지 않는다 — 워크플로우의 소스는 언제나 `skills/` 하나다.

---

## 공통 — MCP 서버 등록

두 하니스 모두 로컬 클론을 stdio MCP 로 실행한다. 자격 증명은 필요 없다
(서버가 LLM 을 호출하지 않는다).

```bash
git clone https://github.com/haandol/ppt-generator.git
cd ppt-generator
uv sync
# Visual QA 를 쓸 거면
uv run playwright install chromium
```

등록에 쓸 커맨드는 아래와 같다. `/path/to/ppt-generator` 를 실제 클론 경로로 바꾼다.

```json
{
  "command": "uv",
  "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
  "env": { "PPT_LOG_DIR": "/tmp/ppt-generator" }
}
```

`env` 블록은 선택 사항이다(로깅용). 환경변수 전체는
[environment.md](environment.md) 참조.

---

## Kiro

Kiro 는 `.kiro/steering/*.md`(steering)와 `.kiro/settings/mcp.json`(MCP)를 자동으로
읽는다. 이 리포에는 두 파일이 이미 들어 있다:

- `.kiro/steering/ppt-generator.md` — prepare/ingest 워크플로우와 확인·병렬화 규칙을
  담은 steering. Kiro 가 세션마다 자동 로드한다 (front-matter `inclusion: always`).
- `.kiro/settings/mcp.json.example` — MCP 등록 예시. 실제 등록은 아래처럼 한다.

### 1. MCP 등록

`.kiro/settings/mcp.json`(워크스페이스) 또는 `~/.kiro/settings/mcp.json`(전역)에
서버를 추가한다:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": { "PPT_LOG_DIR": "/tmp/ppt-generator" },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

리포에 있는 `.kiro/settings/mcp.json.example` 을 복사해 `mcp.json` 으로 두고 경로만
고치면 된다. `autoApprove` 에 자주 쓰는 도구(예: `export_html`)를 넣으면 매번 승인
프롬프트가 뜨지 않는다.

### 2. steering 확인

`.kiro/steering/ppt-generator.md` 가 있으면 Kiro 가 자동으로 컨텍스트에 싣는다.
별도 설정은 필요 없다. steering 이 prepare→생성→ingest 순서, 사용자 확인 게이트,
슬라이드 병렬 생성 규칙을 안내하므로 Kiro 가 Claude Code 스킬과 동일하게 움직인다.

### 3. 사용

자연어로 요청하면 된다:

```
context.md 를 읽고 ppt-generator 로 발표자료를 만들어줘.
```

Kiro 가 `prepare_outline` → 아웃라인 JSON 생성 → `ingest_outline` → (확인) →
디자인 스펙 생성 → `export_html` 순으로 핸드셰이크를 구동한다.

---

## Codex

Codex 는 리포 루트의 [`AGENTS.md`](../../AGENTS.md) 를 자동으로 읽고, MCP 서버는
`~/.codex/config.toml` 의 `[mcp_servers.*]` 로 등록한다.

### 1. MCP 등록

`~/.codex/config.toml` 에 추가한다:

```toml
[mcp_servers.ppt-generator]
command = "uv"
args = ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"]
env = { PPT_LOG_DIR = "/tmp/ppt-generator" }
```

또는 CLI 로:

```bash
codex mcp add ppt-generator -- uv --directory /path/to/ppt-generator run ppt-generator
```

### 2. 워크플로우 컨텍스트

`AGENTS.md` 의 **"LLM Offloading — prepare/ingest"** 섹션에 핸드셰이크 규칙이 이미
정리돼 있어 Codex 가 이 리포에서 작업할 때 자동으로 참고한다. 스킬별 세부 절차가
필요하면 `skills/ppt-*/SKILL.md` 를 열어 그대로 따르라고 지시하면 된다.

리포 밖(임의 디렉토리)에서 발표자료만 만들 때처럼 `AGENTS.md` 가 로드되지 않는
상황이라면, 아래 프롬프트를 커스텀 프롬프트(`~/.codex/prompts/ppt.md`)로 저장해두고
`/ppt` 로 불러 쓰면 스킬과 같은 안내를 준다:

```markdown
ppt-generator MCP 서버로 발표자료를 만든다. 서버는 LLM 을 호출하지 않는다 —
각 생성 단계는 prepare_*(프롬프트+response_schema 반환) / ingest_*(검증·저장) 쌍이다.
네가 response_schema 를 정확히 따르는 JSON 을 생성해 ingest 로 되돌린다.

1. 아웃라인: prepare_outline(목적·시간·청중·발표자 먼저 물어볼 것) → JSON 생성
   → ingest_outline → 사용자에게 보여주고 확인.
2. 디자인: prepare_design_doc_draft → ingest_design_doc_draft(1회, skip:true 면 건너뜀)
   → 슬라이드마다 prepare_design_slide → JSON 생성 → ingest_design_slide (여러 슬라이드 병렬).
3. finalize_design_spec(1회) → export_html → slides_html_path 공유.
4. 수정: prepare_slide_edit / prepare_modify_component 흐름. 이동·삭제는 move_slide/delete_slide.
5. lint 경고가 있으면 사용자에게 수정 여부를 물어본다. 확인 없이 다음 단계로 넘어가지 않는다.
```

### 3. 사용

```
context.md 를 읽고 ppt-generator 로 발표자료를 만들어줘.
```

---

## 하니스별 진입점 요약

| 하니스        | 스킬 로딩            | MCP 등록 위치                       | 리포에 포함된 진입점                     |
| ------------- | -------------------- | ----------------------------------- | ---------------------------------------- |
| Claude Code   | `skills/` 자동 로드  | 플러그인 매니페스트                 | `.claude-plugin/plugin.json`, `skills/`  |
| Kiro          | steering 로 안내     | `.kiro/settings/mcp.json`           | `.kiro/steering/ppt-generator.md`, `.kiro/settings/mcp.json.example` |
| Codex         | `AGENTS.md` 로 안내  | `~/.codex/config.toml`              | `AGENTS.md`, 위 커스텀 프롬프트 템플릿   |

어느 하니스든 워크플로우의 실체와 산출물은 동일하다 — 진입점만 다르다.
