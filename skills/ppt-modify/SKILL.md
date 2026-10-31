---
name: ppt-modify
description: Edit an existing ppt-generator deck or import a PPTX for editing; choose whole-slide, single-component, notes-only, or move/delete operations by the requested scope.
---

# ppt-modify

[공통 핸드셰이크](../_shared/handshake.md)와 [품질·전달](../_shared/quality-and-delivery.md)을
적용한다. 사용자가 지정한 편집 범위에 맞는 도구를 고르고, 관련 없는 내용을 보존한다.
이미 요청한 내용 변경을 다시 승인받지 않는다.

## 편집 범위 선택

- 노트·낭독 대본만 바꾸면 `ppt-speaker-script`를 사용한다.
- 한 textbox/shape의 문구·색·크기만 바꾸면 component 수정이 적합하다.
- 여러 요소, 배치 재구성이나 슬라이드 내용 변경은 add/update를 사용한다.
- 이동·삭제는 생성 없이 순수 파일 도구로 처리한다.

## 추가·수정과 단일 요소

`mcp__ppt-generator__prepare_slide_edit(project_id, action, slide_index, title, content_summary, component_hint, slide_type, speaker_notes, color_theme)`
→ 반환 schema로 생성 →
`mcp__ppt-generator__ingest_slide_edit(project_id, action, slide_index, spec_json, edit_context, color_theme)`.
같은 action·인덱스·edit_context를 전달한다. add의 -1은 끝에 추가이며 title·content_summary가 필수다.
임포트 덱의 update도 두 필드가 필요하다. 기존 슬라이드에서 확인한 정보를 사용해 채운다.

단일 요소는 저장된 design_doc의 leaf id를 확인한 뒤
`mcp__ppt-generator__prepare_modify_component(project_id, slide_index, component_id, instruction, color_theme)`.
`stage=modify`면 생성 후 `ingest_modify_component`에 같은 edit_context를 전달한다.
`stage=backfill`이면 생성 → `ingest_backfill` → available_components에서 올바른 id 선택 →
prepare_modify_component를 다시 호출한다. 임포트 의미 트리 보완이 실제 편집을 대신하지 않는다.

## 이동·삭제·임포트

- `mcp__ppt-generator__move_slide(project_id, from_index, to_index)`.
- `mcp__ppt-generator__delete_slide(project_id, slide_index)`.
- `mcp__ppt-generator__import_pptx(file_path, project_id)`로 외부 PPTX를 가져온다.
인덱스는 문서화된 add의 -1 외에는 1-based다. 진행 중인 준비 문맥이 있으면 재정렬 뒤 새로 준비한다.

## 검토와 전달

편집 묶음을 마친 뒤 영향받은 노트·인접 전환을 확인하고 변경 슬라이드에 Visual QA를 적용한다.
저위험 시각 patch는 자동 적용한다. 추가 메시지·요소 수·슬라이드 수 변경이 사용자 요청을
벗어나면 확인한다. 현재 노트의 `export_speaker_script`와 최종 `export_html`·`export_pptx`를
확보하고 HTML은 반드시 브라우저로 연다. 중간 단계마다 전체 덱을 다시 내보내지 않는다.
