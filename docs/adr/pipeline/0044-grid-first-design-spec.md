# ADR-0044: Grid-First Design Spec — 그리드 우선 디자인 스펙

Date: 2026-05-19

## Status

Proposed

## Context

현재 design_spec 생성은 LLM이 textbox/shape의 절대 좌표(`left_px`, `top_px`, `width_px`, `height_px`)를 직접 산출한다. 결과적으로:

1. **그리드 추상화 부재** — 슬라이드가 어떤 영역(header/content/footer)으로 나뉘고 content가 몇 열로 구성되는지가 spec 어디에도 명시되지 않는다. `design_system_content.prompt.md`에는 hint별 좌표 패턴(예: `step_cards 3 cards: width=352, gap=32 → left: 64, 448, 832`)이 자연어로만 존재한다.
2. **사후 추정 기반 lint** — `sibling-grid-uniformity` 등 그리드 룰은 좌표만 보고 row/column 그룹을 추정한다. 의도적인 row span/col span을 구분할 수 없어 false positive(의도된 비대칭을 위반으로 판정) / false negative(좌표 우연 일치를 한 그룹으로 판정 못함)가 모두 발생한다.
3. **점진적 추상화 부재** — 한 번의 LLM 호출이 "어디에 무엇을 둘지"와 "각 element의 정확한 px"를 동시에 결정한다. 큰 구획 결정이 먼저 잡혔다는 보장이 없어 결과가 불안정하다.
4. **y축 영역의 암묵적 운용** — 제목(top=72, height=48)과 footer(top≥540) 좌표 컨벤션이 prompt 텍스트로만 존재하고, 어떤 슬라이드에 footer가 있는지 spec에서 식별이 불가하다.

ADR-0040(layout planning phase)은 outline 단계에서 자연어 `layout_plan`을 도입했으나, design 단계가 그 plan을 좌표로 옮기는 과정에는 여전히 그리드 표현이 없다.

## Decision

Design 단계의 산출물을 **2단 추상화**로 구성한다.

```
design_summary (presentation-level)
  ├─ header/content/footer 픽셀 범위 결정
  └─ 모든 슬라이드가 공유

design_spec (slide-level)
  ├─ Stage 1: grid_plan (구획 + 행/열 + cell 정의)
  └─ Stage 2: PptxSlideSpec (cell을 좌표로 구체화, 각 element는 cell 참조)
```

### 결정 1 — `design_summary`에 y축 영역 픽셀 범위 추가

`design_summary`(presentation 전체에 한 번 산출)에 다음 필드를 추가한다.

- `header_region`: `{top_px, height_px}` (옵셔널, 슬라이드별 사용 여부는 grid_plan이 결정)
- `content_region`: `{top_px, height_px}` (필수)
- `footer_region`: `{top_px, height_px}` (옵셔널)

이를 통해 모든 슬라이드의 y축 구획이 일관된다. footer를 쓰는 슬라이드와 안 쓰는 슬라이드가 섞여도 footer가 들어가는 위치는 항상 동일하다.

### 결정 2 — `PptxSlideSpec`에 `grid_plan` 필드 추가

각 슬라이드 spec은 다음 구조의 `grid_plan`을 가진다.

- `regions`: 사용하는 영역 목록 — `["header", "content"]`, `["header", "content", "footer"]` 등
  - `header`는 권장(제목 슬라이드/closing 제외 시 거의 필수)
  - `content`는 필수
  - `footer`는 옵셔널
- `content_columns`: content 영역의 열 수 (1~4)
- `content_rows`: content 영역의 행 수 (1~N, 보통 1~3)
- `cells`: cell 목록. 각 cell은 다음을 가진다.
  - `id`: 슬라이드 내 고유 식별자 (예: `"c1"`, `"c2"`)
  - `region`: `"header"` | `"content"` | `"footer"`
  - `row`, `col`: 1-based 시작 위치
  - `row_span`, `col_span`: 차지하는 행/열 수 (기본 1)
  - `role`: 자유 텍스트 라벨 (예: `"title"`, `"step1_card"`, `"left_diagram"`) — 디버깅/lint 메시지용

### 결정 3 — 각 element에 `grid_cell` 참조

