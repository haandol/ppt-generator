# ADR-0046: Progressive Abstraction in Design Output — 점진적 추상화 하강 출력

Date: 2026-05-19

## Status

Accepted

## Context

ADR-0044가 grid-first 디자인 스펙을 도입하며 LLM이 `grid_plan`(regions + columns/rows + cells)을 **먼저** 출력하고 그 다음 element 좌표를 채우도록 설계했다. ADR-0045는 `grid_plan`을 content 슬라이드에서 Pydantic Required로 강제했다.

그러나 현 `GridPlanOutput`은 다음 세 결정을 한 객체에 묶어 한 번에 출력하도록 한다.

1. **레이아웃 결정** — 어떤 region(header/content/footer)을 쓸지, content를 몇 행/열로 나눌지
2. **셀 할당** — 각 cell의 row/col, span, region 매핑, role 라벨
3. (그 다음) element가 cell을 참조해 좌표/스타일을 채움

LLM 관점에서 1과 2는 추상화 레벨이 다르다. 1은 슬라이드 전체 구조 결정(거시), 2는 각 영역의 분할 결정(중간), 3은 그 안의 시각 표현(미시)이다. 한 객체로 묶이면 LLM이 1을 충분히 결정하기 전에 2의 cell 정의로 넘어갈 수 있고, 결과적으로 cell 구성과 columns/rows가 어긋나는 사례가 발생한다.

ADR-0044의 자연어 표현 "추상화 점진적 하강"(outline.layout_plan → grid_plan → element 좌표)을 LLM 응답 스키마에서도 한 단계 더 쪼개 4단으로 명시하면, Pydantic 필드 선언 순서가 LLM 자기-조건화를 강화해 첫 시도 안정성이 더 높아질 것으로 기대된다. 본 ADR은 추가 LLM 호출 없이(비용/지연 변화 없이) 응답 모델 구조와 prompt만 갱신해 이를 달성한다.

## Decision

content 슬라이드용 응답 모델을 4단 점진적 추상화로 재구성한다.

```
Stage 1: outline               (입력, 변경 없음)
   ↓
Stage 2: grid_layout           regions + content_columns + content_rows
   ↓
Stage 3: cell_assignment       각 cell 의 row/col/span/region/role
   ↓
Stage 4: elements              cell_id 를 참조하는 textbox/shape 좌표·스타일
```

### 결정 1 — `GridPlanOutput` 분해

기존 `GridPlanOutput`(regions/columns/rows/cells)을 두 모델로 쪼갠다.

- **`GridLayoutOutput`** (Stage 2)
  - `regions: list[Literal["header", "content", "footer"]]`
  - `content_columns: int (1..4)`
  - `content_rows: int (>=1)`
- **`GridCellAssignmentOutput`** (Stage 3)
  - `cells: list[GridCellOutput]` — 기존 `GridCellOutput` 그대로 재사용

`GridCellOutput`은 변경 없음(id/region/row/col/span/role).

### 결정 2 — `ContentSlideSpecOutput` 필드 순서 재정의

```python
class ContentSlideSpecOutput(_BaseSlideSpecOutput):
    grid_layout: GridLayoutOutput          # Stage 2 (Required)
    cell_assignment: GridCellAssignmentOutput  # Stage 3 (Required)
    background_color: str | None = None
    speaker_notes: str = ""
    textboxes: list[TextBoxOutput] = ...   # Stage 4
    shapes: list[ShapeOutput] = ...        # Stage 4
    overflow: list[OverflowContent] = ...
```

Pydantic이 declared 순서로 schema를 생성하므로 LLM이 거시 → 중간 → 미시 순으로 채운다. 두 stage 필드 모두 Required이므로 ADR-0045의 강제 효과가 유지된다.

`SimpleSlideSpecOutput`(title/closing)은 두 필드 모두 Optional로 둔다.

### 결정 3 — `to_dataclass()`에서 통합

내부 dataclass `PptxSlideSpec.grid_plan: GridPlan | None`은 변경하지 않는다. `_BaseSlideSpecOutput.to_dataclass()`에서 `grid_layout`과 `cell_assignment`를 합쳐 단일 `GridPlan` dataclass로 변환한다.

```python
grid_plan = GridPlan(
    regions=list(self.grid_layout.regions),
    content_columns=self.grid_layout.content_columns,
    content_rows=self.grid_layout.content_rows,
    cells=[... from self.cell_assignment.cells],
)
```

이렇게 하면 lint, renderer, serializer 등 dataclass 소비자는 변경할 필요가 없다.

### 결정 4 — Prompt 갱신

`design_system_base.prompt.md`의 `<grid_first_principle>` 섹션을 4단 절차로 다시 쓴다.

```
Output order (mandatory for content slides):

1. grid_layout — choose regions and content_columns/content_rows
   based on the slide's purpose. Decide layout BEFORE thinking about
   individual cells.

2. cell_assignment — for the layout above, define each cell's
   row/col/span/region/role. All cells you intend to use must be
   declared here BEFORE any element is placed.

3. textboxes / shapes — fill content. Every element MUST reference
   a cell id from cell_assignment via `grid_cell`.
```

