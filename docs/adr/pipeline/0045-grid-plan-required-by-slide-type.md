# ADR-0045: Grid Plan Required by Slide Type — slide_type 분기 응답 스키마

Date: 2026-05-19

## Status

Accepted

## Context

ADR-0044에서 grid-first 디자인 스펙을 도입하면서 `PptxSlideSpec.grid_plan`과 LLM 출력 모델 `SlideSpecOutput.grid_plan`을 추가했다. 그러나 현 구현은 다음과 같이 누락을 강제하지 못한다.

1. **응답 스키마에서 `grid_plan`이 Optional**: `SlideSpecOutput.grid_plan: GridPlanOutput | None = None`. LLM이 `null`을 반환해도 structured_output 검증을 통과한다.
2. **User prompt 의무 명시 부재**: `design_user.prompt.md`, `design_batch_user.prompt.md`에 grid_plan 출력 의무가 없고, system prompt(`design_system_base.prompt.md`)의 `<grid_first_principle>`에만 존재한다.
3. **결과적인 LLM 누락**: 사용자 보고 — `modify_design_spec`으로 imported/기존 프로젝트의 슬라이드를 add/update할 때 디자인 스펙에 grid_plan이 자주 빠진다. lint(`grid-plan-required`)가 누락을 error로 잡지만 review 루프 재생성에서도 같은 누락이 반복될 수 있다.

ADR-0044의 결정 4(2-pass 산출)는 LLM이 grid_plan을 먼저 출력하도록 prompt로 유도하지만, 스키마 레벨 강제가 없어 첫 시도 실패율이 높다.

한편 ADR-0044 결정 2에 따르면 title/closing 슬라이드는 fixed special layout이므로 `grid_plan`이 없어도 정상이다. 따라서 단일 `SlideSpecOutput` 모델로는 Required/Optional을 slide_type별로 분기할 수 없다.

Imported PPTX 자체는 LLM을 호출하지 않으므로 import 시점의 grid_plan 부재는 정상이며 backfill 대상이 아니다. **imported 이후 LLM이 호출되는 모든 경로(`generate_slides_design_spec`, `modify_design_spec` add/update)에서만 grid_plan을 강제**하는 것이 본 ADR의 범위다.

## Decision

LLM 응답 모델을 slide_type에 따라 분기하여 content 슬라이드에 `grid_plan`을 Pydantic 레벨로 Required 표시한다.

### 결정 1 — slide_type별 응답 모델 분리

`SlideSpecOutput`을 두 모델로 분리한다.

- **`ContentSlideSpecOutput`**: content 슬라이드용. `grid_plan: GridPlanOutput` (Required, 필드 기본값 없음)
- **`SimpleSlideSpecOutput`**: title/closing 슬라이드용. `grid_plan: GridPlanOutput | None = None` (Optional)

두 모델은 grid_plan 외 필드(textboxes/shapes/background_color/speaker_notes/overflow)와 `to_dataclass()` 동작이 동일하므로 공통 부분은 mixin 또는 baseclass로 정리하되, 외부에 노출되는 응답 모델은 두 개로 명확히 구분한다.

기존 `SlideSpecOutput` 심볼은 하위 호환을 위해 `SimpleSlideSpecOutput`의 별칭으로 유지하지 않는다(테스트/외부 사용자 전수 검토 후 일괄 이행). 단 dataclass 변환 결과인 `PptxSlideSpec`은 ADR-0044대로 `grid_plan: GridPlan | None = None`을 유지한다 — imported PPTX는 dataclass 레벨에서 None 가능해야 하기 때문.

### 결정 2 — DesignService가 slide_type에 따라 응답 모델 선택

`DesignService._generate_with_structured_output()` 시그니처에 `slide_type: str` 인자를 추가한다.

```python
def _generate_with_structured_output(
    self, prompt: str, *, slide_type: str, label: str = "design_spec"
) -> PptxSlideSpec:
    model = (
        ContentSlideSpecOutput
        if slide_type == "content"
        else SimpleSlideSpecOutput
    )
    result = self._agent(prompt, structured_output_model=model)
    ...
```

`generate_single_slide()`에서 호출 시 `slide_outline.slide_type`을 그대로 전달한다. structured_output 프레임워크(strands)가 Required 누락 시 검증 실패를 발생시키며, 프레임워크의 자체 재시도 또는 예외 전파에 따라 처리된다(별도 service-level 재시도 로직은 도입하지 않음).

### 결정 3 — user prompt 보강 (선택적, 보조 수단)

`design_user.prompt.md`, `design_batch_user.prompt.md`의 끝부분에 다음 라인을 추가한다.

