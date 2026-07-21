# Visual QA Pipeline

## Status

Accepted (2026-07-21)

## Context

디자인 스펙 생성 후 실제 렌더링 결과에서 시각적 결함(의도하지 않은 줄바꿈, 요소 겹침, 텍스트 잘림 등)이 발생할 수 있다. 기존 `validator.py`는 좌표 기반 검증만 수행하며 실제 픽셀 렌더링 결과를 검증하지 않는다. Playwright는 큰 의존성이므로 opt-in 방식으로 구현한다.

## Decision

Playwright + Claude Vision 기반의 Visual QA 파이프라인을 opt-in MCP tool로 추가한다.

- `visual_qa` MCP tool: 디자인 스펙의 시각적 품질을 검사하고 자동 수정
- Playwright를 optional dependency group(`visual-qa`)으로 추가
- 런타임에 `try: import playwright` → `except ImportError`로 graceful degradation
- 디자인 스펙 생성 완료 후 사용자에게 visual QA 실행을 제안하고, 동의 시에만 실행

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

## Changes

- `pyproject.toml`: `visual-qa` dependency group에 `playwright` 추가
- `interfaces/constants.py`: `VISUAL_QA_*` 상수 추가 (PARALLEL, MAX_ITERATIONS, VIEWPORT)
- `interfaces/llm_output_models.py`: `VisualQAIssue`, `VisualQAOutput` Pydantic 모델 추가
- `interfaces/prompts/visual_qa_analysis.prompt.md`: 스크린샷 분석 시스템 프롬프트
- `interfaces/prompts/visual_qa_fix.prompt.md`: 디자인 스펙 수정 시스템 프롬프트
- `interfaces/prompts/design_system_content.prompt.md`: 방향 무관 Arrow endpoint 계약 추가
- `tools/visual_qa/__init__.py`, `controller.py`, `service.py`: 새 모듈
- `di/model_factory.py`: visual_qa 모델 생성 함수 추가
- `di/container.py`: `create_visual_qa_service` 메서드 추가
- `server.py`: `register_visual_qa_tools` 호출 및 MCP instructions 수정
- `tools/design/controller.py`: 응답에 `visual_qa_suggestion` 추가

## QA Loop

```
for iteration in range(max_iterations):
    1. Playwright로 문제 슬라이드 스크린샷 캡처 (1280x720)
    2. Claude Vision으로 스크린샷 분석 → 이슈 목록
    3. 이슈 없으면 pass
    4. 이슈 있으면 LLM으로 디자인 스펙 수정 → 저장 → HTML 재렌더링
    5. 남은 이슈 없으면 break
    6. Progress 리포트: iteration 완료 시 per_slide 상태 기반으로 한 번 보고
```

## Scope Constraints

- **분석(analysis)**: 시각적 렌더링 이슈만 감지. 슬라이드 콘텐츠(텍스트 문구, 데이터 값, 서술 흐름, 언어 선택)는 절대 지적하지 않는다.
- **수정(fix)**: 시각적 속성(위치, 크기, 폰트 크기, 색상, 정렬)만 변경. 텍스트 내용 자체를 수정하지 않는다. `text_truncation`/`overflow`를 리사이징/리포지셔닝으로 해결할 수 없으면 폰트 크기를 줄인다.

## Contract Integrity

분석 프롬프트가 열거하는 issue type과 분석 응답 스키마가 허용하는 issue type은
하나의 정식 분류 집합으로 취급한다. 한쪽에만 존재하는 분류는 허용하지 않으며,
프롬프트 또는 스키마가 바뀌면 계약 검증이 함께 실패해야 한다.

`has_issues`와 품질 등급은 LLM이 제공한 요약값을 신뢰하지 않고 검증된 issue
목록에서 서버가 계산한다. 빈 목록은 통과, 하나 이상의 issue는 수정 대상으로
분류한다.

수정 단계는 다음 보존 규칙을 따른다.

