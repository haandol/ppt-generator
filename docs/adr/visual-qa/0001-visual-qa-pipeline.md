# Visual QA Pipeline

## Status

Accepted (2026-09-09)

## Context

디자인 스펙 생성 후 실제 렌더링 결과에서 시각적 결함이 발생할 수 있다. 좌표 기반
lint만으로는 브라우저 폰트 메트릭, 줄바꿈, 대비와 시각적 계층을 확인할 수 없다.
완성된 덱을 요청한 사용자가 별도 QA 용어를 알지 못해도 결과물의 기본 품질 검사는
수행되어야 한다.

## Decision Drivers

- end-to-end 생성 요청은 읽기 전용 시각 검사를 포함해야 한다.
- 의미를 바꾸지 않는 시각 수정은 별도 승인 없이 완료할 수 있어야 한다.
- 수정 응답은 전체 슬라이드를 다시 생성하지 않고 허용된 필드만 표현해야 한다.
- 콘텐츠와 구조 변경은 시각 수정과 분리되어 사용자 결정으로 남아야 한다.
- 브라우저 캡처 의존성이 없을 때 외부 스크린샷을 안전하게 사용할 수 있어야 한다.

## Decision

Playwright 스크린샷과 클라이언트 비전 생성을 결합한 Visual QA 파이프라인을 제공한다.

- 서버는 스크린샷 캡처와 결과 검증·저장만 담당한다.
- 클라이언트는 서버가 반환한 프롬프트·스키마·이미지로 분석과 수정 JSON을 생성한다.
- Playwright는 선택 의존성으로 유지한다.
- 완성된 덱 생성·편집 요청에서는 read-only 분석과 저위험 수정 루프를 기본 실행한다.
- Visual QA만 별도로 실행하거나 콘텐츠·구조 변경이 필요한 경우는 사용자 요청 경계를 따른다.
- Playwright를 사용할 수 없으면 클라이언트가 만든 외부 스크린샷 경로를 분석 입력으로 받을 수 있다.
- 분석과 수정은 DESIGN.md의 전역 의도와 해당 페이지 요청을 함께 받는다. 의도가
  없는 기존·임포트 프로젝트도 현재 명세와 화면으로 검사를 계속할 수 있다.

## Issue Types

| Issue Type | Description |
|---|---|
| `text_truncation` | 텍스트 컨테이너 경계에서 잘림 |
| `overlap` | 의도하지 않은 요소 겹침 |
| `label_intrusion` | 짧은 다이어그램 라벨이 형제 도형을 침범 |
| `decoration_overlap` | 배지·아이콘 장식이 무관한 카드와 겹침 |
| `arrow_through_card` | 화살표가 대상이 아닌 카드를 관통 |
| `orphan_label_no_arrow` | 흐름 라벨에 대응하는 화살표가 없음 |
| `overflow` | 텍스트가 박스 밖으로 넘침 |
| `contrast` | 텍스트-배경 간 대비 부족 |
| `misalignment` | 같은 행/열 정렬 불일치 |
| `arrow_disconnected` | 화살표 끝점이 연결 대상 edge에 닿지 않음 |
| `wrong_vertical_alignment` | 동일 행 peer 카드에 "middle" 사용으로 콘텐츠 시작 위치 불일치 |
| `inconsistent_font_size` | 같은 레벨 peer 요소 간 폰트 크기 불일치 |
| `inconsistent_padding` | 동일 행 peer 요소의 내부 padding 불일치 |
| `inconsistent_spacing` | peer 요소 간 간격 불일치 |
| `zero_gap` | 인접 요소 사이 여백이 없거나 지나치게 작음 |
| `small_font` | 본문/카드 텍스트가 14pt 미만으로 가독성 저하 |
| `insufficient_padding` | shape/textbox 내 텍스트와 경계 사이 여백 부족 (padding < 8px) |
| `content_too_sparse` | 슬라이드 콘텐츠가 본문 영역의 30% 미만만 차지하여 과도한 여백 |
| `content_too_dense` | 요소가 과밀하거나 폰트/패딩이 권장 최소값 이하로 축소됨 |
| `unbalanced_spacing` | 반복 요소의 광학적 간격과 밀도가 불균형 |
| `label_line_overlap` | 텍스트 라벨이 화살표·연결선과 겹침 |
| `hidden_decorative_strip` | 장식 스트립이 더 큰 도형 뒤에 가려짐 |
| `wrong_z_order` | 의도한 시각 계층과 렌더 순서가 불일치 |