> If this slide is a content slide, you MUST output `grid_plan` (regions/content_columns/content_rows/cells) before any element. The response schema requires it.

system prompt의 `<grid_first_principle>`과 중복되지만, user prompt 말미에서 LLM 어텐션을 끌어올리는 보조 수단이다. 첫 시도 성공률을 높이기 위함이며 강제력은 결정 1·2가 담당한다.

### 결정 4 — Imported 경로 무변경

- `import_pptx`: LLM 호출 없음 → grid_plan 없이 저장(현 동작 유지)
- imported 프로젝트의 `modify_design_spec` add/update: LLM이 호출되며 결정 1·2에 따라 grid_plan이 자동 강제됨 → 별도 분기 불필요
- 기존 lint 동작(`grid-plan-required`는 imported의 `slide_type=="content"`에도 발동)은 그대로 유지. imported 슬라이드를 LLM으로 다시 처리하지 않는 한 위반이 나올 수 있으나, 사용자가 명시적으로 modify를 호출하면 자동 해결됨.

## Technical Details

### 영향 범위

- `src/ppt_generator/interfaces/llm_output_models.py`
  - `SlideSpecOutput` → `ContentSlideSpecOutput` + `SimpleSlideSpecOutput` 분리
  - 공통 필드는 `_BaseSlideSpecOutput` 등 baseclass로 추출
  - `to_dataclass()`는 baseclass에 두어 두 모델이 공유
- `src/ppt_generator/tools/design/service.py`
  - `_generate_with_structured_output()`에 `slide_type` 인자 추가
  - `generate_single_slide()`에서 slide_type 전달
- `src/ppt_generator/interfaces/prompts/design_user.prompt.md`
- `src/ppt_generator/interfaces/prompts/design_batch_user.prompt.md`
- 테스트
  - `SlideSpecOutput`을 import하는 테스트는 신규 모델로 갱신
  - content 슬라이드 LLM 응답이 grid_plan 누락 시 검증 예외가 발생하는 단위 테스트 추가

### 하위 호환성

- `PptxSlideSpec.grid_plan`은 `GridPlan | None` 유지 → imported PPTX 호환
- 기존 generated 프로젝트의 design_spec.json은 grid_plan 부재 시 lint가 잡고, 사용자가 수정하면 LLM 호출 시점에 자동 채워짐
- 외부에서 `SlideSpecOutput`을 import하는 사용자 코드는 없으므로(내부 모듈) 별칭 유지 불필요

### Acceptance Criteria

1. `slide_type=="content"`에서 LLM이 `grid_plan`을 누락하면 Pydantic validation이 실패한다 (스키마 레벨 강제 확인 단위 테스트).
2. `slide_type in ("title", "closing")`에서 `grid_plan` 부재가 정상 통과한다.
3. `generate_slides_design_spec`로 신규 생성 시 모든 content 슬라이드 spec에 grid_plan이 포함된다.
4. imported 프로젝트에서 `modify_design_spec(action="add" 또는 "update")`로 처리된 content 슬라이드 spec에 grid_plan이 포함된다.
5. import 직후 imported 프로젝트의 design_spec.json에는 grid_plan이 없을 수 있다(현 동작 유지).
6. 기존 lint/단위 테스트가 회귀하지 않는다.

### Out of Scope

- imported PPTX 시점에 자동으로 grid_plan을 추론해 채워주는 backfill (별도 ADR)
- service-level 재시도 로직 (Pydantic 강제로 충분)
- title/closing에도 grid_plan 강제 (ADR-0044 결정 2와 충돌)

## Consequences

긍정적:
- structured_output 검증으로 content 슬라이드 grid_plan 누락이 첫 시도부터 결정적으로 차단됨
- service-level 분기/재시도 코드 없이 스키마만으로 강제 → 코드 단순
- review 루프 부담 감소 (lint 통과율 상승 기대)

부정적/리스크:
- 두 응답 모델 유지 비용 — 공통 필드 변경 시 두 곳 갱신 필요(baseclass로 완화)
- LLM이 Required 필드 충족을 위해 빈 cells 등 형식상 valid한 누락을 낼 가능성 — `grid-plan-required` lint(regions/content_columns/cells 검사)가 잡음
- structured_output 프레임워크의 검증 실패 처리 동작에 의존 — 실패 시 예외 형태/재시도 여부는 strands의 동작을 따름

## References

- [ADR-0044: Grid-First Design Spec](./0044-grid-first-design-spec.md)
- [ADR-0033: Design Spec Post-Generation LLM Review](./0033-design-spec-post-generation-review.md)
- [ADR-0041: Validator를 Lint로 전환](./0041-validator-to-lint.md)
