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
     프롬프트의 output_format 대로 생성한다.
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
3. `mcp__ppt-generator__ingest_design_slide(project_id, slide_index=i, spec_json)` 호출.
   - 반환에 `overflow` 가 있으면 담지 못한 컨텐츠다 — 모아 두었다가 finalize 에 넘기거나
     새 슬라이드로 추가할지 사용자와 상의한다.
   - `lint` 가 있으면 위반 목록이다.

### 3. 마무리 (1회)

- 모든 슬라이드 ingest 후 `mcp__ppt-generator__finalize_design_spec(project_id, overflow_json)` 호출
  (모은 overflow 를 JSON 배열 문자열로; 없으면 "").
- 그 다음 **반드시** `mcp__ppt-generator__export_html(project_id)` 를 호출하고
  반환된 `slides_html_path` 를 사용자에게 공유한다.
- 사용자에게 `ppt-visual-qa` (Playwright 필요) 로 시각 품질 검사를 할지 제안한다.

## 선택 — 리뷰

디자인 규칙 위반을 LLM 관점으로 점검하려면: 슬라이드마다
`prepare_review(project_id, slide_index)` → 리뷰 JSON 생성 → `ingest_review(...)`.
`has_high_severity` 이고 고칠 거면 반환된 `fix_feedback` 을 `prepare_slide_edit(action="update")`
의 재생성에 반영한다 (`ppt-modify` 스킬).

## 규칙

- 항상 `response_schema` 를 정확히 따르는 JSON 을 생성한다. ingest 검증 실패 시 스키마에 맞게 고쳐 재시도.
- 슬라이드 생성은 병렬로 — 순차로 하면 느리다.
- 생성/수정/마무리 후에는 항상 `export_html` 을 호출하고 `slides_html_path` 를 공유한다.
- lint 경고가 있으면 사용자에게 수정할지 물어본다 (임의로 넘기지 않는다).
