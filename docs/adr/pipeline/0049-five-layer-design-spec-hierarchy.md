# ADR-0049: 5단 디자인 스펙 계층 — Project / Slide / Layout / Section / Content

Date: 2026-05-26

## Status

Accepted (supersedes ADR-0046 in scope: 4단 점진적 추상화 → 5단으로 확장)

## Context

ADR-0044 ~ 0046은 디자인 스펙을 grid-first 4단(outline → grid_layout → cell_assignment → textboxes/shapes)으로 정의했다. 이 4단은 LLM 자기-조건화에는 효과적이었지만 다음 두 가지를 해결하지 못했다.

1. **사용자 부분 수정의 식별성**: "좌측 두 번째 카드 색을 빨강으로", "다이어그램 영역을 우측으로" 같은 의미 단위 명령에서 LLM이 어떤 textbox/shape을 가리키는지 추정해야 했다. cell의 `role`이 라벨로 쓰였지만 단일 라벨이라 카드/보조 라벨/장식이 한 cell에 섞이면 모호했다.
2. **공간 충돌의 구조적 차단**: 픽셀 좌표가 stage 4에서야 결정되면서 형제 도형 간 겹침, 컨테이너 외부 침범 같은 문제가 stage 4 이후 lint에서야 드러났다. 거시 단계에서 이미 캔버스를 nested 사각형으로 분할해두면 충돌이 *구조적으로* 발생하지 않는다.

본 ADR은 ADR-0046의 4단 사이에 **Section** 계층을 끼워 5단 계층으로 확장하고, Section 계층을 **의미 + bbox** 양쪽 책임을 가진 트리로 정의해 부분 수정 식별성과 공간 충돌 차단을 동시에 해결한다.

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
| Slide | 이 페이지의 한 가지 주제는 무엇인가? speaker_notes는 무엇을 말할 것인가? |
| Layout | 이 슬라이드를 어떻게 격자로 분할하는가? (header/content/footer × columns × rows) |
| Section | 각 영역에 어떤 *의미*가 들어가는가? 그 영역의 bbox는? 어떤 component들로 구성되는가? |
| Content | 그 component를 실제로 어떤 textbox/shape으로 그리는가? (픽셀, 텍스트, 스타일) |

### 결정 1 — Section 계층의 도입

Layout(GridPlan)과 Content(textboxes/shapes) 사이에 **Section 트리**를 끼운다. Section 트리는 `design_doc.layout: list[LayoutNode]` 로 표현되며 각 노드는:

- `id`: 트리 path 형태 (`right_diagram`, `right_diagram.functions.web_search`)
- `parent_id`: 부모 노드 id (root는 빈 문자열) — flat list 직렬화용
- `kind`: `"section"` | `"group"` | `"component"`
- `role`: 자유 라벨 (`llm_box`, `function_card`, `card_title`, `axis_label` 등)
- `description`: 1-2 문장 의미 설명
- `cell_id`: GridPlan cell과 매핑 (Layout과의 link)
- `left_px / top_px / width_px / height_px`: bbox (Section이 점유하는 사각형)
- `children`: 트리 자식 (parent_id로 재구성)

`section`은 슬라이드의 큰 의미 영역(보통 cell 1개와 매핑), `group`은 깊이 2 이상이 필요한 중간 묶음, `component`는 leaf로 정확히 한 textbox/shape이 `component_id`로 참조한다.

### 결정 2 — Content가 Section의 component_id를 참조

`PptxTextBox.component_id` / `PptxShape.component_id` 필드를 Section 트리의 leaf id와 link한다. 부분 수정 시 LLM은 의미 path(`right_diagram.llm_box`)로 정확히 한 요소를 식별한다.

### 결정 3 — bbox-first 점진적 하강

Section/group 노드는 자식보다 *먼저* bbox를 결정한다. 자식 bbox는 부모 bbox 안에 완전히 포함되어야 하며, 같은 부모 아래 형제는 bbox가 겹치면 안 된다. 이로써 Stage 4(Content) 진입 시점에 캔버스가 이미 nested 사각형으로 분할되어 있다.

