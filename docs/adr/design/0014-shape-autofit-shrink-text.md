# PptxShape autofit 기본값을 "shrink_text" 로

Date: 2026-05-26 (split from 0011 결정 14)
Updated: 2026-06-25 (HTML 렌더 경로의 shrink_text 미구현 결함 보정)
Updated: 2026-07-21 (line_spacing 미축소로 다행 텍스트 오버플로 지속되던 결함 보정)

## Status

Accepted (2026-05-26)

## Context

PptxShape 의 `autofit_mode` 는 두 가지가 있다.

- `expand_height` — 텍스트가 길면 shape height 가 늘어남 (CSS `min-height` 로 렌더).
- `shrink_text` — height 는 고정, 폰트가 자동 축소되어 들어감.

기본값이 `expand_height` 였을 때 다음 패턴이 가장 흔한 디자인 회귀였다.

- 카드 그리드(여러 sibling shape 의 높이/폭이 동일해야 보기 좋은 레이아웃) 에서 한 카드의 텍스트가 길면 *그 카드만* 세로로 늘어남.
- 결과적으로 grid 균일성이 깨지고, 옆/아래 element 좌표가 어긋나 시각적 인지가 무너짐.
- LLM 은 매번 카드별로 `autofit_mode="shrink_text"` 를 명시해야 회귀를 막을 수 있는데, 이를 누락하는 빈도가 높았다.

`shrink_text` 가 기본이라면 LLM 이 명시 안 해도 카드 그리드가 자연스럽게 균일성을 유지하고, 폰트가 너무 작아지는 케이스는 별도 lint(font-range, 10~44pt) 가 잡아준다.

### 후속 결함: HTML 렌더 경로에 shrink 가 없었다 (2026-06-25)

이 ADR 은 "shrink_text → 폰트가 자동 축소되어 시각적 잘림이 없다" 를 전제로 lint 의 height overflow 검사까지 스킵하게 했다. 그러나 그 전제는 **PPTX 출력에서만** 성립했다. PPTX 는 PowerPoint 자체 autofit 으로 폰트를 줄여 채우지만, **HTML 렌더 경로에는 축소가 구현돼 있지 않았다** — `expand_height` 만 분기 처리되고 `shrink_text` 는 spec 의 폰트 크기를 그대로 출력한 뒤 컨테이너를 overflow 숨김 처리하므로, 텍스트가 박스를 넘으면 그대로 잘렸다.

게다가 lint 가 "shrink 면 안 잘린다" 는 전제로 height 검사를 스킵했기 때문에, 이 잘림은 경고 한 줄 없이 통과되어 결함을 가렸다. 폰트 축소 비율을 계산하는 측정 유틸은 이미 존재했지만 렌더 경로에서 호출되지 않는 죽은 코드였다.

### 후속 결함: line_spacing 이 축소되지 않아 다행 텍스트가 여전히 넘쳤다 (2026-07-21)

shrink 비율(font_scale)이 폰트 크기에만 적용되고, 명시적 `line_spacing_pt`(절대 pt) 에는 적용되지 않았다. 줄 높이가 line_spacing 으로 고정되면 폰트를 아무리 줄여도 소비 높이(줄 수 × 줄 높이)가 그대로라서, 줄 수가 많은 요소(코드 블록 등)에서 autofit 이 오버플로를 해소하지 못했다. 축소 비율 산출식은 "필요 높이 = 줄 수 × line_spacing 기반 줄 높이" 로 계산하는데, 그 줄 높이가 scale 과 무관하게 상수였으므로, 반환된 scale 로 폰트를 줄여도 실제 required 높이가 변하지 않는 자기모순이었다. HTML 은 `overflow:hidden` 으로 넘친 줄이 가려져 결함이 숨었고, PPTX 는 클리핑이 없어 텍스트가 박스 아래로 그대로 흘러넘쳐 결함이 드러났다.

## Decision

`PptxShape.autofit_mode` 의 기본값을 `expand_height` → `shrink_text` 로 변경한다. ShapeOutput(LLM 응답 모델) 의 default 도 동일하게 정렬한다.

`expand_height` 는 *명시적으로* 필요한 경우(자유롭게 흐르는 텍스트 블록, 단일 callout) 에만 LLM 이 선택하도록 프롬프트에서 안내한다.

### HTML 렌더의 shrink 구현 (2026-06-25 추가)

HTML 렌더 시 `shrink_text` 요소는 측정한 필요 높이가 가용 높이를 초과하면 폰트를 비율만큼 축소해 출력한다. 축소 비율은 이미 존재하던 폰트 스케일 산출 로직(하한 10pt / 상한 44pt 비율)을 재사용해, PPTX autofit 및 lint 의 height-skip 전제와 결과를 일치시킨다. 동일 원리를 textbox(헤더·푸터 포함) 에도 적용해 제목·하단 텍스트가 셀 높이를 넘쳐 잘리던 케이스를 함께 해소한다. 즉 "shrink_text 면 잘리지 않는다" 는 전제를 모든 출력 경로에서 비로소 참으로 만든다.

### shrink 시 line_spacing 도 함께 축소 (2026-07-21 추가)

