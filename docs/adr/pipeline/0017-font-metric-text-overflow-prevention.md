# 17. 폰트 메트릭 기반 텍스트 오버플로우 방지

Date: 2026-02-14

## Status

Accepted

## Context

LLM이 생성한 디자인 스펙에서 텍스트가 박스보다 커서 넘치는 문제가 빈번하게 발생한다.

근본 원인은 기존 `spec_utils.py`의 높이 검증이 **paragraph 개수**만 세고, 텍스트가 박스 너비 안에서 **몇 줄로 줄바꿈되는지** 계산하지 않기 때문이다.

```
기존: min_height = num_paragraphs × max_font × 2.0  (줄바꿈 무시)
변경: min_height = actual_wrapped_lines × line_height  (줄바꿈 계산)
```

특히 한글 텍스트의 경우 Latin 문자보다 글자당 폭이 ~1.6배 넓기 때문에, 동일 글자 수라도 줄바꿈이 훨씬 많이 발생하여 오버플로우가 자주 일어났다.

## Decision

**폰트 메트릭 기반 텍스트 크기 추정 모듈**(`text_measurement.py`)을 신규 도입하고, `spec_utils.py`의 검증 로직을 재작성하여 실제 줄바꿈을 반영한 높이 검증과 auto-fit 폰트 축소를 적용한다.

### Technical Details

#### 1. 텍스트 측정 모듈 (`interfaces/text_measurement.py`)

외부 의존성 없이 순수 함수로 구현. `unicodedata.east_asian_width()`로 CJK/전각 문자를 판별하여 글자별 폭을 다르게 추정한다.

| 함수 | 설명 |
|------|------|
| `_is_wide_char(ch)` | CJK/전각 문자 판별 (W, F) |
| `estimate_text_width_px(text, font_size_pt, is_monospace)` | 글자별 폭 추정 합산 |
| `estimate_paragraph_wrapped_lines(paragraph, available_width_px)` | run별 폭 합산 후 줄바꿈 수 계산 |
| `calculate_required_height(paragraphs, box_width_px, ...)` | 전체 필요 높이 산출 |
| `calculate_required_height_simple_text(text, font_size_pt, ...)` | `shape.text` 전용 높이 산출 |
| `calculate_autofit_font_scale(required_h, available_h, ...)` | 폰트 축소 비율 계산 |

글자 폭 추정 비율:

| 문자 유형 | 비율 | 계산 |
|-----------|------|------|
| CJK/한글 | 0.9 | `font_size_pt × 1.333 × 0.9` |
| Latin/숫자 | 0.55 | `font_size_pt × 1.333 × 0.55` |
| Monospace | 0.6 | `font_size_pt × 1.333 × 0.6` |

#### 2. 텍스트 측정 상수 (`interfaces/constants.py`)

```python
TEXT_MEASURE_PX_PER_PT = 1.333
TEXT_MEASURE_CJK_WIDTH_RATIO = 0.9
TEXT_MEASURE_LATIN_WIDTH_RATIO = 0.55
TEXT_MEASURE_MONOSPACE_WIDTH_RATIO = 0.6
TEXT_MEASURE_BULLET_INDENT_L0_PX = 24.0
TEXT_MEASURE_BULLET_INDENT_L1_PX = 48.0
TEXT_MEASURE_DEFAULT_SHAPE_PADDING_LR_PX = 4.8
TEXT_MEASURE_DEFAULT_SHAPE_PADDING_TB_PX = 2.4
```

#### 3. 검증 로직 재작성 (`interfaces/spec_utils.py`)

**`_validate_textboxes` 변경:**
- 기존 `num_lines × max_font × lh_factor` → `calculate_required_height()` 호출
- 높이 부족 시: 먼저 박스 확장 시도 → 캔버스 경계 초과 시 `_apply_font_scale()`로 폰트 축소

**`_validate_shapes` 변경:**
- padding을 해석하여 `calculate_required_height()`에 전달
- `shape.text` (단순 텍스트): `calculate_required_height_simple_text()` 사용
- `shape.paragraphs` (구조화 텍스트): `calculate_required_height()` 사용
- 동일한 확장 → 축소 전략 적용