`layout-tree-bbox` lint 규칙군이 이 원칙을 강제:
- `layout-tree-sibling-overlap`: 같은 부모 아래 형제 bbox 겹침
- `layout-tree-containment`: 자식이 부모 외부로 빠져나감
- `layout-tree-bbox-missing`: section/group에 bbox 미지정
- `layout-tree-canvas-overflow`: bbox가 캔버스 밖

### 결정 4 — speaker_notes는 발표 narrative 전용

이전엔 `speaker_notes`에 슬라이드 구조 설명("다이어그램 외곽의 점선 박스가...")과 발표 narrative가 섞였다. 5단 계층에서 구조 설명의 자리는 Section 트리 (`description`, `layout_summary`)다. `speaker_notes`는 청중에게 말할 narrative만 담는다 (1-3 short paragraphs, 대화체).

### 결정 5 — design_doc은 content 슬라이드에서 Required

`ContentSlideSpecOutput.design_doc: DesignDocOutput` (Required). title/closing 슬라이드(`SimpleSlideSpecOutput`)는 다이어그램이 거의 없어 Optional 유지.

LLM은 다음 순서로 출력한다 (Pydantic 필드 선언 순서가 schema에 박힘):

```
grid_layout       ← Stage 2 (격자 거시)
cell_assignment   ← Stage 3 (격자 슬롯)
design_doc        ← Stage 3.5 (Section 트리 + bbox)
background_color
speaker_notes     ← 발표 narrative ONLY
textboxes / shapes ← Stage 4 (Content, component_id로 Section과 link)
overflow
```

### 결정 6 — LayoutNode를 flat list + parent_id 로 직렬화

`children: list["LayoutNodeOutput"]` 같은 자기 참조는 strands `structured_output_model` 처리 시 schema 재귀로 RecursionError를 유발한다. flat list + `parent_id` 로 직렬화하고 `to_dataclass()` 변환 시 트리로 재구성한다.

## ADR-0046과의 관계

ADR-0046은 4단(outline → grid_layout → cell_assignment → textboxes/shapes)을 정의했다. 본 ADR은 그 사이 Stage 3.5에 Section 계층을 추가해 5단으로 확장한다. ADR-0046의 모든 결정(grid_layout/cell_assignment 분리, content 슬라이드 Required, 단일 LLM 호출 유지)은 그대로 유효하며, 본 ADR이 그 위에 새 Section 계층을 더한다.

ADR-0046 자체는 deprecated 가 아니다. 0046의 격자 계층 결정은 Layout(=GridPlan) 계층의 정의로 그대로 살아있다. 본 ADR은 Section 계층을 추가하면서 0046의 cell.role이 짊어지던 *의미 결정* 책임을 Section으로 이동시킨다.

## Technical Details

### 영향 범위

- **schemas.py**
  - `LayoutNode` dataclass 신설 (id, parent_id, kind, role, description, cell_id, bbox, children)
  - `DesignDoc` dataclass 신설 (topic, layout_summary, layout 트리)
  - `PptxSlideSpec.design_doc: DesignDoc | None` 필드 추가
  - `PptxTextBox.component_id` / `PptxShape.component_id` 필드 추가
- **llm_output_models.py**
  - `LayoutNodeOutput` (flat, parent_id 참조), `DesignDocOutput` 추가
  - `_BaseSlideSpecOutput.design_doc`, `TextBoxOutput.component_id`, `ShapeOutput.component_id` 추가
  - `ContentSlideSpecOutput.design_doc` Required, `SimpleSlideSpecOutput`은 Optional
  - `_convert_flat_layout()` 헬퍼 (parent_id 기반 트리 재구성)
- **spec_utils/parser.py**
  - `_parse_design_doc()` / `_parse_layout_node()` (재귀 파싱)
  - textbox/shape 파싱에 component_id 추가