`shrink_text` 로 폰트를 비율 축소할 때, 명시적 `line_spacing_pt` 도 같은 비율로 축소해 출력한다(HTML·PPTX 두 경로 공통). 줄 높이가 폰트와 함께 줄어야 소비 높이가 실제로 감소해 autofit 이 오버플로를 해소한다. 산출식 자기모순(줄 높이가 scale 불변이라 required 높이가 변하지 않던 문제) 은, 필요 높이 계산과 실제 출력 양쪽이 동일하게 "축소된 줄 높이" 를 쓰게 하여 제거한다. 축소 하한(폰트 절대 10pt) 은 유지 — 하한에서도 넘치는 극단 입력은 `font-range`/`text-overflow` lint 가 경고한다.

### 축소 목표는 실제 박스(1.0), lint 경고 tolerance(1.15) 와 분리 (2026-07-21 추가)

축소 비율을 lint 의 경고 tolerance(박스 × 1.15) 에 맞춰 산출하던 것이, 박스보다 15% 큰 높이까지 "맞음" 으로 판정해 그만큼 텍스트를 박스 밖으로 새게 했다. PPTX 는 도형 클리핑이 없어 이 초과분이 하단 테두리 밖으로 그대로 삐져나온다(HTML 은 overflow:hidden 으로 가려질 뿐). 두 tolerance 를 분리한다 — **축소 목표는 실제 박스(1.0)** 로 두어 넘침이 없게 하고, **lint 경고 tolerance(1.15)** 는 폰트 메트릭 추정 오차를 흡수하는 용도로만 유지한다.

### lint 는 "축소 후에도 남는" 넘침을 검사 (2026-07-21 추가)

`text-overflow` 가 `shrink_text` shape 의 height 검사를 통째로 스킵하던 것을, "폰트 최소 축소(10pt) 를 적용한 뒤" 의 잔여 높이로 검사하도록 바꾼다. shrink 로 해소 가능한 넘침은 여전히 경고하지 않지만(자동 축소로 실제로 들어감), 하한(10pt)에서도 안 들어가는 잔여 넘침은 PPTX 에서 삐져나오므로 경고한다. 이 경고는 자동 수정하지 않고 사용자에게 해결 방법(텍스트 축약 / 박스 확대 / 슬라이드 분할)을 확인받는다 — 레이아웃이 깨지는 결함은 콘텐츠 판단이 필요하기 때문이다.

### Lint 영향

- `text-overflow` rule 은 `shrink_text` shape 에서 height-based overflow 검사를 *스킵* — 폰트 자동 축소로 시각적 잘림이 없으므로 false positive. width-based 단어 overflow 검사(`text-width-overflow`) 는 유지 (단일 단어가 카드 폭보다 길면 shrink 도 살리지 못하는 케이스).
- `expand-height-collision` rule 은 `expand_height` shape 에 한정된 검사이므로 default 변경이 false positive 를 만들지 않는다.
- 폰트가 너무 작아져 가독성이 떨어지는 케이스는 `font-range` lint(10~44pt) 가 차단한다 — shrink 결과로 10pt 미만이 되면 warning. 이 안전망 덕에 default 변경의 위험이 작다.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| `expand_height` 기본값 유지 + 프롬프트로 카드 그리드에선 shrink_text 사용 안내 | LLM 이 자주 누락 — 카드 그리드가 회귀의 가장 흔한 패턴 |
| 기본값 없이 LLM 이 항상 명시하도록 schema Required 로 강제 | LLM 토큰 부담만 늘고 효과는 같음 (default 가 자연스러움) |
| 새 카드 그리드 전용 wrap 모드 도입 | autofit_mode 가 이미 두 개 — 불필요한 복잡도 |

## Consequences

### Positive

- 카드 그리드 회귀가 *기본값* 차원에서 차단됨 — LLM 이 명시 안 해도 안전.
- text-overflow 노이즈 warning 감소 (shrink_text shape 검사 스킵).
- "텍스트 잘림" 이라는 큰 시각 결함 대신 "폰트 약간 작아짐" 이라는 작은 trade-off 로 부작용이 옮겨감.
- HTML 과 PPTX 의 shrink 동작이 일치하게 되어, lint 의 height-skip 전제가 비로소 실제 출력과 부합한다 (전제와 구현의 괴리 제거).
- 헤더/푸터 textbox 의 폰트가 셀 높이에 맞춰 자동 축소되어, 제목·하단 안내 텍스트 잘림이 사라진다.

### Negative / Risks

- 폰트가 의도보다 많이 작아져 가독성이 떨어질 가능성 — `font-range` lint 가 10pt 미만은 잡지만 10~12pt 구간은 통과.
- HTML shrink 는 폰트 메트릭 *추정* 기반 높이 측정에 의존하므로, 브라우저 실제 렌더와 미세한 오차가 있을 수 있다. 축소 비율에 하한(10pt/44pt)이 있어 극단적으로 긴 텍스트는 여전히 넘칠 수 있으며, 그 경우는 `font-range` lint 가 별도 경고한다.
- 기존 generated 슬라이드 spec/json 의 autofit_mode 가 명시 출력되어 있어 영향 없음. 새로 생성되는 슬라이드만 default 적용.
- imported PPTX 슬라이드: import 단계에서 별도 autofit_mode 부여 안 함 → dataclass default 적용. 시각 출력에 회귀가 의심되면 import 단계에서 `expand_height` 를 명시 부여해 보존하는 옵션을 향후 검토 (현 ADR 범위 밖).

## References

- [0011: 5단 디자인 스펙 계층](./0011-five-layer-design-spec-hierarchy.md)
- [0002: 폰트 메트릭 기반 텍스트 오버플로우 방지](./0002-font-metric-text-overflow.md)
