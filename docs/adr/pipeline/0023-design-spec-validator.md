# 23. 디자인 스펙 Validator

Date: 2026-02-26

## Status

Accepted

## Context

LLM이 생성하는 PptxSlideSpec JSON은 좌표 오류, 폰트 크기 이상, 텍스트 오버플로우 등 렌더링 품질을 저하시키는 결함을 포함할 수 있다. 프롬프트만으로는 이를 완전히 방지할 수 없으므로, 디자인 스펙 파싱 직후 검증·보정하는 validator를 두어 안전망 역할을 한다.

관련 ADR:
- [ADR-0013](./0013-design-spec-pipeline.md): 디자인 스펙 파이프라인에서 validator의 위치
- [ADR-0017](./0017-font-metric-text-overflow-prevention.md): 폰트 메트릭 기반 텍스트 측정으로 validator 재구성
- [ADR-0021](./0021-slide-type-specific-system-prompts.md): 프롬프트 분리로 validator 보정 부담 경감
- [ADR-0022](./0022-title-slide-long-title-overflow-fix.md): title 슬라이드 height 확장 값 유지 개선

## Decision

`spec_utils/validator.py`의 `validate_slide_spec()`이 디자인 스펙을 검증·보정한다. 검증은 파싱 직후, 렌더링 직전에 수행된다.

### 검증 파이프라인

```
LLM 출력 JSON
  → parse_slide_spec()
  → validate_slide_spec()      ← Validator
    ├─ _validate_textboxes()
    ├─ _validate_shapes()
    ├─ _fix_content_title_position()        [content만]
    ├─ _fix_title_closing_main_position()   [title/closing만]
    └─ _center_content_vertically()         [content만]
  → 검증된 PptxSlideSpec
```

### 강제 보정 항목

#### 1. 폰트 크기 클램핑

| 대상 | 범위 | 비고 |
|---|---|---|
| 전체 textbox/shape | 10~44pt | `_clamp_font()` |
| title/closing 메인 텍스트 (첫 번째 textbox) | 40~44pt | `_fix_title_closing_main_position()` |

#### 2. 경계 여백 강제

| 대상 | 규칙 |
|---|---|
| 일반 요소 | left ≥ 64, top ≥ 64, right ≤ 1216, bottom ≤ 688 (좌우/상단 64px, 하단 32px) |
| 장식 요소 | 여백 무시, 캔버스 전체 범위(0~1280, 0~720) 허용 |

장식 요소 판별 (`_is_decorative_shape()`): 텍스트 없는 얇은 shape (height ≤ 10px 또는 width ≤ 10px)

#### 3. 빈 텍스트박스 제거

paragraphs의 모든 run에 텍스트가 없는 textbox를 삭제한다.

#### 4. 텍스트 오버플로우 방지 (autofit)

폰트 메트릭 기반으로 실제 줄바꿈 후 필요 높이를 계산한다 ([ADR-0017](./0017-font-metric-text-overflow-prevention.md)).

- **textbox**: height 부족 시 폰트를 비례 축소 (최소 10pt)
- **shape**: 먼저 height 확장 시도 → 캔버스 한계 초과 시 폰트 축소. padding을 차감하여 실제 텍스트 영역 기준으로 계산

#### 5. content 슬라이드 — 제목 위치 고정

첫 번째 textbox가 bold + 24pt 이상이면 제목으로 인식하여 고정 좌표로 보정한다.

| 속성 | 값 |
|---|---|
| left | 64 |
| top | 72 |
| width | 1152 |
| height | 48 |

#### 6. title/closing 슬라이드 — 메인 텍스트 위치 + 폰트 강제

첫 번째 textbox의 좌표를 프롬프트 명세에 맞게 고정하고, 폰트 크기를 최소 40pt로 강제한다.

| 속성 | title | closing |
|---|---|---|
| left | 64 | 64 |
| top | 260 | 240 |
| width | 1152 | 1152 |
| height | ≥ 80 (텍스트 줄바꿈에 맞게 확장된 값 유지) | ≥ 80 |
| 폰트 최소 | 40pt | 40pt |

#### 7. content 슬라이드 — 수직 중앙 정렬

`top ≥ 100`, `height ≥ 200`인 textbox에서 실제 콘텐츠가 height의 65% 미만이면 `vertical_alignment`을 `"top"` → `"middle"`로 변경한다.

### 설계 원칙

- **프롬프트 + validator 이중 방어**: 프롬프트가 1차 방어, validator가 2차 안전망
- **비파괴적 보정**: 원본 의도를 최대한 존중하되, 렌더링 결함만 수정
- **장식 요소 예외 처리**: 꾸밈용 얇은 라인은 일반 규칙에서 제외

## Consequences

### Positive

- LLM 출력의 좌표/폰트 오류를 자동 보정하여 렌더링 품질 보장
- 프롬프트 변경 없이도 일관된 레이아웃 규칙 강제 가능
- 텍스트 오버플로우를 폰트 메트릭 기반으로 정밀 방지

### Negative

- validator가 보정한 결과가 LLM의 원래 디자인 의도와 다를 수 있음 (예: autofit으로 폰트가 작아짐)
- 보정 규칙 추가 시 기존 슬라이드에 예기치 않은 영향 가능

## References

- `src/ppt_generator/interfaces/spec_utils/validator.py`
- `src/ppt_generator/interfaces/text_measurement.py`
- `src/ppt_generator/interfaces/constants.py` (검증 상수)
- `tests/test_spec_utils_validation.py`