## QA Loop

```
for iteration in range(max_iterations):
    1. Playwright로 문제 슬라이드 스크린샷 캡처 (1280x720)
    2. 클라이언트가 준비된 프롬프트·스키마로 스크린샷 분석 → 이슈 목록
    3. 이슈 없으면 pass
    4. 이슈 있으면 LLM으로 시각 속성 patch 생성 → 검증·적용 → HTML 재렌더링
    5. 남은 이슈 없으면 break
    6. Progress 리포트: iteration 완료 시 per_slide 상태 기반으로 한 번 보고
```

## Scope Constraints

- **분석(analysis)**: 시각적 렌더링 이슈만 감지. 슬라이드 콘텐츠(텍스트 문구, 데이터 값, 서술 흐름, 언어 선택)는 절대 지적하지 않는다.
- **수정(fix)**: 위치, 크기, 패딩, 정렬, 행간, autofit, 글꼴 크기, 색상과 검증된
  레이어 결함의 z-order만 변경한다. 텍스트 내용, 데이터 값, 요소 수·순서와 의미 링크는
  변경하지 않는다. 허용 범위로 해결할 수 없는 이슈는 미수정 상태로 보고한다.
- **의도 보존**: 본문 점유율 30% 미만이나 같은 행 요소의 차이만으로 명시된 전환
  여백·비대칭 강조를 결함으로 판정하지 않는다. 균일성은 같은 역할과 강조 수준에
  적용하며, 실제 잘림·충돌·가독성 문제를 화면에서 확인한다. 수정도 같은 의도를
  유지해야 하고 이를 보존한 수정이 불가능하면 미수정 상태로 보고한다.

## Contract Integrity

분석 프롬프트가 열거하는 issue type과 분석 응답 스키마가 허용하는 issue type은
하나의 정식 분류 집합으로 취급한다. 한쪽에만 존재하는 분류는 허용하지 않으며,
프롬프트 또는 스키마가 바뀌면 계약 검증이 함께 실패해야 한다.

`has_issues`와 품질 등급은 LLM이 제공한 요약값을 신뢰하지 않고 검증된 issue
목록에서 서버가 계산한다. 빈 목록은 통과, 하나 이상의 issue는 수정 대상으로
분류한다.

수정 단계는 전체 슬라이드 spec 대신 patch operation 목록을 사용하며 다음 규칙을 따른다.

- 분석 준비는 명세·디자인 의도·스크린샷과 프로젝트·슬라이드·iteration을 묶은
  검증 문맥을 반환한다. 분석 수신은 같은 준비 문맥을 되돌려 받아 현재 입력과 비교한다.
  문맥이 없거나 입력이 바뀌면 분석을 거부하고 준비부터 다시 실행하도록 안내한다.
  오래된 분석에 현재 입력의 지문을 새로 붙여 수정 권한을 발급하지 않는다.
- 분석 이슈는 현재 슬라이드의 요소 종류와 인덱스 범위까지 서버가 검증한다.
- fix prepare는 검증된 이슈, 프로젝트·슬라이드 식별자와 현재 spec revision을 서명한
  컨텍스트로 반환한다. fix ingest는 재전달된 자유 형식 이슈가 아니라 이 컨텍스트로
  변경 권한과 stale 여부를 판단한다.
