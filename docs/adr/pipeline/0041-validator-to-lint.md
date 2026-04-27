# ADR-0041: 디자인 스펙 Lint

Date: 2026-04-27

## Status

Accepted (Supersedes [ADR-0023](./0023-design-spec-validator.md))

## Context

LLM이 생성하는 PptxSlideSpec JSON은 폰트 크기 이상, 캔버스 경계 이탈 등 렌더링 품질을 저하시키는 결함을 포함할 수 있다. 프롬프트만으로는 이를 완전히 방지할 수 없으므로, 디자인 스펙 품질을 검증하는 안전망이 필요하다.

기존 validator(ADR-0023)는 결함을 **직접 보정**하는 방식이었다. 이 방식의 한계:

1. **전체 레이아웃 컨텍스트 부재**: 제목 폰트를 강제로 올리면 본문과의 비례 관계가 깨질 수 있다
2. **규칙 확장 어려움**: 요소 겹침, 색상 대비, 여백 균형 등 "감지는 쉽지만 기계적 수정은 위험한" 규칙을 추가하기 어렵다
3. **visual_qa와 패턴 불일치**: visual_qa는 "감지 → LLM 수정" 패턴인데, spec 레벨에서는 "감지 → 강제 수정" 패턴이라 불일치

관련 ADR:
- [ADR-0013](./0013-design-spec-pipeline.md): 디자인 스펙 파이프라인에서 lint의 위치
- [ADR-0017](./0017-font-metric-text-overflow-prevention.md): 폰트 메트릭 기반 텍스트 측정
- [ADR-0021](./0021-slide-type-specific-system-prompts.md): 프롬프트 분리로 보정 부담 경감
- [ADR-0026](./0026-visual-qa-pipeline.md): Visual QA 파이프라인

## Decision

### 역할: 위반 감지 + 리포트 (수정하지 않음)

`spec_utils/lint.py`의 `lint_slide_spec()` / `lint_design_spec()`이 디자인 스펙을 검증한다. **위반을 감지하여 리포트만 반환**하고, 강제 수정은 하지 않는다. 수정은 MCP 클라이언트(사용자)가 결정하여 LLM 프롬프트를 통해 수행한다.

### 모듈 구조

```
spec_utils/
├── lint.py              # 오케스트레이터 + clean (public API)
├── lint_types.py         # LintViolation, SlideLintResult, LintResult, is_decorative()
└── lint_rules/
    ├── __init__.py       # ALL_RULES 리스트 — 규칙 등록
    ├── title_font.py     # title-font-min
    ├── font_range.py     # font-range
    ├── canvas_overflow.py    # canvas-overflow
    ├── text_overflow.py      # text-overflow
    └── decorative_no_rounding.py  # decorative-no-rounding
```

- **lint.py**: `lint_slide_spec()`, `lint_design_spec()`, `clean_slide_spec()` public API. `ALL_RULES`를 순회하며 각 규칙 실행.
- **lint_types.py**: 데이터 클래스와 `is_decorative()` 등 규칙 간 공유 헬퍼.
- **lint_rules/**: 규칙당 1파일. 각 규칙은 `(spec, result) → None` 시그니처. 새 규칙 추가 시 파일 생성 후 `__init__.py`의 `ALL_RULES`에 등록.

### 기계적 정리 vs 디자인 lint

| 구분 | 예시 | 처리 방식 |
|---|---|---|
| **기계적 정리** | 빈 텍스트박스 제거 | `clean_slide_spec()`으로 자동 적용 |
| **디자인 lint** | 제목 폰트 최소 크기, 경계 이탈, 폰트 범위 | 위반 리포트만 반환, 수정은 사용자/LLM |

기계적 정리: LLM의 디자인 의도와 무관한 순수 데이터 정리. 빈 텍스트박스는 렌더링에 영향 없으므로 자동 제거.

### Lint 규칙

| 규칙 ID | severity | 조건 | 비고 |
|---|---|---|---|
| `title-font-min` | error | 제목 폰트 < 24pt (content) 또는 < 36pt (title/closing) | |
| `font-range` | warning | 폰트 < 10pt 또는 > 44pt | |
| `canvas-overflow` | warning | 요소가 캔버스(1280×720) 경계 밖 | 장식 요소 예외 |
| `text-overflow` | warning | 텍스트가 컨테이너 높이 초과 (15% 여유 허용) | 장식 요소 예외 |
| `decorative-no-rounding` | warning | 장식 요소에 `corner_radius_px > 0` 설정됨 | 꾸밈선은 직선이어야 함 |

장식 요소 판별: 텍스트 없는 얇은 shape (height ≤ 10px 또는 width ≤ 10px). 규칙은 점진적으로 추가한다.

### 파이프라인

디자인 스펙 생성/수정 후 lint를 실행하고, MCP 응답의 `lint` 필드에 위반 리포트를 JSON으로 포함한다. 위반이 없으면 `lint` 필드를 생략한다.

MCP 클라이언트는 lint 결과를 사용자에게 보여주고, 사용자가 수정 여부를 결정한다. 수정이 필요하면 `modify_design_spec(action="update")`로 해당 슬라이드를 재생성한다.

렌더링(HTML/PPTX) 시점에서는 `clean_slide_spec()`만 적용하고, lint는 실행하지 않는다.

### 레이아웃 비개입 원칙

Lint는 요소의 위치(좌표)를 직접 변경하지 않는다.

**Lint가 하지 않는 것:**
- 제목/메인 텍스트 위치 강제 이동
- 겹치는 요소를 밀어내는 push 로직
- vertical_alignment 강제 변경
- 텍스트-배경 색상 대비 보정
- 텍스트 shape 간 최소 간격 조정
- 폰트 크기 강제 변경 (클램핑, 축소 등)

**이유:** 전체 레이아웃 컨텍스트 없이 개별 요소를 수정하면 LLM이 계산한 좌표 밸런스를 깨트린다. 레이아웃 품질은 프롬프트의 constraint와 LLM의 전체 컨텍스트 이해에 의존한다.

### 설계 원칙

- **감지만, 수정은 하지 않는다**: lint는 ESLint처럼 위반을 리포트하고, 수정은 사용자/LLM이 전체 컨텍스트를 보고 수행
- **프롬프트가 레이아웃·색상, lint가 안전망**: 좌표/레이아웃/색상 결정은 프롬프트와 디자인 서머리가 담당하고, lint는 기계적으로 검증 가능한 항목만 감지
- **최소 개입**: 기계적 정리(빈 textbox 제거)만 자동 적용, 나머지는 리포트
- **장식 요소 예외 처리**: 꾸밈용 얇은 라인은 canvas-overflow 검사에서 제외

## Consequences

### Positive

- **규칙 확장 용이**: 감지만 구현하면 되므로 겹침, 대비, 여백 등 복잡한 규칙 추가 가능
- **visual_qa와 아키텍처 통일**: spec 레벨과 pixel 레벨 모두 "감지 → 리포트 → 사용자/LLM 수정" 패턴
- **LLM 디자인 의도 보존**: 기계적 보정이 타이포그래피 밸런스를 깨는 문제 해소
- **사용자 제어**: 수정 여부를 사용자가 결정하므로 불필요한 LLM 호출 방지

### Negative

- **자동 수정 없음**: 기존에는 제목 폰트가 자동으로 올라갔으나, 이제 사용자가 직접 수정 지시 필요
- **위반이 남을 수 있음**: 사용자가 lint 결과를 무시하면 위반이 그대로 렌더링됨