`PptxTextBox`, `PptxShape`, `PptxImage`에 `grid_cell` 필드를 추가한다.

- `grid_cell`: cell `id` 문자열, 또는 `null` (decorative line/arrow처럼 grid에 속하지 않는 요소)
- 한 cell에 여러 element가 매핑될 수 있다(예: card shape + 그 위의 label textbox). 단 lint는 "겹치는 element가 동일 cell을 명시했는지"를 검증해 의도된 중첩과 실수에 의한 중복을 구분한다.
- 좌표(`left_px` 등)는 여전히 element가 직접 가진다 — 렌더 파이프라인 변경 최소화. cell 좌표와 element 좌표는 lint가 일치 여부를 검증한다.

### 결정 4 — Design LLM의 2-pass 산출

Design 단계 LLM이 1회 호출 안에서 다음 순서로 출력하도록 프롬프트를 강제한다.

1. **Stage 1 (grid_plan first)**: outline의 `layout_plan`(자연어)을 받아 먼저 `grid_plan` JSON을 출력한다. cell 정의까지 끝낸다.
2. **Stage 2 (concretize)**: 자기 자신의 `grid_plan`을 self-conditioning으로 사용해 textbox/shape/image의 좌표와 스타일을 채운다. 모든 element는 cell `id`를 참조한다.

LLM이 두 스테이지를 한 응답에 모두 포함하므로 추가 호출 비용은 없다. `<output_schema>`를 grid_plan 우선으로 재배치해 LLM이 자연스럽게 그리드부터 결정하도록 유도한다.

### 결정 5 — Lint 강화 (4가지 신규 규칙)

기존 `sibling-grid-uniformity`는 grid_plan을 직접 읽도록 재구현한다. 추가/변경되는 lint 규칙:

1. **`grid-plan-required`** (error): content slide_type 슬라이드에 `grid_plan` 누락 또는 `regions`에 `"content"` 부재. `content_columns`이 1~4 범위를 벗어나면 위반.
2. **`grid-cell-uniformity`** (warning, 기존 `sibling-grid-uniformity` 대체): 같은 row의 cell들은 height 균일, 같은 column의 cell들은 width 균일. row_span/col_span을 인지해 의도적 비대칭은 예외.
3. **`grid-cell-coverage`** (warning): 선언된 cell 중 어느 element에서도 참조되지 않는 cell이 있거나(빈 cell), 한 cell에 매핑된 element들이 cell bbox 밖으로 나가는 경우 경고.
4. **`region-stacking`** (error): footer가 사용된 슬라이드에서 content cell의 bottom이 footer top을 침범하면 위반. design_summary가 정의한 region 픽셀 범위를 기준으로 검증.

기존 `sibling-grid-uniformity`는 `grid-cell-uniformity`로 흡수되며 grid_plan이 있을 때는 좌표 추정 fallback을 끈다. grid_plan이 없는 imported PPTX 등 legacy spec은 좌표 추정 fallback을 유지한다.

## Technical Details

### 추상화 점진적 하강

```
1. outline.layout_plan         "horizontal 3 cards"  (자연어)
   ↓
2. grid_plan                    regions=[header, content], content_columns=3,
                                cells=[c1(header,1,1), c2(content,1,1), c3(content,1,2), c4(content,1,3)]
   ↓
3. element 좌표                  shape(grid_cell="c2", left=64, top=148, w=362, h=508)
```

각 단계는 한 단계 위 추상화의 결정을 좌표화할 뿐이며, 새로 무언가를 결정하지 않는다.

### grid_plan과 좌표의 관계

cell 좌표는 design_summary의 region 픽셀 범위 + content_columns/content_rows로 **유도 가능**하다. 그러나 spec에는 element가 직접 px를 가진다(중복). 이 중복은 의도적이다:

- **렌더 파이프라인(HTML/PPTX) 무변경**: 기존 좌표 기반 렌더러가 그대로 동작한다.
- **Lint가 정합성 검증**: cell 좌표와 element 좌표 불일치는 lint가 잡는다.

추후 lint 통과율이 충분히 높아지면 element가 cell 참조만 갖고 좌표는 derive하는 방향으로 단순화 가능(현 ADR 범위 외).