- 시각 결함과 무관한 슬라이드 필드는 기존 값을 보존한다.
- operation은 기존 element 또는 slide의 허용된 시각 필드에 대한 replace만 허용한다.
- add, remove, move, 배열 재정렬과 텍스트 run 내용 변경은 허용하지 않는다.
- 렌더 순서 결함은 검증된 이슈 목록에 레이어 관련 이슈가 있을 때만 `z_index`를
  변경해 수정한다. 배열 순서 변경은 요소 정체성을 훼손할 수 있어 허용하지 않는다.
- 기존 `z_index`는 레이어 관련 이슈가 없는 수정에서 보존한다.
- 배경색 등 슬라이드 전역 속성과 요소별 시각 속성은 해당 issue type이 허용한 경우에만
  변경한다.
- 위치·스타일 수정으로 해결할 수 없는 경우에도 텍스트 문구, 데이터, 발표자 노트는
  변경하지 않는다. 해결 불가능한 이슈는 미수정 상태로 보고한다.
- 여러 독립 이슈 중 안전하게 해결 가능한 수정은 수행한다. 한 이슈를 해결할 수
  없다는 이유로 나머지를 포기하지 않으며, 안전한 수정이 하나도 없을 때 빈 patch를 반환한다.

수정 iteration이 끝나면 HTML과 PPTX를 같은 DesignSpec에서 다시 내보내고 HTML을
클라이언트의 사용 가능한 브라우저로 연다.

## Alternatives Considered

| 대안 | 판단 |
|---|---|
| 프롬프트와 응답 스키마가 각각 issue type을 관리 | 드리프트가 런타임 검증 실패로 이어져 제외 |
| LLM의 `has_issues` 값을 그대로 사용 | issue 목록과 모순될 수 있어 제외 |
| 수정 결과 전체 spec을 다시 생성 | 출력이 크고 무관한 필드가 흔들릴 수 있어 제외 |
| 검증된 issue 범위의 patch operation | 여러 요소의 저위험 수정과 데이터 보존을 함께 보장해 채택 |
| 모든 Visual QA를 별도 opt-in | 안전하지만 완성 요청에서도 결함이 남고 사용자가 내부 기능을 알아야 해 제외 |

## 기존 필드 보존

patch에 포함되지 않은 모든 slide, element, paragraph와 run 필드는 기존 값을 그대로
보존한다. images, slide_type, speaker_notes, grid_plan, design_doc, 배경 이미지와
component identity는 Visual QA patch 대상이 아니다. 허용된 replace를 모두 적용한 뒤
전체 slide spec을 다시 검증하고 렌더한다.

## Progress Reporting

- progress 단위는 **iteration** 기반: `completed = iteration + 1`, `total = max_iterations`.
- iteration 완료 시 pass/fixed/pending 상태를 메시지에 포함하여 보고.
- 100% (`max_iterations/max_iterations`)는 `run_qa` 반환 후 controller에서만 보고 → 실제 완료 시점과 일치.
- 주의: 이전에는 슬라이드 수 기반 `completed_count` 누적 카운터를 사용했는데, (1) `max_iterations >= 2`일 때 중복 증가로 `done > total` (예: 11/10), (2) iteration 0 완료 시 이미 100%에 도달하여 후속 iteration 진행 중에도 완료로 표시되는 문제가 있었다.

## Consequences

- 디자인 스펙 생성 후 시각적 결함을 자동 감지하고 수정할 수 있다.
- Playwright 미설치 시에도 기존 기능에 영향 없음 (graceful degradation).
- end-to-end 요청은 별도 승인 없이 read-only QA와 저위험 수정을 완료할 수 있다.
- patch 응답으로 토큰과 무관 필드 회귀 위험이 줄어든다.
- 클라이언트에서 분석과 수정 생성이 추가로 필요하다.
- 스크린샷 파일이 `~/.ppt-generator/<project_id>/screenshots/`에 저장된다.
- issue 분류가 프롬프트와 스키마에서 어긋나면 배포 전에 검출된다.
- 수정 단계가 기존 렌더 순서와 비시각 필드를 보존하므로 부분 수정으로 인한 회귀를
  줄인다.
