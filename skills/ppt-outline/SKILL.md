---
name: ppt-outline
description: Start a presentation by generating its outline via the ppt-generator MCP server (prepare/ingest handshake). Use when the user wants to create a new slide deck / PPT / presentation, or "발표자료 만들어줘 / PPT 생성 / 프레젠테이션 초안". The server returns the prompt + JSON schema; YOU generate the outline JSON and hand it back.
---

# ppt-outline

프레젠테이션 아웃라인을 만든다. ppt-generator 서버는 LLM 을 호출하지 않는다 —
서버가 프롬프트와 출력 스키마를 주면 **네가(클라이언트) 그 스키마대로 아웃라인 JSON 을
생성**하고 서버에 되돌려주면 서버가 검증·저장한다.

## 사전 확인 (필수)

`prepare_outline` 을 호출하기 전에 사용자에게 반드시 확인한다. 명시하지 않았으면
기본값을 쓰지 말고 물어본다:

1. **목적**(purpose) — 예: 사내 기술 공유, 고객 제안, 컨퍼런스 발표
2. **발표 시간**(presentation_minutes) — 몇 분짜리인지 (3~60)
3. **청중**(audience_type) — general / technical / executive
4. **발표자 정보**(presenter_name, presenter_title, presenter_org) — 조직은 없으면 비워도 됨

## 절차

1. `mcp__ppt-generator__prepare_outline(topic, purpose, audience_type, presentation_minutes, num_slides, presenter_name, presenter_title, presenter_org)` 호출.
   - 반환: `system_prompt`, `user_prompt`, `response_schema`, `project_id`.
2. **네가** `system_prompt` 를 지침으로, `user_prompt` 를 입력으로 삼아
   `response_schema` 를 **정확히** 따르는 아웃라인 JSON (`{"slides": [...]}`) 을 생성한다.
   - 스키마의 required 필드(title, content_summary, component_hint, slide_type, layout_plan, speaker_notes)를 모두 채운다.
3. `mcp__ppt-generator__ingest_outline(project_id, outline_json)` 호출 — 서버가 검증·발표자 정보 주입·저장.
4. **아웃라인을 사용자에게 보여주고 확인받는다** (슬라이드 수, 제목, 구성). 수정 요청이 있으면
   아웃라인 JSON 을 고쳐 `ingest_outline` 을 다시 호출한다. `prepare_outline` 을 다시 부를 필요는 없다
   (같은 project_id 로 ingest 만 반복).
5. 확인이 끝나면 디자인 단계로 넘어간다 — `ppt-design` 스킬 참조.

## 규칙

- `response_schema` 를 어긴 JSON 을 만들지 않는다. ingest 가 검증 에러를 내면 스키마에 맞게 고쳐 재시도.
- 아웃라인 구조(무엇을·어떤 순서로)만 결정한다. 색상·폰트·좌표는 디자인 단계의 몫이다.
- 사용자 확인 없이 디자인 생성으로 넘어가지 않는다.
