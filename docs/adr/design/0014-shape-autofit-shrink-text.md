# PptxShape autofit 기본값을 "shrink_text" 로

Date: 2026-05-26 (split from ADR-0011 결정 14)

## Status

Accepted

## Context

PptxShape 의 `autofit_mode` 는 두 가지가 있다.

- `expand_height` — 텍스트가 길면 shape height 가 늘어남 (CSS `min-height` 로 렌더).
- `shrink_text` — height 는 고정, 폰트가 자동 축소되어 들어감.

기본값이 `expand_height` 였을 때 다음 패턴이 가장 흔한 디자인 회귀였다.

- 카드 그리드(여러 sibling shape 의 높이/폭이 동일해야 보기 좋은 레이아웃) 에서 한 카드의 텍스트가 길면 *그 카드만* 세로로 늘어남.
- 결과적으로 grid 균일성이 깨지고, 옆/아래 element 좌표가 어긋나 시각적 인지가 무너짐.
- LLM 은 매번 카드별로 `autofit_mode="shrink_text"` 를 명시해야 회귀를 막을 수 있는데, 이를 누락하는 빈도가 높았다.

`shrink_text` 가 기본이라면 LLM 이 명시 안 해도 카드 그리드가 자연스럽게 균일성을 유지하고, 폰트가 너무 작아지는 케이스는 별도 lint(font-range, 10~44pt) 가 잡아준다.

## Decision

`PptxShape.autofit_mode` 의 기본값을 `expand_height` → `shrink_text` 로 변경한다. ShapeOutput(LLM 응답 모델) 의 default 도 동일하게 정렬한다.

`expand_height` 는 *명시적으로* 필요한 경우(자유롭게 흐르는 텍스트 블록, 단일 callout) 에만 LLM 이 선택하도록 프롬프트에서 안내한다.

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

### Negative / Risks

- 폰트가 의도보다 많이 작아져 가독성이 떨어질 가능성 — `font-range` lint 가 10pt 미만은 잡지만 10~12pt 구간은 통과.
- 기존 generated 슬라이드 spec/json 의 autofit_mode 가 명시 출력되어 있어 영향 없음. 새로 생성되는 슬라이드만 default 적용.
- imported PPTX 슬라이드: import 단계에서 별도 autofit_mode 부여 안 함 → dataclass default 적용. 시각 출력에 회귀가 의심되면 import 단계에서 `expand_height` 를 명시 부여해 보존하는 옵션을 향후 검토 (현 ADR 범위 밖).

## References

- [ADR-0011: 5단 디자인 스펙 계층](./0011-five-layer-design-spec-hierarchy.md)
- [ADR-0002: 폰트 메트릭 기반 텍스트 오버플로우 방지](./0002-font-metric-text-overflow.md)
