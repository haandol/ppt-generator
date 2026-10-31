---
name: ppt-design
description: Generate the design spec (per-slide layout/style) for a deck via the ppt-generator MCP server's prepare/ingest handshake, then export and compare HTML/PPTX. Use after an outline exists and the user wants to build/generate the slides. The server returns prompts + JSON schemas; YOU generate each slide's spec JSON. Keywords - "슬라이드 생성 / 디자인 생성 / 디자인 스펙 / build the slides".
---

# ppt-design

아웃라인으로부터 슬라이드 디자인 스펙을 생성한다. 서버는 LLM 을 호출하지 않는다 —
각 단계마다 서버가 프롬프트와 출력 스키마를 주면 **네가 그 스키마대로 JSON 을 생성**하고
되돌려주면 서버가 검증·정합화·저장·렌더·lint 한다.

전제: `ppt-outline` 으로 필수 발표 골격이 만들어져 있어야 한다. AI Slop 방지 기준은
DESIGN.md 초안에 내장되어 있으므로 별도 디자인 스킬 호출이 필요하지 않다.

## 절차

### 1. DESIGN.md 초안 (덱 전체에서 1회)

1. `mcp__ppt-generator__prepare_design_doc_draft(project_id, color_theme)` 호출.
   - `{"skip": true}` 가 오면 이미 DESIGN.md 가 있는 것 — 그대로 재사용하고 이 단계를 건너뛴다.
   - 아니면 `system_prompt`, `user_prompt` 를 받아 **네가** 초안 JSON
     (theme + tone + anti_slop + page_requests)을
     반환된 `response_schema` 에 정확히 맞춰 생성한다.
2. `mcp__ppt-generator__ingest_design_doc_draft(project_id, draft_json, color_theme)` 호출 — DESIGN.md 저장.

사용자가 직접 DESIGN.md 를 편집했다면 이 단계를 건너뛰고 편집본을 그대로 쓴다.

### 2. 슬라이드별 생성 (병렬)

슬라이드는 서버측에서 서로 독립이다. **여러 슬라이드를 동시에** prepare→생성→ingest 한다.

각 슬라이드 `i` (1-based)에 대해:

1. `mcp__ppt-generator__prepare_design_slide(project_id, slide_index=i)` 호출.
   - 반환: `system_prompt`, `user_prompt`(인접 슬라이드 컨텍스트·DESIGN.md 지시 포함),
     `response_schema`, `slide_type`, `thinking_budget`(사고 예산 힌트).
2. **네가** `response_schema` 를 정확히 따르는 슬라이드 spec JSON 을 생성한다.
   - `speaker_notes`는 입력 노트를 그대로 보존하거나 빈 문자열로 둔다.
     이 단계에서 대본을 생성·교정하지 않는다.
   - `thinking_budget` 이 크면(복잡한 다이어그램 등) 더 신중하게 사고한다.
   - content 슬라이드는 grid_layout·cell_assignment·design_doc 이 required 다 (스키마가 강제).
3. `mcp__ppt-generator__ingest_design_slide(project_id, slide_index=i, spec_json, generation_context)` 호출.
   - `generation_context` 는 같은 `prepare_design_slide` 응답의 opaque token을 그대로 사용한다.
   - 반환에 `overflow` 가 있으면 담지 못한 컨텐츠다 — 모아 두었다가 finalize 에 넘기거나
     새 슬라이드로 추가할지 사용자와 상의한다.
   - `lint` 가 있으면 위반 목록이다.

### 3. 마무리 (1회)

- 모든 슬라이드 ingest 후 `mcp__ppt-generator__finalize_design_spec(project_id, overflow_json)` 호출
  (모은 overflow 를 JSON 배열 문자열로; 없으면 "").
- `ppt-speaker-script` 스킬을 읽고 실제 덱에 맞는 대본을 작성·검토·저장한다.
  사용자가 대본 생성을 생략하도록 요청했다면 기존 노트를 보존하고 건너뛴다.
  이 호출은 대본 저장까지 진행한 뒤 이 워크플로로 돌아온다.
