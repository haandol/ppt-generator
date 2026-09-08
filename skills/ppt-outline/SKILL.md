---
name: ppt-outline
description: Start a presentation by generating its outline via the ppt-generator MCP server (prepare/ingest handshake). Use when the user wants to create a new slide deck / PPT / presentation, or "발표자료 만들어줘 / PPT 생성 / 프레젠테이션 초안". The server returns the prompt + JSON schema; YOU generate the outline JSON and hand it back.
---

# ppt-outline

프레젠테이션 아웃라인을 만든다. ppt-generator 서버는 LLM 을 호출하지 않는다 —
서버가 프롬프트와 출력 스키마를 주면 **네가(클라이언트) 그 스키마대로 아웃라인 JSON 을
생성**하고 서버에 되돌려주면 서버가 검증·저장한다.

## 입력 보완

목적·발표 시간·청중이 명시되지 않았으면 요청 문맥에서 추론하거나 서버 기본값을
사용한다. 발표자 정보가 없으면 비워 두며 가짜 이름·직책·소속을 만들지 않는다.

## 절차

1. `mcp__ppt-generator__prepare_outline(topic, purpose, audience_type, presentation_minutes, num_slides, presenter_name, presenter_title, presenter_org)` 호출.
   - 반환: `system_prompt`, `user_prompt`, `response_schema`, `project_id`.
2. **네가** `system_prompt` 를 지침으로, `user_prompt` 를 입력으로 삼아
   `response_schema` 를 **정확히** 따르는 아웃라인 JSON (`{"slides": [...]}`) 을 생성한다.
   - 스키마의 required 필드와 `source_refs`, `assumptions`를 모두 채운다.
   - 4~20장, Title → Agenda → 최소 1개 Body → Closing 구조를 지킨다.
3. `mcp__ppt-generator__ingest_outline(project_id, outline_json)` 호출 — 서버가 검증·발표자 정보 주입·저장.
4. 아웃라인만 요청받았으면 결과를 보여주고 멈춘다. 완성된 덱 요청이면 바로
   `ppt-design` 단계로 진행한다.

## 규칙

- `response_schema` 를 어긴 JSON 을 만들지 않는다. ingest 가 검증 에러를 내면 스키마에 맞게 고쳐 재시도.
- 아웃라인 구조(무엇을·어떤 순서로)만 결정한다. 색상·폰트·좌표는 디자인 단계의 몫이다.
- 외부 사실·수치에 근거가 없으면 `assumptions`에 표시하고 출처를 지어내지 않는다.
