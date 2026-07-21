---
name: ppt-design
description: Generate the design spec (per-slide layout/style) for a deck via the ppt-generator MCP server's prepare/ingest handshake, then export HTML. Use after an outline exists and the user wants to build/generate the slides. The server returns prompts + JSON schemas; YOU generate each slide's spec JSON. Keywords - "슬라이드 생성 / 디자인 생성 / 디자인 스펙 / build the slides".
---

# ppt-design

아웃라인으로부터 슬라이드 디자인 스펙을 생성한다. 서버는 LLM 을 호출하지 않는다 —
각 단계마다 서버가 프롬프트와 출력 스키마를 주면 **네가 그 스키마대로 JSON 을 생성**하고
되돌려주면 서버가 검증·정합화·저장·렌더·lint 한다.

전제: `ppt-outline` 으로 아웃라인이 만들어지고 사용자가 확인했어야 한다. 디자인 의도의
품질(내러티브 아크, 밀도, AI slop 회피)은 `presentation-design` 스킬을 함께 참고한다.

## 절차

### 1. DESIGN.md 초안 (덱 전체에서 1회)

1. `mcp__ppt-generator__prepare_design_doc_draft(project_id, color_theme)` 호출.
   - `{"skip": true}` 가 오면 이미 DESIGN.md 가 있는 것 — 그대로 재사용하고 이 단계를 건너뛴다.
   - 아니면 `system_prompt`, `user_prompt` 를 받아 **네가** 초안 JSON(theme + tone + page_requests)을
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
- 그 다음 **반드시** `mcp__ppt-generator__export_html(project_id)` 를 호출하고
  반환된 `slides_html_path` 를 사용자에게 공유한다.

### 4. lint 자동 처리 (경미=자동, 중대=보고)

finalize/export 의 lint 결과를 **경미**와 **중대**로 나눠 다르게 대응한다. 판단이
애매하면 중대로 취급한다.

**경미 (사용자에게 묻지 않고 알아서 처리)** — 대부분 의도된 레이아웃/장식에서 나오는
구조적 warning 이라 실제 시각 결함이 아닌 경우가 많다:
- `grid-cell-uniformity`, `grid-cell-coverage` (의도된 비대칭 강약 레이아웃·다이어그램 장식 도형)
- `element-out-of-grid-cell`, `textbox-shape-intrusion` (다이어그램 라벨·중첩 컨테이너)
- `slide-edge-alignment-*`, `arrow-endpoint-attachment`, `sibling-gap-minimum` 등 미세 정렬

처리 방법: 경미 warning 이 있는 슬라이드만 골라 `ppt-visual-qa` 로 **자동 검증**한다
(`capture_slides(slide_indices=...)` → 스크린샷 Read → 실제 결함 여부 육안 확인).
- 스크린샷상 실제 결함(텍스트 잘림, 도형 겹침, 화살표 붕 뜸 등)이 보이면
  `ppt-modify` 의 `prepare_slide_edit(action="update")` 로 **스스로 좌표를 고쳐 재생성**한다.
- 스크린샷이 깨끗하면 오탐으로 판단하고 그대로 둔다. 무엇을 자동 수정/무시했는지 한 줄로 요약 보고.

**중대 (반드시 사용자에게 보고하고 확인)** — 내용·구조 판단이 필요해 임의로 못 고치는 것:
- severity `error` (렌더 실패로 이어짐)
- 정보 손실을 부르는 `overflow` (담지 못한 컨텐츠 → 새 슬라이드 추가 여부는 사용자 몫)
- 슬라이드의 **메시지·구성 변경**이 필요한 결함 (문구 재작성, 슬라이드 분할 등)

- Playwright(chromium)가 없어 `capture_slides` 가 실패하면 자동 검증을 건너뛰고,
  경미 warning 목록만 요약해 알린 뒤 넘어간다 (설치는 강요하지 않는다).

## 선택 — 리뷰

디자인 규칙 위반을 LLM 관점으로 점검하려면: 슬라이드마다
`prepare_review(project_id, slide_index)` → 리뷰 JSON 생성 → 반환된 `review_context`와 함께 `ingest_review(...)`.
`has_high_severity` 이고 고칠 거면 반환된 `fix_feedback` 을 `prepare_slide_edit(action="update")`
의 재생성에 반영한다 (`ppt-modify` 스킬).

## 규칙

- 항상 `response_schema` 를 정확히 따르는 JSON 을 생성한다. ingest 검증 실패 시 스키마에 맞게 고쳐 재시도.
- 슬라이드 생성은 병렬로 — 순차로 하면 느리다.
- 생성/수정/마무리 후에는 항상 `export_html` 을 호출하고 `slides_html_path` 를 공유한다.
- lint 결과는 4단계 기준으로 처리한다 — **경미**한 warning 은 visual QA 로 자동 검증 후
  실제 결함만 스스로 고치고, **중대**한 건(error·overflow·메시지/구성 변경)은 사용자에게
  보고하고 확인받는다. 경미 warning 을 아무 검증 없이 그냥 넘기지 않는다.
