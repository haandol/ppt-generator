---
name: ppt-modify
description: Add, update, delete, move, or make narrow single-component edits to slides in an existing ppt-generator project (prepare/ingest handshake for LLM steps; move/delete are pure file ops). Also imports external PPTX for editing. Keywords - "슬라이드 추가/수정/삭제/이동 / 컴포넌트 수정 / PPTX 편집 / import pptx".
---

# ppt-modify

기존 프로젝트의 슬라이드를 편집한다. 서버는 LLM 을 호출하지 않는다 — 생성이 필요한
편집(add/update/component)은 prepare→생성→ingest 로, 생성이 필요 없는 편집(move/delete)은
단일 도구로 처리한다.

편집 후에는 **항상** `mcp__ppt-generator__export_html(project_id)` 와
`mcp__ppt-generator__export_pptx(project_id)` 를 같은 DesignSpec에 호출한다.
HTML과 PPTX의 공유 렌더 의미를 확인하고 두 결과 경로를 사용자에게 공유한다.

## 슬라이드 추가 / 수정 (add / update)

1. `mcp__ppt-generator__prepare_slide_edit(project_id, action, slide_index, title, content_summary, component_hint, slide_type, speaker_notes, color_theme)` 호출.
   - add: `slide_index` 는 삽입 위치(1-based, -1=끝). title·content_summary 필수.
   - update: `slide_index` 는 대상. title/content_summary 를 주면 outline 도 갱신.
     imported 프로젝트는 title·content_summary 필수.
   - 반환: `system_prompt`, `user_prompt`, `response_schema`, `action`.
2. **네가** `response_schema` 대로 슬라이드 spec JSON 을 생성한다.
3. `mcp__ppt-generator__ingest_slide_edit(project_id, action, slide_index, spec_json, edit_context, color_theme)` 호출. `edit_context`는 1단계 prepare 응답 값을 그대로 전달한다.
   — 같은 action·slide_index 를 넘긴다.
4. `export_html` + `export_pptx` → 공유 렌더 의미 확인 + 두 결과 경로 공유.

## 좁은 단일 컴포넌트 수정 (modify_component)

"LLM 박스를 빨갛게", "두 번째 카드 제목만 변경" 처럼 한 요소만 바꿀 때.

1. `mcp__ppt-generator__prepare_modify_component(project_id, slide_index, component_id, instruction, color_theme)` 호출.
   - 반환의 `stage` 를 본다:
     - `stage="modify"`: `response_schema` 대로 ComponentModify JSON 을 생성 → `ingest_modify_component(...)`.
     - `stage="backfill"` (imported 슬라이드, design_doc 없음): backfill JSON 생성 →
       `ingest_backfill(project_id, slide_index, backfill_json)` → 반환된 `available_components` 에서
       올바른 component_id 를 골라 `prepare_modify_component` 를 **다시** 호출.
2. `component_id` 는 `load_design_spec` 의 design_doc.layout leaf 에서 찾는다.
3. 넓은 변경(카드 3개 교체, 주제 전환, 레이아웃 재구성)은 대신 `prepare_slide_edit(action="update")` 를 쓴다.
4. `ingest_modify_component` 반환의 `slide_html_path` 를 사용자에게 공유.

## 이동 / 삭제 (LLM 불필요)

- `mcp__ppt-generator__move_slide(project_id, from_index, to_index)` — 순수 파일 재정렬.
- `mcp__ppt-generator__delete_slide(project_id, slide_index)` — 순수 삭제 + 재색인.
- 둘 다 인덱스는 1-based. 이후 `export_html` 과 `export_pptx` 로 새로고침하고
  양쪽 결과를 확인한다.

## 외부 PPTX 편집 (import)

1. `mcp__ppt-generator__import_pptx(pptx_path, ...)` 로 외부 .pptx 를 프로젝트로 임포트.
2. imported 프로젝트는 outline 이 없다 — add/update 시 title·content_summary 를 inline 으로 넘긴다.
3. imported 슬라이드의 component 수정은 위 backfill 흐름을 따른다.

## 규칙

- 생성 단계에서는 항상 `response_schema` 를 정확히 따른다. ingest 검증 실패 시 고쳐 재시도.
- 모든 편집 후 `export_html` + `export_pptx` 호출, 양쪽 결과 확인 + 경로 공유.
- lint 경고가 있으면 사용자에게 수정 여부를 물어본다.
