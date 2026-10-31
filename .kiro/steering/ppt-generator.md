---
inclusion: always
---

# ppt-generator — 발표자료 생성 워크플로우

`ppt-generator` MCP 서버로 발표자료를 만든다. **서버는 LLM 을 호출하지 않는다.**
각 생성 단계는 `prepare_*`(system/user 프롬프트 + `response_schema` 반환)와
`ingest_*`(검증·후처리·저장)의 쌍이다. 그 사이의 JSON 생성은 **네가(클라이언트)**
`response_schema` 를 정확히 따라 수행하고 `ingest_*` 로 되돌린다.

## 절차는 스킬 원문을 따른다

**워크플로우의 소스는 `skills/ppt-*/SKILL.md` 하나다.** 이 steering 은 어느 스킬을
언제 열지만 안내하고, 단계별 절차·도구 인자·lint 처리 기준은 복제하지 않는다
(복제하면 한쪽만 갱신돼 지침이 엇갈린다). 작업을 시작하기 전에 해당 `SKILL.md` 를
열어 그대로 따른다.

| 상황 | 열어볼 스킬 |
| --- | --- |
| 새 덱 시작 (아웃라인) | `skills/ppt-outline/SKILL.md` |
| 아웃라인 → 슬라이드 생성 | `skills/ppt-design/SKILL.md` |
| 발표 대본·발표자 노트 작성 및 수정 | `skills/ppt-speaker-script/SKILL.md` |
| 슬라이드 추가·수정·삭제·이동, 외부 PPTX 임포트 | `skills/ppt-modify/SKILL.md` |
| 스크린샷 기반 시각 검사·저위험 patch | `skills/ppt-visual-qa/SKILL.md` |
| 임포트 충실도 검증 | `skills/ppt-import-verify/SKILL.md` |

디자인 의도의 품질(내러티브 아크, 밀도, AI slop 회피)은 `presentation-design` 스킬을
함께 참고한다.

## 하니스 무관 규칙

스킬을 열 수 없는 상황에서도 지켜야 하는 것들만 남긴다.

- 항상 `response_schema` 를 정확히 따르는 JSON 을 생성한다. ingest 검증 실패 시 반환된
  오류에 맞게 고쳐 재시도한다.
- 슬라이드 생성은 **병렬로** — 서버측 stateless 라 순차 처리는 느리기만 하다.
- 아웃라인은 Title → Agenda → 최소 1개 Body → Closing 구조의 4~20장이다.
- 완성 덱 요청은 별도 아웃라인 승인 없이 디자인, 발표 대본, deck review, Visual QA까지 진행한다.
- 여러 편집 중에는 증분 HTML을 사용하고 안정 체크포인트에서 `export_html`과
  `export_pptx`를 한 번 호출한다. 최종 HTML은 반드시 브라우저로 연다.
- 저위험 Visual QA patch는 자동 적용한다. 텍스트·데이터·요소 수·슬라이드 수 변경만
  사용자에게 확인한다.