**`_apply_font_scale(paragraphs, scale, font_min)` 신규 헬퍼:**
- `dataclasses.replace()`로 모든 run의 `font_size_pt`를 `int(pt × scale)` 적용
- `font_min` (기본 10pt) 이하로는 축소하지 않음

#### 4. 프롬프트 강화 (`interfaces/prompts/design_prompts.py`)

하드 제약 조건 앞에 텍스트 크기 추정 가이드 섹션 추가:
- 한글 1글자 ≈ `font_size_pt × 1.2px`, Latin 1글자 ≈ `font_size_pt × 0.73px`
- 예시: `width_px=500`, `font_size_pt=18`, 한글 → 한 줄 ~23글자
- shape padding 차감 필수 안내
- 하드 제약 #3 강화: "실제 줄바꿈 포함 줄수" 명시

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. 프롬프트만 강화 | LLM에게 줄바꿈 계산을 더 정확히 하라고 지시 | LLM의 수학 계산 정확도 한계, 탈락 |
| B. 고정 줄당 최대 글자 수 | 한국어 20자, 영어 40자 등 고정 규칙 | 폰트 크기/박스 폭 조합 반영 불가, 탈락 |
| **C. 폰트 메트릭 기반 측정 + auto-fit** | 글자별 폭 추정 → 줄바꿈 계산 → 높이 확장/폰트 축소 | **채택** |

### Acceptance Criteria

1. 긴 한글 텍스트가 포함된 textbox에서 줄바꿈을 반영한 높이 확장이 적용된다
2. padding이 있는 shape에서 padding을 차감한 실제 텍스트 영역 폭으로 줄바꿈을 계산한다
3. 캔버스 하단 가까이에서 확장 불가능 시 폰트 축소가 적용된다
4. 폰트 축소 시 최소 폰트 크기(10pt) 이하로 내려가지 않는다
5. 장식용 shape(텍스트 없음, height ≤ 10px)는 텍스트 기반 확장이 적용되지 않는다
6. 기존 테스트가 모두 통과한다

### Out of Scope

- 실제 폰트 파일 로드를 통한 정밀 폰트 메트릭 (OS/환경 의존성 발생)
- 자동 줄바꿈 위치의 정밀 시뮬레이션 (단어 단위 줄바꿈 등)
- 렌더링 후 시각적 검증 자동화

## Consequences

### Positive

- **텍스트 오버플로우 감소**: 실제 줄바꿈을 반영한 높이 계산으로 대부분의 오버플로우 사전 방지
- **CJK 텍스트 지원 강화**: 한글/일본어/중국어의 넓은 글자 폭을 정확히 반영
- **자동 복구**: 높이 확장 → 폰트 축소의 2단계 전략으로 캔버스 제한 내에서 최적 해 도출
- **외부 의존성 없음**: `unicodedata` 표준 라이브러리만 사용하여 모든 환경에서 동작
- **LLM 부담 감소**: 프롬프트 가이드 + 후처리 검증의 이중 안전장치로 LLM의 정밀 계산 부담 완화

### Negative

- 폰트 메트릭이 추정치이므로 실제 렌더링과 차이가 발생할 수 있음 (보수적 추정으로 완화)
- 높이 확장이 다른 요소와의 겹침을 유발할 수 있음 (캔버스 경계 클리핑으로 완화)
- auto-fit 폰트 축소 시 디자인 일관성이 떨어질 수 있음

## References

- 텍스트 측정 모듈: `src/ppt_generator/interfaces/text_measurement.py`
- 상수: `src/ppt_generator/interfaces/constants.py` — `TEXT_MEASURE_*` 상수
- 검증 유틸리티: `src/ppt_generator/interfaces/spec_utils.py` — `_validate_textboxes`, `_validate_shapes`, `_apply_font_scale`
- 프롬프트: `src/ppt_generator/interfaces/prompts/design_prompts.py` — 텍스트 크기 추정 가이드
- 테스트: `tests/test_text_measurement.py`, `tests/test_spec_utils_validation.py`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md)