- 분석 이슈는 현재 슬라이드의 요소 종류와 인덱스 범위까지 서버가 검증한다.
- fix prepare는 검증된 이슈, 프로젝트·슬라이드 식별자와 현재 spec revision을 서명한
  컨텍스트로 반환한다. fix ingest는 재전달된 자유 형식 이슈가 아니라 이 컨텍스트로
  변경 권한과 stale 여부를 판단한다.
- 시각 결함과 무관한 슬라이드 필드는 기존 값을 보존한다.
- 텍스트박스, 도형과 이미지의 수 및 배열 순서를 보존한다.
- 요소의 immutable content와 component identity가 같은 인덱스에서 일치하지 않으면
  재정렬 또는 구조 변경으로 간주해 거부한다.
- 렌더 순서 결함은 검증된 이슈 목록에 레이어 관련 이슈가 있을 때만 `z_index`를
  변경해 수정한다. 배열 순서 변경은 요소 정체성을 훼손할 수 있어 허용하지 않는다.
- 기존 `z_index`는 레이어 관련 이슈가 없는 수정에서 보존한다.
- 배경색 등 슬라이드 전역 속성과 요소별 시각 속성은 해당 issue type이 허용한 경우에만
  변경한다.
- 위치·스타일 수정으로 해결할 수 없는 경우에도 텍스트 문구, 데이터, 발표자 노트는
  변경하지 않는다. 해결 불가능한 이슈는 미수정 상태로 보고한다.

## Alternatives Considered

| 대안 | 판단 |
|---|---|
| 프롬프트와 응답 스키마가 각각 issue type을 관리 | 드리프트가 런타임 검증 실패로 이어져 제외 |
| LLM의 `has_issues` 값을 그대로 사용 | issue 목록과 모순될 수 있어 제외 |
| 수정 결과 전체를 새 슬라이드로 간주 | 수정과 무관한 필드 손실 위험이 있어 제외 |
| 검증된 issue 목록과 기존 spec을 기준으로 서버가 요약·보존 | 계약과 데이터 무결성을 함께 보장해 채택 |

## 기존 필드 보존

`SlideSpecOutput` Pydantic 모델(LLM structured output)에는 `images`와 `slide_type` 필드가 없다. LLM은 시각적 속성만 수정하므로 이 필드를 생성할 수 없다.

`fix_design_spec()` 에서 LLM 출력을 `to_dataclass()`로 변환한 후, 기존 spec의 다음 필드를 복원한다:

| 필드 | 복원 조건 | 이유 |
|------|----------|------|
| `images` | 기존 spec에 images가 있을 때 | 배경 이미지, 임포트된 이미지 등 LLM이 생성할 수 없는 바이너리 데이터 |
| `slide_type` | 기존 spec의 slide_type이 `"content"`가 아닐 때 | title/closing 슬라이드의 배경 이미지 적용에 필요 |

## Progress Reporting

- progress 단위는 **iteration** 기반: `completed = iteration + 1`, `total = max_iterations`.
- iteration 완료 시 pass/fixed/pending 상태를 메시지에 포함하여 보고.
- 100% (`max_iterations/max_iterations`)는 `run_qa` 반환 후 controller에서만 보고 → 실제 완료 시점과 일치.
- 주의: 이전에는 슬라이드 수 기반 `completed_count` 누적 카운터를 사용했는데, (1) `max_iterations >= 2`일 때 중복 증가로 `done > total` (예: 11/10), (2) iteration 0 완료 시 이미 100%에 도달하여 후속 iteration 진행 중에도 완료로 표시되는 문제가 있었다.

## Consequences

- 디자인 스펙 생성 후 시각적 결함을 자동 감지하고 수정할 수 있다.
- Playwright 미설치 시에도 기존 기능에 영향 없음 (graceful degradation).
- 추가 LLM 호출 비용 발생 (분석 + 수정, 슬라이드당 최대 2회 반복).
- 스크린샷 파일이 `~/.ppt-generator/<project_id>/screenshots/`에 저장된다.
- issue 분류가 프롬프트와 스키마에서 어긋나면 배포 전에 검출된다.
- 수정 단계가 기존 렌더 순서와 비시각 필드를 보존하므로 부분 수정으로 인한 회귀를
  줄인다.
