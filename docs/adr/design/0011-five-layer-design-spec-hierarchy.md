# 5단 디자인 스펙 계층 — Project / Slide / Layout / Section / Content

Date: 2026-05-26 (rolled up earlier grid-first + progressive abstraction ADRs; 데이터 무결성·lint 정책·autofit 기본값은 design/0013, lint/0005, design/0014 로 분리)

## Status

Accepted (2026-09-08)

## Context

초기에는 디자인 스펙을 grid-first 4단(outline → grid_layout → cell_assignment → textboxes/shapes) 으로 두었다. 이 4단은 LLM 자기-조건화에는 효과적이었지만 다음 두 가지를 해결하지 못했다.

1. **사용자 부분 수정의 식별성**: "좌측 두 번째 카드 색을 빨강으로", "다이어그램 영역을 우측으로" 같은 의미 단위 명령에서 LLM 이 어떤 textbox/shape 을 가리키는지 추정해야 했다. cell 의 `role` 이 라벨로 쓰였지만 단일 라벨이라 카드/보조 라벨/장식이 한 cell 에 섞이면 모호했다.
2. **공간 충돌의 구조적 검증**: 의미 그룹과 실제 렌더 요소가 연결되어야 어느 영역의
   충돌인지 설명하고 부분 수정 후에도 범위를 검증할 수 있다. 다만 같은 bbox를 Section과
   Content에 두 번 생성하게 하면 응답 크기와 실패 표면이 커진다.

본 ADR은 그 4단 사이에 **Section** 계층을 끼워 5단 계층으로 확장한다. Section은 의미
구조와 component 식별을 소유하고, 좌표는 Content에서 한 번만 생성한 뒤 서버가 Section
bbox를 파생한다.

## Decision Drivers

- 사용자는 배열 인덱스가 아니라 의미 이름으로 요소를 수정할 수 있어야 한다.
- LLM은 같은 좌표를 두 계층에 반복 출력하지 않아야 한다.
- 서버는 생성 결과에서 Section bbox를 결정론적으로 재구성할 수 있어야 한다.
- 필수 의미 링크가 빈 design_doc 껍데기로 우회되지 않아야 한다.

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
| Section | 각 영역에 어떤 *의미* 가 들어가는가? 어떤 component 들로 구성되는가? |
| Content | 그 component 를 실제로 어떤 textbox/shape 으로 그리는가? (픽셀, 텍스트, 스타일) |

### 결정 1 — Section 계층의 도입

Layout(GridPlan) 과 Content(textboxes/shapes) 사이에 **Section 트리** 를 끼운다. design_doc 안의 트리 노드는 다음을 가진다:

- 트리 path 형태의 id (`right_diagram`, `right_diagram.functions.web_search`)
- parent_id (root 는 빈 문자열)
- kind: `section` | `group` | `component`
- role: 자유 라벨 (`llm_box`, `function_card`, `card_title`, `axis_label` 등)
- description: 1-2 문장 의미 설명
- cell_id: GridPlan cell 과 매핑 (Layout 과의 link)

`section` 은 슬라이드의 큰 의미 영역(보통 cell 1개와 매핑), `group` 은 깊이 2 이상이 필요한 중간 묶음, `component` 는 leaf 로 정확히 한 textbox/shape 이 component_id 로 참조한다.

### 결정 2 — Content 가 Section 의 component_id 를 참조

textbox/shape 의 component_id 필드를 Section 트리의 leaf id 와 link 한다. 부분 수정 시 LLM 은 의미 path(`right_diagram.llm_box`) 로 정확히 한 요소를 식별한다.

### 결정 3 — Content 좌표에서 Section bbox를 파생

LLM 응답의 LayoutNode는 bbox를 출력하지 않는다. 서버는 component leaf가 참조하는
textbox/shape의 bbox를 leaf bbox로 사용하고, group과 section bbox는 모든 자식 bbox의
합집합으로 계산한다. 따라서 실제 좌표는 Content 계층에 한 번만 존재한다.

파생 후에는 같은 부모 아래 형제 영역의 의도하지 않은 겹침, 부모 영역 외부 침범과
캔버스 이탈을 lint로 검출한다. 장식 connector처럼 의미 component가 아닌 element는
Section 트리에 포함하지 않는다.

### 결정 4 — speaker_notes 는 발표 narrative 전용

이전엔 speaker_notes 에 슬라이드 구조 설명("다이어그램 외곽의 점선 박스가...") 과 발표 narrative 가 섞였다. 5단 계층에서 구조 설명의 자리는 Section 트리 (description, layout_summary) 다. speaker_notes 는 청중에게 말할 narrative 만 담는다 (1-3 short paragraphs, 대화체).
슬라이드에 배치하지 못한 보충 콘텐츠를 speaker_notes로 이동하지 않으며, 해당 내용은
구조화된 overflow로 보고해 upstream 콘텐츠 결정으로 돌려보낸다.

