---
inclusion: always
---

# ppt-generator — 발표자료 생성 워크플로우

`ppt-generator` MCP 서버로 발표자료를 만든다. **서버는 LLM 을 호출하지 않는다.**
각 생성 단계는 `prepare_*`(system/user 프롬프트 + `response_schema` 반환)와
`ingest_*`(검증·후처리·저장)의 쌍이다. 그 사이의 JSON 생성은 **네가(클라이언트)**
`response_schema` 를 정확히 따라 수행하고 `ingest_*` 로 되돌린다.

이 파일은 Claude Code 스킬(`skills/ppt-*/SKILL.md`)과 동일한 안내를 Kiro 에 제공한다.
세부가 필요하면 해당 `SKILL.md` 를 열어 그대로 따른다. 스킬 원문이 소스이며 이 steering
은 요약이다.

## 신규 덱 (아웃라인 → 디자인 → 내보내기)

1. **아웃라인** (`skills/ppt-outline`)
   - `prepare_outline` **전에** 사용자에게 물어볼 것: 목적(purpose), 발표 시간
     (presentation_minutes, 3~60), 청중(audience_type: general/technical/executive),
     발표자 정보. 명시 안 했으면 기본값을 쓰지 말고 물어본다.
   - `prepare_outline` → `response_schema` 대로 아웃라인 JSON(`{"slides":[...]}`) 생성
     → `ingest_outline` → **아웃라인을 사용자에게 보여주고 확인받는다.**
   - 수정 요청 시 JSON 만 고쳐 `ingest_outline` 을 다시 부른다 (같은 project_id).

2. **디자인** (`skills/ppt-design`)
   - `prepare_design_doc_draft` → (`{"skip":true}` 면 건너뜀) 초안 JSON 생성
     → `ingest_design_doc_draft` (덱 전체에서 1회).
   - 슬라이드마다 `prepare_design_slide` → spec JSON 생성 → `ingest_design_slide`.
     **여러 슬라이드를 병렬로** 처리한다 (서버측 stateless).
   - `finalize_design_spec` (1회) → **반드시** `export_html` + `export_pptx`
     → 양쪽 결과 확인 및 경로 공유.

## 편집 (`skills/ppt-modify`)

- 추가/수정: `prepare_slide_edit(action="add"|"update")` → JSON 생성 → 반환된 `edit_context`와 함께 `ingest_slide_edit`.
- 단일 컴포넌트: `prepare_modify_component` → (imported 슬라이드는 `stage="backfill"`
  먼저: backfill 생성 → `ingest_backfill` → 재시도) → JSON 생성 → `ingest_modify_component`.
- 이동/삭제: `move_slide` / `delete_slide` (순수 파일 연산, 생성 불필요).
- 외부 PPTX: `import_pptx` (결정론적 파싱, 아웃라인 없음 — add/update 시 title·content_summary inline).

## Visual QA (opt-in, `skills/ppt-visual-qa`)

`playwright install chromium` 필요. `capture_slides` → `prepare_visual_qa_analysis`
→ 스크린샷 분석 JSON 생성 → `ingest_visual_qa_analysis` → (이슈 있으면)
`prepare_visual_qa_fix` → 전체 spec JSON 생성 → `ingest_visual_qa_fix`
→ `finalize_visual_qa`. **사용자가 요청할 때만** 실행한다.

## 규칙

- 항상 `response_schema` 를 정확히 따르는 JSON 을 생성한다. ingest 검증 실패 시 스키마에
  맞게 고쳐 재시도.
- 슬라이드 생성은 병렬로 — 순차는 느리다.
- add/update/modify/finalize 후에는 항상 `export_html` 과 `export_pptx` 를 호출하고
  양쪽 결과 경로를 공유한다.
- HTML 결과에 영향을 주는 수정 후에는 같은 프로젝트를 `export_pptx`로도 내보내고,
  공유 렌더 의미(좌표·크기·타이포그래피·불렛·선·화살표·효과)가 PPTX에도 반영됐는지
  확인한다. 한쪽만 맞으면 완료하지 않는다.
- **lint 경고가 있으면 사용자에게 수정 여부를 물어본다** (임의로 넘기지 않는다).
- 사용자 확인 없이 다음 단계로 넘어가지 않는다.
