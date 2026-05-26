# 47. nowrap 오버플로우 방지 — tolerance 보수화 + lint 추가

Date: 2026-05-25

## Status

Accepted (verified 2026-05-26: nowrap_overflow lint rule + TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO 정착)

## Context

ADR-0017에서 도입된 `should_apply_nowrap_to_paragraph`는 PPT↔브라우저 폰트 메트릭 차이로 인한 wrap 회귀를 막기 위해 paragraph가 박스 폭에 "거의 맞을 때" `white-space:nowrap`을 적용한다. 판정 식은:

```python
total_width <= available_width_px * TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO
```

현재 `TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO = 1.15`이다. 즉 추정 폭이 박스 가용 폭의 **1.15배까지 nowrap을 강제 적용**한다. 이는 PPT 메트릭이 브라우저 메트릭보다 작게 측정되는 경우(글자가 실제로는 더 넓게 그려지는 경우)를 흡수하기 위한 안전 마진이었다.

### 발견된 문제

37페이지 "Skills & MCP" 카드(width=268px, padding=12+12, usable=244px)의 본문 "스킬로 작업 실행·결과 자가 개선" (14자, 한글):

- 추정 폭: `14 × 14pt × 1.333 × 0.9 ≈ 235px`
- nowrap 게이트: `235 ≤ 244 × 1.15 = 281` → **True → nowrap 강제**
- 브라우저 실제 렌더 폭: ~270px (박스 244를 초과)
- 결과: 한 줄 강제 + 박스 좌우로 글자가 **튀어나감**

shape의 `expand_height` 모드는 `min-height` + `overflow:visible`이라 height만 늘어나고 width는 고정이므로, 좌우 오버플로우를 막지 못한다. shape `overflow:hidden` 모드라도 잘림이 발생할 뿐 근본 해결은 아니다.

핵심 모순:
- **wrap 회귀 방지** (ADR-0017): tolerance를 크게 → nowrap 자주 적용
- **좌우 오버플로우 방지** (이 ADR): tolerance를 작게 → nowrap을 안전한 경우에만 적용

1.15는 wrap 회귀 방지에 치우친 값이며, 좌우 오버플로우라는 더 치명적인 시각 버그를 유발한다. **"한 줄짜리 라벨이 두 줄로 풀린 경우"보다 "글자가 박스를 뚫고 나간 경우"가 훨씬 눈에 띄고 신뢰도를 깎는다.**

## Decision

두 가지 변경을 함께 적용한다.

### A. tolerance_ratio 보수화: 1.15 → 0.95

`TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO`를 `0.95`로 낮춘다. 추정 폭이 박스 가용 폭의 **95% 이하일 때만** nowrap을 적용하여, 어떤 메트릭 차이가 발생해도 박스를 뚫지 않도록 한다.

> **운영 노트**: 메트릭 차이로 짧은 라벨(예: 토큰 박스 `_ with`)이 wrap 되는 케이스가 드물게 발생할 수 있다. 이는 tolerance 를 더 키우는 대신 **spec 단계에서 해당 박스 폭을 살짝 키워 해결**한다 (정확도 게임 회피). 1.05 같은 중간값은 두 부작용 모두 못 막을 수 있어 채택하지 않았다.

### B. lint 규칙 신설: `nowrap-overflow`

새 lint 규칙 `check_nowrap_overflow`를 `lint_rules/`에 추가한다. shape/textbox의 paragraph마다 `should_apply_nowrap_to_paragraph` 결과를 시뮬레이션하고, nowrap이 적용될 paragraph의 추정 폭이 가용 폭을 초과하면 warning을 발행한다. 이는 향후 tolerance가 다시 느슨해지거나 다른 경로로 nowrap이 적용되는 경우의 회귀를 사전에 잡는 사후 검증이다.

### Technical Details

#### 1. 상수 변경 (`interfaces/constants.py`)

```python
# AS-IS
TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO = 1.15
# TO-BE
TEXT_MEASURE_NOWRAP_TOLERANCE_RATIO = 0.95
```

근거: 폭 추정 함수가 한글 0.9, Latin 0.55의 보수적 비율을 사용하므로, 추정값이 실제값보다 작게 나올 가능성이 있다. 이 갭을 1.15로 보정하면 박스를 뚫는 부작용이 발생한다. 0.95는 추정 정확도를 유지하면서 박스 폭의 5% 안전 마진을 남기는 값이다. 짧은 라벨이 wrap 되는 케이스는 spec 단계에서 박스 폭을 키워 처리한다 (양쪽 모두 만족하는 tolerance 는 존재하지 않음).

#### 2. 새 lint 규칙 (`lint_rules/nowrap_overflow.py`)

