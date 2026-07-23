# 타이틀 슬라이드 긴 제목 텍스트 잘림 수정

Date: 2026-02-25

## Status

Accepted (2026-02-25)

## Context

타이틀 슬라이드에서 제목이 길어 2줄로 줄바꿈될 때, HTML 미리보기에서 텍스트 상단이 잘리는 문제가 발생했다.

근본 원인은 세 가지가 복합적으로 작용:

1. **validator의 height 강제 리셋**: `_fix_title_closing_main_position()`이 `_validate_textboxes()` 이후에 호출되면서, 텍스트 줄바꿈에 맞게 확장된 height를 다시 80px로 강제 리셋 (validator 상세: [lint/0001](../lint/0001-design-spec-validator.md))
2. **HTML 렌더러의 CSS 조합**: `overflow:hidden` + `justify-content:center`가 80px 박스 안에서 2줄 텍스트(~94px)를 중앙 정렬하려 하면서 상단을 잘라냄
3. **프롬프트의 고정 height**: 대제목 height=80을 하드 제약으로 고정하여 LLM이 2줄 제목에 대응할 수 없음

PPTX 렌더링에서는 정상 표시되며, HTML 미리보기에서만 발생하는 문제였다.

## Decision

### 1. validator: height 확장 값 유지

`_fix_title_closing_main_position()`에서 height를 `max(target_height, tb.height_px)`로 설정하여, 검증 단계에서 텍스트 줄바꿈에 맞게 확장된 높이를 유지한다.

### 2. HTML 렌더러: textbox overflow 변경

`textbox_to_html()`에서 `overflow:hidden` → `overflow:visible`로 변경하여 텍스트가 박스를 넘어도 표시되도록 한다. HTML 미리보기는 시각적 확인 용도이므로 overflow:visible이 적합하다.

### 3. 프롬프트: 2줄 제목 대응

타이틀 슬라이드 프롬프트에서 대제목 height를 1줄(80) / 2줄(160) 조건부로 설정하도록 변경하고, 구분선과 부제목의 top도 함께 조정하도록 가이드를 추가했다.

## Consequences

### Positive

- 2줄 제목이 HTML 미리보기에서 잘리지 않고 정상 표시됨
- validator가 텍스트 측정 기반으로 확장한 높이를 title/closing 슬라이드에서도 유지
- LLM이 제목 길이에 따라 유연하게 레이아웃을 조정할 수 있음

### Negative

- textbox의 overflow:visible로 인해 의도치 않게 텍스트가 다른 요소와 겹칠 수 있음 (validator의 겹침 해소 로직으로 완화)

## References

- validator: `src/ppt_generator/interfaces/spec_utils/validator.py` — `_fix_title_closing_main_position`
- HTML 렌더러: `src/ppt_generator/tools/slides/html_renderer.py` — `textbox_to_html`
- 프롬프트: `src/ppt_generator/interfaces/prompts/design_system_title.prompt.md`
- 테스트: `tests/test_spec_utils_validation.py` — `TestTitleClosingMainPositionFix`
- 관련 ADR: [0017-font-metric-text-overflow-prevention](./0002-font-metric-text-overflow.md), [0023-design-spec-validator](../lint/0001-design-spec-validator.md)