- `mcp__ppt-generator__prepare_deck_review(project_id)` → review JSON 생성 →
  `mcp__ppt-generator__ingest_deck_review(...)` 로 덱 전체의 근거·중복·용어·서사를
  read-only 검토한다. high 의미 이슈만 사용자 결정을 요청한다.

### 4. lint와 Visual QA

완성된 덱 요청은 read-only Visual QA와 저위험 시각 patch를 포함한다. lint warning이
있거나 렌더 확인이 필요한 슬라이드를 우선 캡처한다.

**경미** — 의도된 레이아웃/장식에서도 발생할 수 있는 구조적 warning:
- `grid-cell-uniformity`, `grid-cell-coverage` (의도된 비대칭 강약 레이아웃·다이어그램 장식 도형)
- `element-out-of-grid-cell`, `textbox-shape-intrusion` (다이어그램 라벨·중첩 컨테이너)
- `slide-edge-alignment-*`, `arrow-endpoint-attachment`, `sibling-gap-minimum` 등 미세 정렬

처리 방법:
- 경미 warning 은 슬라이드 번호와 규칙을 짧게 요약한다.
- 실제 결함이 확인되면 `ppt-visual-qa`의 최소 patch를 적용하고 재캡처한다.
- 텍스트·데이터·요소 수·슬라이드 수 변경은 사용자 확인 전 적용하지 않는다.

**중대** — 실제 결함을 확인한 뒤 수정 범위를 판단한다:
- severity `error`는 원인을 확인하고, 스키마·연결 계약을 복구한다. 의미 관계를
  바꿔야 하는 경우에만 사용자 결정을 요청한다.
- 정보 손실을 부르는 `overflow` (담지 못한 컨텐츠 → 새 슬라이드 추가 여부는 사용자 몫)
- **레이아웃 파손** (`text-overflow`, `text-width-overflow`, `canvas-overflow`, `nowrap-overflow`
  등 텍스트가 잘리거나 박스·캔버스를 벗어남): 먼저 박스 크기·위치·패딩·폰트·autofit의
  저위험 시각 patch로 해결하고 재캡처한다. 가독성을 유지한 시각 수정으로 해결할 수 없어
  텍스트 축약·삭제·슬라이드 분할이 필요할 때 사용자에게 선택지를 제시한다.
- 슬라이드의 **메시지·구성 변경**이 필요한 결함 (문구 재작성, 슬라이드 분할 등)

- Playwright 캡처가 불가능하면 사용 가능한 클라이언트 브라우저로 PNG를 만든 뒤
  `prepare_visual_qa_analysis(..., screenshot_path=...)`에 전달한다.

### 5. 최종 내보내기

- QA가 끝난 안정 체크포인트에서 `export_html`과 `export_pptx`를 같은 DesignSpec에 호출한다.
- `mcp__ppt-generator__export_speaker_script(project_id)`를 호출해 현재 노트의
  Markdown 대본을 내보낸다. 순서나 제목이 바뀌었다면 이전 대본을 재사용하지 않는다.
- 반환된 HTML을 사용 가능한 브라우저 또는 `open` 명령으로 반드시 연다.
- Markdown 대본·HTML/PPTX 경로와 미해결 의미·시각 이슈를 공유한다. medium 이슈도 관련 슬라이드와
  함께 요약한다. 검사를 실행하지 못한 경우 그 범위와 이유를 명시한다.

## 선택 — 리뷰

디자인 규칙 위반을 LLM 관점으로 점검하려면: 슬라이드마다
`prepare_review(project_id, slide_index)` → 리뷰 JSON 생성 → 반환된 `review_context`와 함께 `ingest_review(...)`.
`has_high_severity` 이고 고칠 거면 반환된 `fix_feedback` 을 `prepare_slide_edit(action="update")`
의 재생성에 반영한다 (`ppt-modify` 스킬).

## 규칙

- 항상 `response_schema` 를 정확히 따르는 JSON 을 생성한다. ingest 검증 실패 시 스키마에 맞게 고쳐 재시도.
- 슬라이드 생성은 병렬로 — 순차로 하면 느리다.
- 여러 수정 중에는 슬라이드 HTML만 증분 렌더하고 최종 체크포인트에서 두 출력을 만든다.
- Visual QA patch는 시각 필드만 바꾼다. 메시지·구성 변경은 사용자에게 확인받는다.