```python
def check_nowrap_overflow(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    """nowrap이 적용될 paragraph의 추정 폭이 가용 폭을 초과하는지 검사."""
    for idx, tb in enumerate(spec.textboxes):
        _check_container_nowrap(
            paragraphs=tb.paragraphs,
            width_px=tb.width_px,
            padding_left=tb.padding_left_px,
            padding_right=tb.padding_right_px,
            element_index=idx,
            element_type="textbox",
            result=result,
        )
    for idx, shape in enumerate(spec.shapes):
        if shape.shape_type == "line":
            continue
        _check_container_nowrap(
            paragraphs=shape.paragraphs,
            width_px=abs(shape.width_px),
            padding_left=shape.padding_left_px,
            padding_right=shape.padding_right_px,
            element_index=idx,
            element_type="shape",
            result=result,
        )
```

내부 헬퍼는 `should_apply_nowrap_to_paragraph`로 nowrap 판정을 그대로 재현하고, 판정이 True인 경우 `estimate_text_width_px` 합산값과 가용 폭을 직접 비교해 초과 시 violation을 추가한다.

```python
LintViolation(
    rule="nowrap-overflow",
    severity="warning",
    message=(
        f"{element_type}[{idx}] paragraph[{p_idx}] 가 nowrap 으로 렌더되지만 "
        f"추정 폭({total_width:.0f}px) 이 가용 폭({usable:.0f}px) 을 초과 — "
        f"브라우저에서 박스 좌우로 텍스트가 넘칠 수 있음"
    ),
    ...
)
```

bullet(`<li>`)에는 nowrap이 적용되지 않으므로(ADR-0017 §4) `bullet_level >= 0` paragraph는 검사 대상에서 제외한다.

#### 3. ALL_RULES 등록 (`lint_rules/__init__.py`)

```python
from ppt_generator.interfaces.spec_utils.lint_rules.nowrap_overflow import (
    check_nowrap_overflow,
)
ALL_RULES = [
    ...,
    check_nowrap_overflow,
]
```

#### 4. 테스트 (`tests/test_spec_utils_lint.py`)

기존 테스트 헬퍼 `_tb()`, `_slide()` 패턴을 따라 다음 케이스를 추가:

| 케이스 | 기대 결과 |
|---|---|
| 짧은 한글 텍스트가 박스 폭 50% (nowrap 적용, 가용 폭 이내) | pass |
| 긴 한글 텍스트가 박스 폭 110% (nowrap 미적용, paragraph wrap) | pass |
| 박스 폭의 95~100% 범위 한글 텍스트 (nowrap 미적용 기대) | pass |
| 박스 폭 추정 100% 추정값(이전 1.15 tolerance 회귀 시나리오) | nowrap 미적용으로 pass |
| 명시적 nowrap을 우회하기 위한 강제 시나리오는 검사하지 않음 | — |

폰트 메트릭 회귀를 직접 재현할 수는 없으므로(브라우저 환경 필요), 테스트는 추정 폭과 nowrap 게이트 동작 자체를 단위 검증한다.

## Consequences

### Positive
- 37페이지 같은 좌우 오버플로우 시각 버그가 사라진다.
- nowrap-overflow lint로 향후 tolerance가 다시 느슨해지거나, 다른 경로로 nowrap이 적용되는 경우의 회귀를 사전에 잡는다.
- 추정 정확도 자체에 안전 마진(5%)이 명시적으로 남아 가독성/안정성이 향상된다.

### Negative / Trade-offs
- 박스 폭 95~115% 구간의 paragraph는 이제 wrap된다. PPT에서는 한 줄, 브라우저에서는 두 줄로 보일 수 있다.
  - 완화: 이 구간은 LLM이 의도한 한 줄 라벨일 가능성이 낮고, 두 줄로 풀려도 박스가 `expand_height`로 늘어나 콘텐츠 자체는 보존된다.
  - 좌우 오버플로우(글자가 박스 밖으로 튀어나감)와 비교하면 시각적 충격이 훨씬 작다.
- 다이어그램 노드 라벨처럼 한 줄을 강하게 원하는 경우 LLM이 박스 폭을 더 넉넉히 잡거나 폰트를 줄이는 식으로 자율 조정해야 한다. 프롬프트에 명시하지 않는다 — 측정 함수의 보수성으로 자연 수렴하는 쪽이 단순하다.

### 마이그레이션
- 기존 디자인 스펙 호환성 영향 없음 (렌더링 동작만 바뀜).
- 기존 프로젝트의 `slides/*.html`은 다음 export_html 호출 시 자동 갱신.
- 새 lint 규칙은 `severity=warning`이므로 generation/modification을 차단하지 않는다.