`design_user.prompt.md` / `design_batch_user.prompt.md` 끝의 `<output_requirements>` 라인도 4단 표현에 맞게 갱신한다(`grid_layout` + `cell_assignment` 모두 필수 명시).

### 결정 5 — visual_qa fix 경로도 동일 모델 사용

ADR-0045에서 visual_qa의 `fix_design_spec`가 `ContentSlideSpecOutput` / `SimpleSlideSpecOutput`을 사용하도록 변경된 부분은 그대로 유효. 본 ADR의 모델 재구성을 자동 반영한다.

## Technical Details

### 영향 범위

- `src/ppt_generator/interfaces/llm_output_models.py`
  - `GridPlanOutput` 제거(또는 alias로 임시 보존 후 단계적 제거 — 본 ADR에선 즉시 제거)
  - `GridLayoutOutput`, `GridCellAssignmentOutput` 신설
  - `ContentSlideSpecOutput` 필드 변경 — `grid_plan` → `grid_layout` + `cell_assignment`
  - `SimpleSlideSpecOutput` 동일하게 두 필드 옵셔널로 보유
  - `_BaseSlideSpecOutput.to_dataclass()`에서 두 필드를 `GridPlan`으로 합침
- `src/ppt_generator/interfaces/prompts/design_system_base.prompt.md`
  - `<grid_first_principle>` 섹션 4단 절차로 재작성
  - 예제 JSON snippet도 신규 필드명으로 갱신
- `src/ppt_generator/interfaces/prompts/design_system_content.prompt.md`
  - 본문 예제가 `grid_plan` 키를 직접 쓰는 부분 갱신
- `src/ppt_generator/interfaces/prompts/design_user.prompt.md`
- `src/ppt_generator/interfaces/prompts/design_batch_user.prompt.md`
- 테스트
  - `tests/test_slide_spec_output_models.py` — 신규 모델 구조에 맞춰 갱신
  - `_grid_plan()` 헬퍼를 `_grid_layout()` + `_cell_assignment()`로 분리
  - 두 필드 누락 시 ValidationError 검증 케이스 추가

### 하위 호환성

- 내부 dataclass `GridPlan` / `PptxSlideSpec.grid_plan`은 변경 없음 → 기존 design_spec.json 파일/lint/renderer/serializer 무영향
- 기존 generated 프로젝트의 design_spec.json은 dataclass 구조를 따르므로 호환 유지
- LLM 응답 모델만 변경되므로 외부 API 영향 없음
- imported PPTX는 LLM 호출이 없으므로 무영향

### Acceptance Criteria

1. content 슬라이드에서 `grid_layout` 또는 `cell_assignment` 누락 시 Pydantic ValidationError가 발생한다 (단위 테스트).
2. title/closing 슬라이드에서 두 필드 모두 부재가 정상 통과한다.
3. `to_dataclass()` 결과의 `PptxSlideSpec.grid_plan`은 기존 ADR-0044/0045 구조와 동일하다(regions/columns/rows/cells 모두 채워짐).
4. 기존 lint(`grid-plan-required`, `grid-cell-coverage`, `grid-cell-uniformity`, `region-stacking`)는 변경 없이 통과한다.
5. system prompt 예제 JSON이 신규 필드명을 사용한다.
6. 전체 pytest 회귀 없음.

### Out of Scope

- 다단 LLM 호출 분리 (별도 ADR 필요 — 비용/지연 영향 큼)
- imported PPTX 시점 grid 자동 추론 backfill
- 슬라이드별 region 픽셀 범위 동적 분할

## Consequences

긍정적:
- LLM 자기-조건화 강화 — 거시(layout) → 중간(cell) → 미시(element) 순서가 schema에 박혀 첫 시도 정합성 향상 기대
- 추가 호출 비용 없음 (단일 호출 유지)
- 4단 절차가 prompt 자연어와 schema 양쪽에서 일관 → review 단계도 동일 추상화로 피드백 가능

부정적/리스크:
- 응답 토큰 약간 증가(필드명 분리에 따른 키 중복) — 미미
- LLM이 cell_assignment의 cells 수와 grid_layout의 columns×rows 곱이 어긋나는 사례 가능 → lint(`grid-cell-coverage`)가 잡음
- 기존 e2e 회귀 가능 — 단위 테스트 + 샘플 슬라이드 생성으로 확인 필요

## References

- [ADR-0011: 점진적 구체화 파이프라인 설계](./0011-progressive-refinement-pipeline.md)
- [ADR-0040: Layout Planning Phase](./0040-layout-planning-phase.md)
- [ADR-0044: Grid-First Design Spec](./0044-grid-first-design-spec.md)
- [ADR-0045: Grid Plan Required by Slide Type](./0045-grid-plan-required-by-slide-type.md)