- **spec_utils/lint_rules/layout_tree_bbox.py** (신규)
  - sibling-overlap / containment / bbox-missing / canvas-overflow 4종 규칙
- **prompts**
  - `design_system_base.prompt.md`: Stage 3.5 design_doc 절차 추가, bbox-first 원칙 명시, speaker_notes 정의를 narrative-only로 정정
  - 출력 스키마 예시에 design_doc + component_id 추가
- **tests**
  - `tests/test_spec_utils_lint.py::TestLayoutTreeBbox` (6 케이스)
  - `tests/test_pptx_import.py` round-trip 테스트
  - `tests/test_slide_spec_output_models.py` design_doc Required 검증

### 하위 호환성

- 기존 generated 슬라이드는 design_doc=None / component_id=None 으로 그대로 동작 (graceful fallback)
- HTML / PPTX 렌더러는 design_doc / component_id 를 무시하므로 시각 출력 무영향
- imported PPTX는 design_doc=None 으로 들어감 (LLM 후처리 backfill은 별도 PR)

### Acceptance Criteria

1. content 슬라이드에서 `grid_layout`, `cell_assignment`, `design_doc` 누락 시 ValidationError (단위 테스트로 검증).
2. title/closing 슬라이드에서 design_doc 부재가 정상 통과.
3. layout-tree 규칙군이 sibling-overlap / containment / bbox-missing / canvas-overflow 케이스를 모두 검출.
4. design_doc.layout이 flat list로 직렬화되고 dataclass 변환 시 parent_id로 트리 재구성됨.
5. textbox/shape의 component_id가 design_doc 트리 leaf id와 매칭.
6. speaker_notes에 슬라이드 구조 설명이 들어가지 않음 (프롬프트로 강제, 새로 생성한 슬라이드의 speaker_notes에 "다이어그램 외곽의 점선 박스" 같은 구조 표현이 없는지 점검).
7. 기존 lint(`grid-plan-required` 등)는 변경 없이 통과.
8. 전체 pytest 회귀 없음.

### Out of Scope

- 다단 LLM 호출 분리 (별도 ADR 필요 — 비용/지연 영향 큼)
- imported PPTX 시점 design_doc / component_id 자동 추론 (LLM 후처리, 별도 PR)
- `modify_component(component_id, instruction)` MCP 도구 (Phase 2)
- 슬라이드별 region 픽셀 범위 동적 분할

## Consequences

긍정적:
- **사용자 부분 수정 명확**: "좌측 두 번째 카드", "LLM 박스" 같은 의미 명령이 component_id 매칭으로 정확히 식별됨
- **구조적 충돌 차단**: bbox-first 원칙 + layout-tree lint로 형제 겹침/외부 침범이 stage 4 이전에 차단
- **speaker_notes 정화**: 발표용 텍스트가 청중-facing tone 으로 유지
- **추상화 응집**: Layout(격자)와 Section(의미)이 분리되어 각 계층이 한 종류의 결정만 담당
- **단방향 의존성 강화**: lint가 Content → Section → Layout 단방향성을 강제

부정적/리스크:
- LLM 응답 schema 커짐 → 토큰/지연 약간 증가 (실측 단일 호출 ~3-5% 증가)
- design_doc Required로 인해 LLM 출력 실패율이 미미하게 상승 가능 → review/재생성 메커니즘으로 회복
- LayoutNode의 자기 참조 트리는 strands의 schema 처리 제약 때문에 flat list + parent_id 로 우회 (직접 nested children 사용 불가)

## References

- [ADR-0011: 점진적 구체화 파이프라인 설계](./0011-progressive-refinement-pipeline.md)
- [ADR-0040: Layout Planning Phase](./0040-layout-planning-phase.md)
- [ADR-0044: Grid-First Design Spec](./0044-grid-first-design-spec.md)
- [ADR-0045: Grid Plan Required by Slide Type](./0045-grid-plan-required-by-slide-type.md)
- [ADR-0046: Progressive Abstraction in Design Output](./0046-progressive-abstraction-design-output.md)