### 영향 범위

- 프롬프트: `outline_system.prompt.md`(layout_plan 가이드 보강), `design_summary_user.prompt.md`(region 추가), `design_system_base.prompt.md` / `design_system_content.prompt.md`(grid_plan 출력 스키마와 2-pass 절차), `examples/`(grid_plan 포함 예시로 교체)
- 스키마: `PptxSlideSpec.grid_plan`, `PptxTextBox/Shape/Image.grid_cell` 추가. 기본값은 `None`/`null`로 두어 imported PPTX 호환.
- Lint: 신규 규칙 3개 추가, 기존 규칙 1개 grid_plan 인식 모드 추가.
- Review 프롬프트: lint 결과에 grid 위반이 포함되도록 입력 범위 갱신.

### 하위 호환성

- imported PPTX(grid_plan 없음): 모든 grid 관련 lint 규칙은 grid_plan 부재 시 skip 또는 legacy 추정 모드로 동작.
- 기존 generated 프로젝트: 재생성 전까지는 legacy 모드. 재생성 시점에 새 스키마로 산출.
- 신규 필드는 모두 옵셔널이므로 schema migration 없이 점진 도입 가능.

### Acceptance Criteria

1. design_summary 산출물에 `header_region`/`content_region`/`footer_region`이 포함되고, 모든 슬라이드가 동일 픽셀 범위를 공유한다.
2. content slide_type 슬라이드의 design spec 출력에 `grid_plan`이 포함되며, `content_columns`이 1~4 범위에 들어간다.
3. 모든 textbox/shape는 `grid_cell`을 명시하거나(decorative element는 명시적으로 `null`), lint가 미명시를 잡아낸다.
4. `grid-cell-uniformity` lint가 의도된 row_span/col_span에서 false positive를 내지 않는다.
5. footer가 선언된 슬라이드에서 content가 footer 영역을 침범하면 `region-stacking` lint가 error로 잡는다.
6. imported PPTX 프로젝트에서 lint 실행 시 grid 관련 규칙이 정상적으로 skip되어 기존 동작을 깨지 않는다.

### Out of Scope

- cell 참조만으로 좌표를 자동 도출하는 단순화 (향후 ADR)
- y축 영역 동적 분할 (예: 슬라이드별로 footer 높이를 다르게) — 현 ADR은 presentation-level 고정 범위
- content_columns ≥ 5 지원 — 1~4로 한정

## Consequences

긍정적:
- 디자인 의도(영역/열/cell)가 spec 구조에 박혀 정적 분석 가능 → lint 정확도 상승, false positive 감소
- 추상화 점진적 하강으로 LLM 산출 안정성 향상 (큰 결정 → 작은 결정 순서 강제)
- y축 영역이 presentation 내내 일관 → 슬라이드 전환 시 시각적 안정감
- review 단계가 grid 위반을 명시적으로 받아볼 수 있어 자동 수정 quality 상승 기대

부정적/리스크:
- LLM 출력 토큰 증가(grid_plan만큼) — design 단계 비용 소폭 증가
- 프롬프트와 스키마 동시 변경으로 회귀 리스크 — 기존 e2e 테스트 + golden spec 비교 필요
- imported PPTX와 generated PPTX의 lint 동작이 분기 → lint 코드 복잡도 상승
- 초기 도입 직후 LLM이 grid_plan과 좌표 간 불일치를 자주 낼 가능성 — review 루프에 의존하게 됨

## References

- [ADR-0011: 점진적 구체화 파이프라인 설계](./0011-progressive-refinement-pipeline.md)
- [ADR-0013: 디자인 스펙 기반 슬라이드 생성 파이프라인](./0013-design-spec-pipeline.md)
- [ADR-0033: Design Spec Post-Generation LLM Review](./0033-design-spec-post-generation-review.md)
- [ADR-0034: 슬라이드 추가 시 기존 디자인 스펙 참조를 통한 일관성 향상](./0034-add-slide-design-consistency.md)
- [ADR-0040: Layout Planning Phase](./0040-layout-planning-phase.md)
- [ADR-0041: Validator를 Lint로 전환](./0041-validator-to-lint.md)
