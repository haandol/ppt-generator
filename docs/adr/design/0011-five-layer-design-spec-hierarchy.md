# 5단 디자인 스펙 계층 — Project / Slide / Layout / Section / Content

Date: 2026-05-26 (rolled up earlier grid-first + progressive abstraction ADRs; 데이터 무결성·lint 정책·autofit 기본값은 design/0013, lint/0005, design/0014 로 분리)

## Status

Accepted (2026-07-21)

## Context

초기에는 디자인 스펙을 grid-first 4단(outline → grid_layout → cell_assignment → textboxes/shapes) 으로 두었다. 이 4단은 LLM 자기-조건화에는 효과적이었지만 다음 두 가지를 해결하지 못했다.

1. **사용자 부분 수정의 식별성**: "좌측 두 번째 카드 색을 빨강으로", "다이어그램 영역을 우측으로" 같은 의미 단위 명령에서 LLM 이 어떤 textbox/shape 을 가리키는지 추정해야 했다. cell 의 `role` 이 라벨로 쓰였지만 단일 라벨이라 카드/보조 라벨/장식이 한 cell 에 섞이면 모호했다.
2. **공간 충돌의 구조적 차단**: 픽셀 좌표가 stage 4 에서야 결정되면서 형제 도형 간 겹침, 컨테이너 외부 침범 같은 문제가 stage 4 이후 lint 에서야 드러났다. 거시 단계에서 이미 캔버스를 nested 사각형으로 분할해두면 충돌이 *구조적으로* 발생하지 않는다.

본 ADR 은 그 4단 사이에 **Section** 계층을 끼워 5단 계층으로 확장하고, Section 계층을 **의미 + bbox** 양쪽 책임을 가진 트리로 정의해 부분 수정 식별성과 공간 충돌 차단을 동시에 해결한다.

## Decision

디자인 스펙을 다음 5단 계층으로 정의하고 모든 코드/프롬프트/테스트를 이 계층에 맞춰 정렬한다.

```
Project   = DesignSpec                  ── 전체 발표 묶음 (slides 리스트)
  └ Slide  = PptxSlideSpec              ── 한 페이지, 한 주제
      └ Layout = GridPlan               ── 거시 격자 (regions + columns/rows + cells)
          └ Section = design_doc.layout 트리 ── 의미 영역 + bbox + role + description
              └ Content = textboxes/shapes  ── 픽셀, 텍스트, 폰트, 색
```

각 계층이 답하는 질문이 다르다:

| 계층 | 답하는 질문 |
|---|---|
| Project | 이 발표는 무엇을 다루는가? 슬라이드 순서는? |
| Slide | 이 페이지의 한 가지 주제는 무엇인가? speaker_notes 는 무엇을 말할 것인가? |
| Layout | 이 슬라이드를 어떻게 격자로 분할하는가? (header/content/footer × columns × rows) |
| Section | 각 영역에 어떤 *의미* 가 들어가는가? 그 영역의 bbox 는? 어떤 component 들로 구성되는가? |
| Content | 그 component 를 실제로 어떤 textbox/shape 으로 그리는가? (픽셀, 텍스트, 스타일) |

### 결정 1 — Section 계층의 도입

Layout(GridPlan) 과 Content(textboxes/shapes) 사이에 **Section 트리** 를 끼운다. design_doc 안의 트리 노드는 다음을 가진다:

- 트리 path 형태의 id (`right_diagram`, `right_diagram.functions.web_search`)
- parent_id (root 는 빈 문자열)
- kind: `section` | `group` | `component`
- role: 자유 라벨 (`llm_box`, `function_card`, `card_title`, `axis_label` 등)
- description: 1-2 문장 의미 설명
- cell_id: GridPlan cell 과 매핑 (Layout 과의 link)
- bbox (left/top/width/height)

`section` 은 슬라이드의 큰 의미 영역(보통 cell 1개와 매핑), `group` 은 깊이 2 이상이 필요한 중간 묶음, `component` 는 leaf 로 정확히 한 textbox/shape 이 component_id 로 참조한다.

### 결정 2 — Content 가 Section 의 component_id 를 참조

textbox/shape 의 component_id 필드를 Section 트리의 leaf id 와 link 한다. 부분 수정 시 LLM 은 의미 path(`right_diagram.llm_box`) 로 정확히 한 요소를 식별한다.

### 결정 3 — bbox-first 점진적 하강

Section/group 노드는 자식보다 *먼저* bbox 를 결정한다. 자식 bbox 는 부모 bbox 안에 완전히 포함되어야 하며, 같은 부모 아래 형제는 bbox 가 겹치면 안 된다. 이로써 Stage 4(Content) 진입 시점에 캔버스가 이미 nested 사각형으로 분할되어 있다. `layout-tree-bbox` lint 규칙군(sibling-overlap, containment, bbox-missing, canvas-overflow) 이 이 원칙을 강제한다.

### 결정 4 — speaker_notes 는 발표 narrative 전용

이전엔 speaker_notes 에 슬라이드 구조 설명("다이어그램 외곽의 점선 박스가...") 과 발표 narrative 가 섞였다. 5단 계층에서 구조 설명의 자리는 Section 트리 (description, layout_summary) 다. speaker_notes 는 청중에게 말할 narrative 만 담는다 (1-3 short paragraphs, 대화체).
슬라이드에 배치하지 못한 보충 콘텐츠를 speaker_notes로 이동하지 않으며, 해당 내용은
구조화된 overflow로 보고해 upstream 콘텐츠 결정으로 돌려보낸다.

### 결정 5 — design_doc 은 content 슬라이드에서 Required, title/closing 은 Optional

