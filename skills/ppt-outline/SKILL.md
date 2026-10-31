---
name: ppt-outline
description: Create a presentation outline with the ppt-generator prepare/ingest tools, then continue to design when a complete deck is requested.
---

# ppt-outline

주제·목적·근거를 슬라이드별 계획으로 만든다. 첫 서버 작업이면
[공통 prepare/ingest 지침](../_shared/handshake.md)을 읽는다.

## 입력과 판단

사용자 문맥과 저장된 발표 조건으로 청중·시간·목적을 보완한다. 발표자 정보가 없으면
비워 둔다. 아웃라인은 내용과 제안 구성을 소유하고 색·폰트·좌표는 디자인 단계에 맡긴다.
사용자가 고정한 수와 방향을 명시하며, 나머지 배치는 메시지를 보존하는 디자인 개선이 가능하다.

## 생성과 전달

1. `mcp__ppt-generator__prepare_outline(topic, purpose, audience_type, presentation_minutes, num_slides, presenter_name, presenter_title, presenter_org)`.
2. 반환 프롬프트와 `response_schema`로 JSON을 생성한다. 현재 계약은 4~20장,
   Title → Agenda → 최소 1개 Body → Closing이다. 범위를 벗어난 요청을 몰래 축소하지 않는다.
   제공된 `speaker_notes`는 그대로 보존하거나 빈 문자열로 둔다. 최종 대본은 실제 덱에서
   `ppt-speaker-script`가 작성한다. `source_refs`, `assumptions`도 보존한다.
3. `mcp__ppt-generator__ingest_outline(project_id, outline_json)`.
4. 아웃라인만 요청받았으면 결과를 전달한다. 완성 덱 요청이면 추가 승인 없이 `ppt-design`으로 이어간다.
