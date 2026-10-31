---
name: ppt-design
description: Turn an existing outline into a ppt-generator deck, coordinate design, script and quality review, and deliver the current HTML/PPTX and notes.
---

# ppt-design

아웃라인을 읽을 수 있는 덱으로 만든다. [공통 핸드셰이크](../_shared/handshake.md)와
[품질·최종 전달](../_shared/quality-and-delivery.md)을 적용한다. 디자인 의도는 DESIGN.md가
소유한다. 별도의 presentation-design 탐색은 사용자가 요청한 경우에만 필요하다.

## 덱 의도와 슬라이드 생성

1. `mcp__ppt-generator__prepare_design_doc_draft(project_id, color_theme)`.
   `skip=true`면 기존 DESIGN.md를 재사용한다. 아니면 반환 schema에 맞게 초안을 만들고
   `mcp__ppt-generator__ingest_design_doc_draft(project_id, draft_json, color_theme)`로 저장한다.
2. 각 1-based 슬라이드에 `mcp__ppt-generator__prepare_design_slide(project_id, slide_index)`를 호출한다.
   현재 `response_schema`, 아웃라인과 디자인 의도로 spec을 만든다. 사용자 고정값 외의
   배치·그룹·표현은 메시지와 핵심 관계를 보존하며 개선할 수 있다. 예시를 복제할 필요는 없다.
3. `mcp__ppt-generator__ingest_design_slide(project_id, slide_index, spec_json, generation_context)`.
   같은 prepare의 `generation_context`를 전달한다. 입력 노트를 보존하고 이 단계에서
   대본을 다시 쓰지 않는다. 반환된 overflow와 lint를 모아 판단한다.
4. 모든 슬라이드가 저장되면 `mcp__ppt-generator__finalize_design_spec(project_id, overflow_json)`.
   독립 슬라이드는 병렬 처리할 수 있지만 클라이언트 역량·의존성에 맞게 실행 방식을 선택한다.

## 대본과 덱 검토

`ppt-speaker-script`가 실제 덱에서 대본을 작성·검토·저장한 뒤 이 흐름으로 돌아온다.
사용자의 대본 생략 요청은 존중한다. 이후 `mcp__ppt-generator__prepare_deck_review(project_id)`
→ 생성 → `mcp__ppt-generator__ingest_deck_review(project_id, review_json, review_context)`로
근거·용어·반복·서사를 검토한다. 의미 변경이 기존 승인 범위를 벗어나면 사용자 결정을 받는다.

## 시각 품질과 완료

완성 덱에는 read-only Visual QA와 저위험 시각 patch를 포함한다. `ppt-visual-qa`를 적용하되
경고 수를 줄이기 위해 의도된 여백·비대칭을 없애지 않는다. 실제 잘림·겹침은 먼저 시각
속성으로 고치고, 내용 삭제나 슬라이드 추가가 필요하면 기존 요청의 권한 범위를 확인한다.
Visual QA patch는 텍스트·데이터·요소 수·슬라이드 수를 보존한다.
위험한 슬라이드에는 `prepare_review` → `ingest_review`를 선택적으로 사용할 수 있다.

최종 체크포인트의 `export_html`, `export_pptx`,
`mcp__ppt-generator__export_speaker_script(project_id)` 산출물을 확보한다.
같은 현재 명세로 이미 생성된 산출물은 재사용한다. 최종 HTML을 반드시 연다.
경로와 미해결 이슈, 실제 검증 범위를 전달한다.
