# 5단 디자인 스펙 계층 — 데이터 무결성

Date: 2026-05-26 (split from 0011 결정 7/8/11)

## Status

Accepted

## Context

0011 가 5단 계층(Project / Slide / Layout / Section / Content) 을 정의하고도, *정의* 만으로는 안전망이 없다. 파이프라인이 슬라이드를 LLM 출력 → parse → lint/clean → save → load → render → modify 순으로 옮길 때 어느 한 곳에서 Layout/Section 메타가 떨어져 나가면 5단 계층의 가치(부분 수정 식별성, 구조적 충돌 차단) 가 그 시점부터 깨진다.

실제로 다음 회귀가 이미 한 번 발견됐다.

- "정리" 함수(`clean_slide_spec`) 가 dataclass 를 명시 생성하면서 design_doc / images 등을 누락. 새 필드가 추가될 때마다 사람이 손으로 인자를 추가해야 했고 한 차례 빠뜨림.
- modify_component(modify/0003) 가 LLM 응답으로 element 를 통째 교체할 때, LLM schema 에 *포함되지 않는* 비-design 메타 필드(z_index 등) 가 새 element 에서 누락되어 렌더 순서가 흔들림.
- lint rule 이 새로 추가됐는데 `RULE_LAYER_MAP` 등록이 누락되어 `"content"` default 로 fallback. layer 별 단계적 검증이 잘못된 layer 에서 일어남.

세 케이스 모두 0011 의 결정에는 모순되지 않지만 *실행 차원에서* 결정이 깨진다. 본 ADR 은 데이터 무결성 약속을 명시 결정으로 분리해 강제한다.

## Decision

### 결정 1 — 모든 PptxSlideSpec 재구성 지점은 5단 계층 필드를 보존한다

PptxSlideSpec 을 새로 만드는 모든 코드 경로는 다음 필드를 명시적으로 채워야 한다:

- slide_type (Slide layer 의 분류 키)
- grid_plan (Layout layer)
- design_doc (Section layer)
- images (Content layer 의 일부 — 파이프라인 단계에서 누락되면 시각 회귀)
- background_image_bytes / background_image_src (rendering side data)

특히 "정리" 의도가 있는 함수(`clean_slide_spec` 같은) 는 *정리 의도가 있는 필드* 만 변경하고 나머지는 무손실로 통과시켜야 한다. dataclass 의 `replace()` 를 사용하면 새 필드가 추가되어도 자동으로 보존된다 — 명시 생성 패턴은 신규 필드 누락 위험을 영구적으로 만든다.

### 결정 2 — lint rule 은 RULE_LAYER_MAP 에 전수 분류한다

`lint_types.RULE_LAYER_MAP` 는 *모든* lint rule 을 5단 계층 중 하나로 분류한다. 명시 안 된 rule 이 default `"content"` 로 fallback 되는 동작은 유지하되, 신규/기존 규칙 모두 명시적으로 매핑한다. 분류 가이드:

| layer | 검사 대상 |
|---|---|
| `layout` | grid_plan(regions/columns/rows/cells) |
| `section` | design_doc.layout 트리/bbox |
| `content` | 단일 textbox/shape 의 텍스트·픽셀·스타일 |
| `cross` | 두 계층 간 link (shape.component_id ↔ design_doc leaf) 또는 두 element 간 관계 (label↔arrow 부착 등) |

`cross` 는 본 ADR 에서 신규 도입하는 layer 라벨이다. 기존 4개(layout/section/content + default content) 분류로는 표현되지 않던 *계층 간 정합성 검사* 를 명시한다. 자동 검증 테스트가 lint_rules/ 디렉토리의 rule id 와 RULE_LAYER_MAP 키 집합을 비교해 누락을 잡는다.

### 결정 3 — Element 부분 교체 시 비-design 메타 필드는 코드가 보존한다

modify_component 같은 도구가 LLM 으로부터 단일 textbox/shape 을 통째로 받아 교체하는 경우, LLM 응답 schema 에 *포함되지 않는* 비-design 메타 필드는 LLM 이 다시 채워주지 않으므로 코드가 기존 element 에서 가져와 보존해야 한다.

대상 필드:
- `z_index` (rendering order — 일반 생성·component 수정에서는 기존 값을 보존하고,
  렌더 순서 결함을 직접 다루는 Visual QA 수정에서만 명시 변경 허용)
- `grid_cell` (Layout layer link — 부분 수정 도구는 cell 변경 책임 없음)
- `component_id` (Section layer link — 호출 시 입력값 그대로 유지)

이 원칙은 미래에 추가되는 모든 "element 부분 교체" 도구에 동일하게 적용된다. 새 메타 필드가 schemas 에 추가될 때 해당 필드가 LLM schema 에 포함되지 않으면 자동으로 본 정책 대상이 된다.

전체 슬라이드 수정 도구도 같은 보존 원칙을 적용한다. 수정 응답이 표현하지 않는
필드는 기존 spec에서 복원하고, 응답이 표현할 수 있는 필드라도 수정 목적과 무관하면
기존 값을 유지한다. 특히 Visual QA는 issue가 지목한 시각 속성만 변경하고 나머지
렌더 순서와 계층 링크를 보존한다.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| dataclass 생성을 그대로 두고 누락 시 lint 로 잡기 | 시점이 늦음 — render/save 후 발견되면 이미 회귀 |
| LLM schema 에 z_index/grid_cell 도 포함시켜 LLM 이 다시 채우게 | LLM 이 의도 없는 z_index 를 만들어 렌더 순서가 매번 흔들림 — 오히려 회귀 |
| RULE_LAYER_MAP 등록을 자동 추론 (rule 이름 prefix 매칭 등) | 분류가 의미적이라 이름만으로 결정 불가, 명시 등록이 더 안전 |

## Consequences

### Positive

- 5단 계층 필드 누락이 *원천적으로* 일어날 수 없다 (`replace()` 패턴 + 자동 검증 테스트).
- 새 lint rule 추가 시 layer 분류를 강제로 의식하게 됨 (테스트 실패가 가이드).
- 부분 수정 도구가 늘어도 비-design 메타 보존 정책이 자동 적용.

### Negative / Risks

- `replace()` 패턴 은 dataclass frozen 인스턴스에 한해 동작. 새 필드 추가 시 default 값을 잘 설정해야 의도치 않은 누락을 막음.
- `cross` layer 분류는 의미적이라 새 규칙이 어디 속하는지 사람이 판단해야 함 — 명백하지 않은 케이스에서 분류가 흔들릴 수 있음.

## References

- [0011: 5단 디자인 스펙 계층](./0011-five-layer-design-spec-hierarchy.md)
- [modify/0003 (modify): modify_component MCP 도구](../modify/0003-modify-component-mcp-tool.md)
- [lint/0005 (lint): 5단 계층 lint 정책](../lint/0005-five-layer-lint-policy.md)
