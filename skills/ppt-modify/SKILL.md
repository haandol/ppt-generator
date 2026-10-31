---
name: ppt-modify
description: Add, update, delete, move, or make narrow single-component edits to slides in an existing ppt-generator project (prepare/ingest handshake for LLM steps; move/delete are pure file ops). Also imports external PPTX for editing. Keywords - "슬라이드 추가/수정/삭제/이동 / 컴포넌트 수정 / PPTX 편집 / import pptx".
---

# ppt-modify

기존 프로젝트의 슬라이드를 편집한다. 서버는 LLM 을 호출하지 않는다 — 생성이 필요한
편집(add/update/component)은 prepare→생성→ingest 로, 생성이 필요 없는 편집(move/delete)은
단일 도구로 처리한다.

여러 편집은 먼저 완료하고, 안정 체크포인트에서 HTML/PPTX를 한 번 내보낸다.

## 발표자 노트만 수정

대본 작성·교정·분량 조정은 `ppt-speaker-script` 스킬을 따른다. 노트를 바꾸기 위해
슬라이드를 재생성하지 않는다. 이 경로는 임포트 덱에도 사용할 수 있다.

## 슬라이드 추가 / 수정 (add / update)

1. `mcp__ppt-generator__prepare_slide_edit(project_id, action, slide_index, title, content_summary, component_hint, slide_type, speaker_notes, color_theme)` 호출.
   - add: `slide_index` 는 삽입 위치(1-based, -1=끝). title·content_summary 필수.
   - update: `slide_index` 는 대상. title/content_summary 를 주면 outline 도 갱신.
     imported 프로젝트는 title·content_summary 필수.
   - 반환: `system_prompt`, `user_prompt`, `response_schema`, `action`.
2. **네가** `response_schema` 대로 슬라이드 spec JSON 을 생성한다.
3. `mcp__ppt-generator__ingest_slide_edit(project_id, action, slide_index, spec_json, edit_context, color_theme)` 호출. `edit_context`는 1단계 prepare 응답 값을 그대로 전달한다.
   — 같은 action·slide_index 를 넘긴다.
4. 변경된 슬라이드의 HTML과 lint 결과를 확인한다.

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
- 둘 다 인덱스는 1-based.

## 외부 PPTX 편집 (import)

1. `mcp__ppt-generator__import_pptx(file_path, project_id)` 로 외부 .pptx 를 프로젝트로 임포트.
   - `file_path` 는 원본 .pptx 경로. `project_id` 는 생략하면 새 프로젝트를 만든다.
2. imported 프로젝트는 outline 이 없다 — add/update 시 title·content_summary 를 inline 으로 넘긴다.
3. imported 슬라이드의 component 수정은 위 backfill 흐름을 따른다.

## 규칙

- 화면 내용이나 순서가 바뀌면 `ppt-speaker-script`의 기준으로 영향받은 노트와
  인접 슬라이드 전환을 다시 검토한다. 대본 수정 생략 요청은 보존한다.
- 최종 체크포인트에서 `mcp__ppt-generator__export_speaker_script(project_id)`를
  호출해 현재 제목·순서·노트에 맞는 Markdown을 내보낸다.
- 생성 단계에서는 항상 `response_schema` 를 정확히 따른다. ingest 검증 실패 시 고쳐 재시도.
- 편집 묶음이 끝나면 변경 슬라이드에 Visual QA를 실행하고 최종 `export_html` +
  `export_pptx`를 호출한다. HTML은 반드시 브라우저로 연다.
- lint 결과 처리 기준은 `ppt-design` 스킬의 "lint 처리" 절을 따른다. warning 은
  요약하되 저위험 시각 patch는 자동 적용한다. 메시지·요소 수·슬라이드 수 변경은
  사용자에게 확인한다.