### 결정 5 — design_doc은 content 슬라이드에서 실질적으로 Required

content 슬라이드 LLM 응답 모델은 grid_layout, cell_assignment와 design_doc을 모두
요구한다. design_doc의 topic과 layout_summary는 비어 있을 수 없고, 최소 한 개의 root
section과 component leaf가 있어야 한다. 모든 의미 있는 textbox/shape는 선언된 grid
cell과 component leaf를 참조하고, 모든 component leaf는 정확히 한 element에서
참조되어야 한다. 빈 객체나 빈 layout은 계약을 만족하지 않는다.

title/closing은 Layout과 Section을 생략할 수 있지만 타입별 의미 역할을 component_id로
표현한다.

LLM 은 거시 → 미시 순서로 출력한다 (Pydantic 필드 선언 순서가 schema 에 박힘):

```
grid_layout       ← Stage 2 (격자 거시)
cell_assignment   ← Stage 3 (격자 슬롯)
design_doc        ← Stage 3.5 (Section 의미 트리)
background_color
speaker_notes     ← 발표 narrative ONLY
textboxes / shapes ← Stage 4 (Content, component_id 로 Section 과 link)
overflow
```

### 결정 6 — LayoutNode 를 flat list + parent_id 로 직렬화

자기 참조 트리(`children: list["LayoutNodeOutput"]`) 는 strands `structured_output_model` 처리 시 schema 재귀로 RecursionError 를 유발한다. flat list + parent_id 로 직렬화하고 dataclass 변환 시 트리로 재구성한다.

### 결정 7 — 예시는 관련 슬라이드에서만 제공한다

응답 계약 예시는 테스트 가능한 별도 자산으로 유지하되 모든 슬라이드 프롬프트에
상시 주입하지 않는다. 현재 component_hint와 복잡도에 도움이 되는 예시만 prepare
단계에서 선택해 제공한다.

### 결정 8 — 프롬프트 예시는 실제 응답 계약을 통과해야 한다

프롬프트에 포함되는 JSON 예시는 설명용 의사 JSON이 아니라 해당 슬라이드 타입의 실제
응답 계약을 만족하는 유효한 예시로 유지한다. content 예시는 Layout, Section,
Content 링크를 모두 포함하고, title/closing 예시는 해당 타입의 생략 가능 필드 정책을
따른다. 예시가 응답 스키마와 어긋나면 테스트에서 실패해야 한다.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| 4단 유지 + 프롬프트로 의미 라벨 강화 | cell.role 단일 라벨이 카드/보조 라벨/장식 혼재를 표현 못함 |
| Section 계층과 Content가 bbox를 각각 출력 | 충돌을 일찍 생각하게 하지만 같은 값을 두 번 맞춰야 해 응답과 검증이 비대해짐 |
| Section은 의미만 출력하고 서버가 Content 좌표에서 bbox 파생 | 식별성과 검증 가능성을 유지하면서 중복 좌표를 제거하므로 채택 |
| design_doc 을 별도 LLM 호출로 분리 | 호출 수 증가·지연 증가, single-call self-conditioning 의 이점 손실 |
| LayoutNode 를 nested children 으로 직렬화 | strands schema 재귀로 RecursionError, flat + parent_id 로 우회 필요 |

## 하위 호환성

- 기존 generated 슬라이드는 design_doc=None / component_id=None 으로 그대로 동작 (graceful fallback).
- HTML / PPTX 렌더러는 design_doc / component_id 를 무시하므로 시각 출력 무영향.
- imported PPTX 는 design_doc=None 으로 들어감 (lazy backfill 은 modify/0004).

## Consequences

### Positive

- **사용자 부분 수정 명확**: "좌측 두 번째 카드", "LLM 박스" 같은 의미 명령이 component_id 매칭으로 정확히 식별됨.
- **중복 좌표 제거**: 실제 좌표는 Content에 한 번만 생성되고 Section bbox는 서버가 파생.
- **실질 계약 보장**: 빈 design_doc과 누락된 component link가 ingest를 통과하지 못함.
- **speaker_notes 정화**: 발표용 텍스트가 청중-facing tone 으로 유지.
- **추상화 응집**: Layout(격자)와 Section(의미)이 분리되어 각 계층이 한 종류의 결정만 담당.
- **단방향 의존성 강화**: lint 가 Content → Section → Layout 단방향성을 강제.

### Negative / Risks

- 의미 트리와 component link를 생성하는 비용은 남지만 bbox 반복 출력 비용은 제거된다.
- component link가 필수라 기존의 느슨한 content 응답은 새 schema로 재생성해야 한다.
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
