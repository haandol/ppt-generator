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
    └─ _validate_shapes()
  → 검증된 PptxSlideSpec
```

### 강제 보정 항목

#### 1. 폰트 크기 클램핑

| 대상 | 범위 | 비고 |
|---|---|---|
| 전체 textbox/shape | 10~44pt | `_clamp_font()` |

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

**autofit 비활성화 (`autofit=False`):**

임포트된 PPTX처럼 원본에서 레이아웃이 이미 확정된 경우, autofit 로직이 텍스트 크기를 과도하게 축소할 수 있다. `line_spacing_pt`가 `None`이면 줄 높이를 `font_size × 2.0`으로 과대 추정하여 불필요한 폰트 스케일링이 발생하기 때문이다.

이를 방지하기 위해 `validate_slide_spec(spec, autofit=False)`로 호출하면 폰트 스케일링(높이 계산 → 폰트 축소)을 완전히 스킵한다. 폰트 클램핑, 경계 여백 강제, 빈 텍스트박스 제거는 autofit과 무관하게 항상 적용된다.

| 호출 경로 | autofit |
|---|---|
| LLM 생성 디자인 스펙 (generate_slides_design_spec) | `True` (기본값) |
| PPTX 임포트 (import_pptx) | `False` |
| 임포트된 프로젝트의 PPTX 내보내기 (export_pptx) | `False` (metadata `steps_completed`에 `"import"` 키 존재 시) |

### 레이아웃 비개입 원칙

Validator는 요소의 위치(좌표)를 직접 변경하지 않는다. 레이아웃 관련 규칙은 프롬프트와 예제로 가이드한다.

**Validator가 하지 않는 것:**
- 제목/메인 텍스트 위치 강제 이동
- 겹치는 요소를 밀어내는 push 로직
- vertical_alignment 강제 변경
- 텍스트-배경 색상 대비 보정 (디자인 서머리의 테마/색상 팔레트를 프롬프트에서 지정하여 LLM이 올바른 색상을 출력하도록 가이드)
- 텍스트 shape 간 최소 간격 조정 (프롬프트의 constraint와 pre-output overlap verification으로 가이드)

**이유:** Validator는 전체 레이아웃 컨텍스트 없이 개별 요소만 보정하므로, 위치를 이동하면 LLM이 전체적으로 계산한 좌표 밸런스를 깨트린다. 예를 들어 제목 위치를 고정한 후 바로 아래 요소만 밀어내면, 그 아래 요소들은 원래 위치에 남아 연쇄적 겹침이 발생한다.

레이아웃 품질은 프롬프트의 constraint, 예제, pre-output overlap verification 절차를 통해 LLM이 올바른 좌표를 출력하도록 1차적으로 보장한다.

### 설계 원칙

- **프롬프트가 레이아웃·색상, validator가 안전망**: 좌표/레이아웃/색상 결정은 프롬프트와 디자인 서머리가 담당하고, validator는 기계적으로 검증 가능한 항목(폰트 범위, 캔버스 경계, 텍스트 오버플로우)만 보정
- **최소 개입**: 원본 의도를 최대한 존중하고, LLM이 출력한 색상·간격을 강제로 변경하지 않음
- **비파괴적 보정**: 렌더링 결함만 수정하되, 시각 디자인 요소(색상, 간격)는 수정하지 않음
- **장식 요소 예외 처리**: 꾸밈용 얇은 라인은 일반 규칙에서 제외

## Consequences

### Positive

- LLM 출력의 폰트/경계 오류를 자동 보정하여 렌더링 품질 보장
- 텍스트 오버플로우를 폰트 메트릭 기반으로 정밀 방지
- 레이아웃에 개입하지 않아 LLM의 디자인 의도를 훼손하지 않음

### Negative

- LLM이 프롬프트를 따르지 않을 경우 제목 위치나 수직 정렬이 비표준일 수 있음 (프롬프트 품질에 의존)
- autofit으로 폰트가 축소되면 LLM의 원래 타이포그래피 의도와 다를 수 있음

## References

- `src/ppt_generator/interfaces/spec_utils/validator.py`
- `src/ppt_generator/interfaces/text_measurement.py`
- `src/ppt_generator/interfaces/constants.py` (검증 상수)
- `tests/test_spec_utils_validation.py`
