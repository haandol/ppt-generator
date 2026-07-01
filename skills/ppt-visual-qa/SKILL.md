---
name: ppt-visual-qa
description: Run visual QA on a generated deck — capture slide screenshots (server-side Playwright), then YOU analyze them for visual defects and generate fixes via the ppt-generator prepare/ingest handshake. Opt-in; needs `playwright install chromium`. Keywords - "비주얼 QA / 시각 검사 / 스크린샷 점검 / visual qa / pixel-perfect check".
---

# ppt-visual-qa

렌더된 슬라이드의 시각적 결함(줄바꿈, 겹침, 잘림, 대비, 정렬 등)을 스크린샷으로 점검하고
고친다. 스크린샷 캡처는 서버(Playwright)가, **비전 분석과 수정 spec 생성은 네가(클라이언트)**
담당한다. 반복 루프(분석→수정→재캡처)도 네가 오케스트레이션한다.

전제: 디자인 스펙이 생성돼 있어야 하고, 사용자가 동의해야 한다 (opt-in).
`playwright install chromium` 로 브라우저 바이너리가 설치돼 있어야 한다.

## 반복 루프

`max_iterations`(기본 2)만큼 반복하되, 이슈가 없어지면 멈춘다. iteration 은 0 부터 센다.

각 iteration `n` 에서:

### 1. 스크린샷 캡처 (서버)

`mcp__ppt-generator__capture_slides(project_id, slide_indices, iteration=n)` 호출.
- `slide_indices` 는 1-based comma 문자열 (빈 문자열 = 전체). 이후 iteration 에서는
  아직 이슈가 남은 슬라이드만 넘긴다.
- 반환: `screenshots: [{slide_index, screenshot_path}]`, `max_iterations`.

### 2. 분석 (슬라이드별, 병렬)

각 캡처된 슬라이드에 대해:
1. `mcp__ppt-generator__prepare_visual_qa_analysis(project_id, slide_index, iteration=n)` 호출.
   - 반환: `system_prompt`, `user_prompt`, `response_schema`, `images`(스크린샷 경로).
2. **네가** `images` 의 스크린샷을 읽고 spec 과 대조해 시각적 이슈를 찾아,
   `response_schema` 대로 분석 JSON 을 생성한다.
3. `mcp__ppt-generator__ingest_visual_qa_analysis(project_id, slide_index, analysis_json)` 호출.
   - 반환의 `has_issues` 가 false 면 이 슬라이드는 통과 — 다음 iteration 대상에서 제외.
   - true 면 `issues` 를 다음 단계로 넘긴다.

### 3. 수정 (이슈 있는 슬라이드만, 병렬)

이슈가 있는 각 슬라이드에 대해:
1. `mcp__ppt-generator__prepare_visual_qa_fix(project_id, slide_index, issues_json, iteration=n)` 호출.
   - `issues_json` 은 이전 단계 `issues` 를 JSON 배열 문자열로.
   - 반환: `response_schema`, `images`.
2. **네가** 이슈를 반영한 **전체** 슬라이드 spec JSON 을 `response_schema` 대로 생성한다.
3. `mcp__ppt-generator__ingest_visual_qa_fix(project_id, slide_index, fix_json)` 호출 — 저장·재렌더.
   - `status="fixed"` 면 다음 iteration 에서 이 슬라이드를 다시 캡처·분석해 검증.
   - `status="unfixed"` 면 검증 실패 — 그대로 두거나 재시도.

### 4. 마무리

- 반복이 끝나면 `mcp__ppt-generator__finalize_visual_qa(project_id)` 를 1회 호출.
- 반환된 `slides_html_path` 를 사용자에게 공유한다.

## 규칙

- 스크린샷을 실제로 읽고 분석한다 (`images` 경로). 근거 없이 이슈를 지어내지 않는다.
- 생성 단계에서는 항상 `response_schema` 를 정확히 따른다. ingest 검증 실패 시 고쳐 재시도.
- `max_iterations` 를 넘겨 무한히 반복하지 않는다. 이슈가 없어지면 즉시 멈춘다.
- 사용자가 동의한 경우에만 실행한다.