content 슬라이드 LLM 응답 모델은 grid_layout / cell_assignment / design_doc 모두 Required. title/closing 슬라이드는 fixed special layout 이라 모두 Optional. 슬라이드 타입별 프롬프트(`design_system_title` / `design_system_closing`) 도 동일 정책을 명시해 base prompt 와 정합을 맞춘다.

LLM 은 거시 → 미시 순서로 출력한다 (Pydantic 필드 선언 순서가 schema 에 박힘):

```
grid_layout       ← Stage 2 (격자 거시)
cell_assignment   ← Stage 3 (격자 슬롯)
design_doc        ← Stage 3.5 (Section 트리 + bbox)
background_color
speaker_notes     ← 발표 narrative ONLY
textboxes / shapes ← Stage 4 (Content, component_id 로 Section 과 link)
overflow
```

### 결정 6 — LayoutNode 를 flat list + parent_id 로 직렬화

자기 참조 트리(`children: list["LayoutNodeOutput"]`) 는 strands `structured_output_model` 처리 시 schema 재귀로 RecursionError 를 유발한다. flat list + parent_id 로 직렬화하고 dataclass 변환 시 트리로 재구성한다.

### 결정 7 — examples 디렉토리는 5단 계층 데모로 채운다

`prompts/examples/` 는 LLM 인-컨텍스트 학습용 슬라이드 예시 모음이다. 5단 계층(특히 design_doc.layout 트리 + component_id 링크) 이 충실히 채워진 예시 ≥1 개를 두고, base 프롬프트에서 참조한다.

### 결정 8 — 프롬프트 예시는 실제 응답 계약을 통과해야 한다

프롬프트에 포함되는 JSON 예시는 설명용 의사 JSON이 아니라 해당 슬라이드 타입의 실제
응답 계약을 만족하는 유효한 예시로 유지한다. content 예시는 Layout, Section,
Content 링크를 모두 포함하고, title/closing 예시는 해당 타입의 생략 가능 필드 정책을
따른다. 예시가 응답 스키마와 어긋나면 테스트에서 실패해야 한다.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| 4단 유지 + 프롬프트로 의미 라벨 강화 | cell.role 단일 라벨이 카드/보조 라벨/장식 혼재를 표현 못함 |
| Section 계층은 의미만, bbox 는 Content 가 결정 | 공간 충돌이 Stage 4 이후 lint 에서야 드러남 — 구조적 사전 차단 불가 |
| design_doc 을 별도 LLM 호출로 분리 | 호출 수 증가·지연 증가, single-call self-conditioning 의 이점 손실 |
| LayoutNode 를 nested children 으로 직렬화 | strands schema 재귀로 RecursionError, flat + parent_id 로 우회 필요 |

## 하위 호환성

- 기존 generated 슬라이드는 design_doc=None / component_id=None 으로 그대로 동작 (graceful fallback).
- HTML / PPTX 렌더러는 design_doc / component_id 를 무시하므로 시각 출력 무영향.
- imported PPTX 는 design_doc=None 으로 들어감 (lazy backfill 은 modify/0004).

## Consequences

### Positive

- **사용자 부분 수정 명확**: "좌측 두 번째 카드", "LLM 박스" 같은 의미 명령이 component_id 매칭으로 정확히 식별됨.
- **구조적 충돌 차단**: bbox-first 원칙 + layout-tree lint 로 형제 겹침/외부 침범이 stage 4 이전에 차단.
- **speaker_notes 정화**: 발표용 텍스트가 청중-facing tone 으로 유지.
- **추상화 응집**: Layout(격자)와 Section(의미)이 분리되어 각 계층이 한 종류의 결정만 담당.
- **단방향 의존성 강화**: lint 가 Content → Section → Layout 단방향성을 강제.

### Negative / Risks

- LLM 응답 schema 가 커져 토큰/지연 약간 증가 (실측 단일 호출 ~3-5%).
- design_doc Required 로 인해 LLM 출력 실패율이 미미하게 상승 가능 → review/재생성 메커니즘으로 회복.
- LayoutNode 의 자기 참조 트리는 schema 제약상 flat list + parent_id 로 우회 (직접 nested children 사용 불가).
- 프롬프트 예시를 계약 테스트 대상으로 유지해야 하므로 예시 변경 시 검증 비용이
  추가된다.

## Out of Scope (다른 ADR 에서 다룸)

- 5단 계층 *데이터 무결성* (PptxSlideSpec 재구성 필드 보존, element 부분 교체 시 비-design 메타 보존) — **0013**
- 5단 계층 *lint 정책* (단계적 lint, cross-layer link 검증, layout-tree severity 격상 등) — **lint/0005**
- shape autofit 기본값 변경 — **0014**
- 다단 LLM 호출 분리 (비용/지연 영향 큼)
- imported PPTX lazy design_doc backfill — modify/0004

## References

- [project/0002 (project): 점진적 구체화 파이프라인 설계](../project/0002-progressive-refinement-pipeline.md)
- [outline/0004 (outline): Layout Planning Phase](../outline/0004-layout-planning-phase.md)
- [modify/0003 (modify): modify_component MCP 도구 — Section 단위 부분 수정](../modify/0003-modify-component-mcp-tool.md)
- [modify/0004 (modify): Imported 슬라이드 design_doc lazy backfill](../modify/0004-imported-slide-lazy-backfill.md)
- [0013: 5단 계층 데이터 무결성](./0013-five-layer-data-integrity.md)
- [lint/0005 (lint): 5단 계층 lint 정책 — cross-layer 검증 + 단계적 실행](../lint/0005-five-layer-lint-policy.md)
- [0014: PptxShape autofit 기본값 — shrink_text](./0014-shape-autofit-shrink-text.md)
