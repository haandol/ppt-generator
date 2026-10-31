---
name: ppt-visual-qa
description: Inspect actual slide screenshots and apply issue-scoped visual patches while preserving content, structure, notes and element identity.
---

# ppt-visual-qa

완성 덱 생성·편집 요청에는 이 검사가 포함된다. [공통 핸드셰이크](../_shared/handshake.md)와
[품질·전달](../_shared/quality-and-delivery.md)을 적용한다. 서버는 캡처·검증·저장을,
클라이언트는 시각 판단과 patch 생성을 담당한다.

## 캡처와 분석

1. `mcp__ppt-generator__capture_slides(project_id, slide_indices, iteration)`.
   인덱스는 1-based comma 문자열이고 iteration은 0부터 시작한다. 서버가 반환한
   max_iterations를 사용하며, 후속 캡처는 남은 이슈가 있는 슬라이드에 집중한다.
2. `mcp__ppt-generator__prepare_visual_qa_analysis(project_id, slide_index, iteration)`.
   실제 images를 읽고 spec·design_intent와 대조해 반환 schema로 분석한다.
3. `mcp__ppt-generator__ingest_visual_qa_analysis(project_id, slide_index, analysis_json, prepared_context)`.
   같은 prepare의 토큰을 되돌린다. 입력이 바뀌면 다시 준비한다. has_issues=false이면 그 슬라이드는 통과다.

서버 캡처의 선택 의존성은 `uv sync --group visual-qa` 및
`uv run --group visual-qa playwright install chromium`으로 준비한다. 서버 Playwright가
없으면 격리된 클라이언트 브라우저에서 PNG를 만들고 screenshot_path로 분석에 전달한다.
사용 가능한 캡처·비전 경로가 없으면 검사 불가 범위를 밝히며 성공 분석을 만들지 않는다.

## 수정과 재검증

`mcp__ppt-generator__prepare_visual_qa_fix(project_id, slide_index, analysis_context, iteration)`
→ 최소 operation 생성 →
`mcp__ppt-generator__ingest_visual_qa_fix(project_id, slide_index, fix_json, fix_context)`.
분석 ingest의 analysis_context와 fix prepare의 fix_context를 그대로 사용한다.

- fixed: 다시 캡처해 실제 효과를 검증한다.
- unfixed: 실패 이유에 맞춰 입력을 고치거나 재준비한다. 동일 요청을 맹목적으로 반복하지 않는다.
- unresolved: 허용된 시각 필드로 해결하지 못한 이슈를 보존·보고한다. 다른 독립적인 안전한 수정은 계속한다.

텍스트·데이터·요소 수·순서·슬라이드 수·의미 링크는 visual patch로 바꾸지 않는다.
이미 승인된 더 넓은 편집은 적절한 modify 도구로 보내며, 승인 범위 밖이면 사용자 결정을 받는다.

## 완료

이슈가 없어지거나 반환된 반복 상한에 도달하면 `mcp__ppt-generator__finalize_visual_qa(project_id)`.
마지막 수정의 재검증을 못 했다면 그 사실을 남긴다. 현재 명세에서 나온 산출물은 재사용하고,
HTML을 반드시 브라우저로 열고 경로·잔여 이슈·실제 검사 범위를 전달한다.
