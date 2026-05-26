# ADR-0049: 5단 디자인 스펙 계층 — Project / Slide / Layout / Section / Content

Date: 2026-05-26 (rolled up 2026-05-26: ADR-0044/0045/0046 흡수)

## Status

Accepted

## Context

초기에는 디자인 스펙을 grid-first 4단(outline → grid_layout → cell_assignment → textboxes/shapes)으로 두었다. 이 4단은 LLM 자기-조건화에는 효과적이었지만 다음 두 가지를 해결하지 못했다.

1. **사용자 부분 수정의 식별성**: "좌측 두 번째 카드 색을 빨강으로", "다이어그램 영역을 우측으로" 같은 의미 단위 명령에서 LLM이 어떤 textbox/shape을 가리키는지 추정해야 했다. cell의 `role`이 라벨로 쓰였지만 단일 라벨이라 카드/보조 라벨/장식이 한 cell에 섞이면 모호했다.
2. **공간 충돌의 구조적 차단**: 픽셀 좌표가 stage 4에서야 결정되면서 형제 도형 간 겹침, 컨테이너 외부 침범 같은 문제가 stage 4 이후 lint에서야 드러났다. 거시 단계에서 이미 캔버스를 nested 사각형으로 분할해두면 충돌이 *구조적으로* 발생하지 않는다.

본 ADR은 그 4단 사이에 **Section** 계층을 끼워 5단 계층으로 확장하고, Section 계층을 **의미 + bbox** 양쪽 책임을 가진 트리로 정의해 부분 수정 식별성과 공간 충돌 차단을 동시에 해결한다.

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

## Data Integrity — 5단 계층의 보존성

5단 계층은 *정의*만이 아니라 *데이터 흐름 전 구간*에서 보존되어야 의미가 있다. 즉,
파이프라인이 슬라이드를 LLM 출력 → parse → lint/clean → save → load → render → modify
순으로 옮길 때, 어느 한 곳에서도 Layout/Section 메타가 떨어져 나가면 안 된다.

### 결정 7 — 모든 `PptxSlideSpec` 재구성 지점은 5단 계층 필드를 모두 포함해야 한다

`PptxSlideSpec(...)` 를 새로 만드는 모든 코드 경로는 다음 필드를 명시적으로 채워야 한다:

- `slide_type` (Slide layer의 분류 키)
- `grid_plan` (Layout layer)
- `design_doc` (Section layer)
- `images` (Content layer의 일부 — 파이프라인 단계에서 누락되면 시각 회귀)
- `background_image_bytes` / `background_image_src` (rendering side data)

특히 `clean_slide_spec()` / `_clean_spec()` 같은 "정리" 함수는 *정리 의도*가 들어간 필드만
변경하고 나머지는 무손실로 통과시켜야 한다. dataclass 의 `replace()` 사용을 권장한다 —
새 dataclass 를 직접 생성할 경우 새 필드가 추가될 때마다 누락 위험이 생긴다.

### 결정 8 — Layer 매핑은 lint rule 전수 분류

`lint_types.RULE_LAYER_MAP` 는 *모든* lint rule 을 5단 계층 중 하나로 분류한다.
명시 안 된 rule 이 default `"content"` 로 fallback 되는 동작은 유지하되, 신규/기존
규칙 모두 명시적으로 매핑한다. 분류 가이드:

- `layout`: `grid_plan` (regions/columns/rows/cells) 을 보는 규칙
- `section`: `design_doc.layout` 트리/bbox 를 보는 규칙
- `content`: 단일 textbox/shape 의 텍스트·픽셀·스타일을 보는 규칙
- `cross`: 두 계층 간 link (예: shape 의 `component_id` 가 design_doc 트리의 leaf
  와 매칭하는지) 또는 두 element 간 관계 (label↔arrow 부착 등) 를 보는 규칙

`cross` 는 본 ADR에서 신규 도입하는 layer 라벨이다. 기존 4개(layout/section/content
+ default content) 분류로는 표현되지 않던 *계층 간 정합성 검사* 를 명시한다.

### 결정 9 — 슬라이드 타입별 프롬프트는 base 프롬프트와 정합

`design_system_title.prompt.md` / `design_system_closing.prompt.md` 는 fixed special
layout 슬라이드를 다룬다. base 프롬프트가 "title/closing MAY omit grid_layout/
cell_assignment/design_doc" 라고 명시한 만큼, 타입별 프롬프트도 동일 정책을
중복 명시한다. `grid_layout`/`cell_assignment` 만 omit 가능으로 적고 `design_doc`
은 누락하면 LLM 이 base 와 type 프롬프트의 불일치를 만난다.

### 결정 10 — examples 디렉토리는 5단 계층 데모로 채운다

`prompts/examples/` 는 LLM 인-컨텍스트 학습을 위한 슬라이드 예시 모음이다. 5단
계층(특히 `design_doc.layout` 트리 + `component_id` 링크) 이 충실히 채워진 예시
1~2 개를 두고, base 프롬프트에서 참조한다.

### 결정 11 — Element 부분 교체 시 비-design 메타 필드는 코드 보존

modify_component(ADR-0050) 처럼 LLM 이 단일 textbox/shape 을 통째로 출력해
교체하는 경우, LLM 응답 schema 에 포함되지 않는 *비-design 메타 필드* 는 LLM 이
다시 채워주지 않으므로 코드가 기존 element 에서 가져와 보존해야 한다.

대상 필드:
- `z_index` (rendering order — `TextBoxOutput`/`ShapeOutput` Pydantic schema 에
  의도적으로 제외됨; visual_qa_fix 단계에서만 명시 부여)
- `grid_cell` (Layout layer link — modify_component 는 cell 변경 책임 없음)
- `component_id` (Section layer link — 호출 시 입력값 그대로 유지)

코드 패턴:

```python
# modify_component 내부
new_elem = textbox_output_to_dataclass(output.textbox)
new_elem = replace(
    new_elem,
    component_id=component_id,                 # 입력값 유지
    z_index=existing.z_index,                  # 기존 보존
    grid_cell=existing.grid_cell,              # 기존 보존
)
```

이 원칙은 미래에 추가되는 모든 "element 부분 교체" 도구에 동일하게 적용된다.

### 결정 12 — Cross-layer link 정합성은 lint 로 강제

ADR-0049 Acceptance Criteria #5 ("textbox/shape의 component_id가 design_doc 트리
leaf id와 매칭") 는 base prompt 에서만 가이드되었다. LLM 출력 결함이 modify
단계에서 `ValueError` 로 늦게 터지는 위험을 차단하기 위해 다음 lint rule 을 추가한다.

**`component-id-link` (layer="cross")**:
- (a) 모든 textbox/shape 의 `component_id` 는 `design_doc.layout` 트리 어딘가의
  leaf 노드 `id` 와 매칭되어야 한다.
- (b) 모든 component leaf 는 정확히 1 개의 element 에서 참조되어야 한다 (0 개:
  trailing leaf, 2개 이상: ambiguous link).
- (c) 한 `component_id` 가 textbox 와 shape 양쪽에 등장하면 ambiguous (modify
  도구가 어느 element 를 가리키는지 결정 불가).

`component_id`/`design_doc` 가 모두 None 인 imported(미-backfill) 슬라이드와
title/closing 슬라이드는 검사 대상에서 제외 (조건부 lint).

이 규칙은 generate 직후 lint 와 review 진입 시점에 실행되어 이른 단계에서 LLM
결함을 잡는다.

### 결정 13 — 단계적 lint 실행 + Layout/Section 추가 link 검증

ADR-0049 결정 3·8·12 는 layer 분류·layout-tree bbox·component_id 정합성을
선언했지만, 실제 실행 차원에서 *단계적 검증* 은 이뤄지지 않았다. lint 호출
지점들 (`parallel_runner`, `handlers/generation`, `handlers/modification`) 이
모두 `lint_slide_spec(spec)` 만 호출했고, `layers=` 인자는 도입돼 있으나 미사용.
또한 GridPlan↔design_doc.cell_id, design_doc leaf bbox↔element bbox 의
정합성도 명시 검사 없이 LLM 자가 일관성에만 의존했다.

본 결정은 다음 세 가지를 추가해 ADR-0049 의 "구조적 사전 차단" 약속을
실행 차원에서 보강한다.

**(a) ALL_RULES 를 layer 그룹으로 정렬**

`lint_rules/__init__.py::ALL_RULES` 는 layout → section → cross → content 순서로
재정렬한다. 모든 규칙이 매번 다 돌긴 하지만, 호출자가 layer 별로 결과를
훑을 때 생성 파이프라인 순서와 일치하므로 가독성이 좋아진다.

**(b) `lint_slide_spec(stop_on_layer_error=True)` 옵션**

`lint_slide_spec(spec, layers=...)` 에 `stop_on_layer_error: bool = False`
인자를 추가한다. True 일 때 layout/section/cross 순서로 layer 별 검사를
순차 실행하고, 어느 layer 에 `severity="error"` 위반이 발견되면 *그 다음
layer 검사를 중단* 한다. 거시 위반을 먼저 보고하고 미시 노이즈로 가리지
않는 효과. 기본값은 False (기존 동작 유지).

`generate_slides_design_spec` / `modify_design_spec(action="update")` /
`modify_component` 의 lint 호출 지점이 이 옵션을 사용한다.

**(c) `grid-section-link` lint (layer="cross")**

design_doc.layout 트리의 모든 노드 `cell_id` 가 비어있지 않다면 GridPlan.cells.id
집합에 속해야 한다. 깨지면 modify 시 cell 정렬 일관성이 무너진다.

- `grid-section-link-orphan-cell` (severity="error"): cell_id 가 GridPlan 에
  존재하지 않는 id 를 가리킴.

design_doc 또는 grid_plan 이 None 인 슬라이드는 검사 제외.

**(d) `section-element-bbox-mismatch` lint (layer="cross")**

design_doc 의 component leaf bbox 와 그 leaf 를 component_id 로 참조하는
textbox/shape 의 bbox 가 임계값(8px) 이상 어긋나면 위반으로 보고.

- `section-element-bbox-mismatch` (severity="error"): leaf bbox 와 element bbox
  의 left/top/right/bottom 중 어느 하나라도 8px 초과로 불일치.

ADR-0049 결정 3 의 "Section bbox 가 Content bbox 보다 *먼저* 결정된다" 는
약속을 lint 차원에서 검증한다. modify_component 가 `bbox_changed=True` 시
동기화하는 것과 같은 맥락의 정합성 보장.

**(e') layout-tree sibling/containment/canvas-overflow severity error 격상**

ADR-0049 결정 3 의 "구조적 사전 차단" 을 실질화하려면 다음 3 개 규칙은
warning 이 아닌 **error** 여야 한다 — 이들은 시각 결함이 아니라 *데이터
구조 결함* 이고, modify_component 시 의미 영역을 잘못 가리키게 되어
부분 수정이 신뢰를 잃는다.

- `layout-tree-sibling-overlap`: 같은 부모 아래 형제 섹션의 origin(x,y) +
  width/height 로 정의된 bbox 가 1px² 초과로 겹침
- `layout-tree-containment`: 자식 bbox 가 부모 bbox 외부로 빠져나감
- `layout-tree-canvas-overflow`: bbox 가 캔버스 [0,0,1280,720] 밖

`layout-tree-bbox-missing` 만 warning 유지 (LLM 이 의도적으로 bbox 를
nested 노드로 미루는 경우가 있음).

**(e) generate 직후 cross-layer error 가드**

`parallel_runner._build_pipeline` 의 lint 호출이 `severity="error"` & `layer="cross"`
위반을 발견하면 슬라이드 결과에 `cross_layer_errors` 필드를 포함하고 응답에서
사용자에게 명시적으로 노출. 자동 재시도는 비용 영향이 커서 본 결정에선
*경고만* 한다 — 자동 재생성 정책은 별도 ADR 에서 다룬다.

**(f) 슬라이드 외곽 정렬 lint (`slide-edge-alignment-*`, layer="content")**

같은 슬라이드 안에서 외곽에 가까이 배치된 element 들은 좌/우/상/하 변이
일치해야 한다. 각 변의 *극값* (left=최소 left, right=최대 right, top=최소 top,
bottom=최대 bottom) 에서 16px 이내(cluster_threshold)에 있는 element 들을
"외곽 cluster" 로 보고, 그 cluster 내 element 들의 해당 변이 4px 초과로
극값과 어긋나면 위반 (severity="warning").

배경: PPT 의 시각적 일관성에서 가장 중요한 신호 중 하나는 *외곽 정렬* 이다.
"좌상단 좌하단의 x 좌표 시작이 같다" "우상단 우하단의 x 좌표 끝이 같다"
"좌상단 우상단의 y 좌표가 같다" 같은 인지가 깨지면 슬라이드 전체가
들쭉날쭉하게 보인다. 장식 element (얇은 디바이더) 는 검사 제외.

**(g) Section/Cell containment lint (`element-out-of-section` /
`element-out-of-grid-cell`, layer="cross")**

`section-element-bbox-mismatch` 가 *leaf↔element 1:1 동기화* 를 검사한다면
이 규칙은 *조상 섹션* 까지 거슬러 올라가 element 좌표가 섹션 경계를 벗어나는지
검사한다 — 각 섹션은 그리드를 어긋나는 좌표를 가진 element 를 가져선 안 된다.

- `element-out-of-section` (severity="error"): textbox/shape 의 bbox 가
  `component_id` 로 link 된 leaf 의 가장 가까운 ancestor section/group bbox
  외부로 8px 초과 빠져나감.
- `element-out-of-grid-cell` (severity="warning"): textbox/shape 의 `grid_cell`
  이 link 된 cell 의 region 분할 estimated bbox 외부로 16px 초과 빠져나감.
  design_doc.layout 의 cell_id 매칭 노드 bbox 가 더 정확하므로 보조 정보 수준.

### 결정 14 — PptxShape autofit_mode 기본값을 "shrink_text" 로 변경

`PptxShape.autofit_mode` 의 기본값을 `"expand_height"` → `"shrink_text"` 로 변경한다.
LLM 출력 모델 (`ShapeOutput.autofit_mode`) 의 default 도 동일하게 정렬한다.

**Why**:
- 대부분의 슬라이드는 카드 그리드(여러 sibling shape 의 높이/폭이 동일해야 보기
  좋은 레이아웃) 이며, expand_height 가 기본일 때는 카드 하나의 텍스트가 길면
  그 카드만 세로로 늘어나 균일성이 깨진다. 가장 흔한 디자인 회귀 패턴.
- shrink_text 는 카드 높이를 그대로 유지하고 폰트를 자동 축소한다. "텍스트 잘림"
  대신 "폰트 약간 작아짐" 으로 부작용이 옮겨가며, 이는 사용자가 받아들일 수 있는
  품질 저하다.
- 폰트가 너무 작아지는 케이스(가독성 ↓) 는 `font-range` lint(10~44pt 범위) 가
  차단한다. shrink 결과로 10pt 미만이 되면 warning. 이 안전망 덕에 default
  변경의 위험이 작다.
- `expand_height` 는 *명시적으로* 필요한 경우(자유롭게 흐르는 텍스트 블록, 단일
  callout) 에만 LLM 이 선택하도록 프롬프트에서 안내한다.

**Lint 영향**:
- `text-overflow` rule 은 `shrink_text` shape 에서 height-based overflow 검사를
  스킵 (폰트 자동 축소로 시각적 잘림이 없음). width-based 단어 overflow 검사
  (`text-width-overflow`) 는 그대로 유지 — 단일 단어가 카드 폭보다 길면 shrink
  도 못 살리는 케이스.
- `expand-height-collision` rule 은 `expand_height` shape 에 한정된 검사이므로
  default 변경이 false positive 를 만들지 않는다.

**하위 호환성**:
- 기존 generated 슬라이드 spec/json: `autofit_mode` 가 명시 출력되어 있어 영향
  없음. 새로 생성되는 슬라이드만 default 가 적용된다.
- imported PPTX 슬라이드: import 단계에서 별도 `autofit_mode` 부여 안 함 →
  dataclass default 적용. 시각 출력에 회귀가 의심되면 import 단계에서
  `autofit_mode="expand_height"` 를 명시 부여해 보존하는 옵션을 검토
  (현 ADR 범위 밖, 향후 회귀 발견 시 별도 조치).

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
9. **데이터 무결성 (결정 7)**: `clean_slide_spec()` / `_clean_spec()` 가 design_doc / grid_plan / images / slide_type / background_image_* 를 모두 보존 (단위 테스트로 검증). lint 후 cleaned_spec 의 5단 계층 필드가 입력 spec 과 동일.
10. **Layer 매핑 전수성 (결정 8)**: `lint_rules/` 의 모든 규칙이 `RULE_LAYER_MAP` 에 명시적으로 등록되어 있음 (test_lint_layer_coverage 로 검증). 신규 layer `"cross"` 가 `LintViolation.layer` 값으로 허용됨.
11. **타입별 프롬프트 정합 (결정 9)**: `design_system_title` / `design_system_closing` prompt 가 `design_doc` 도 omit 가능으로 명시.
12. **examples 디렉토리 (결정 10)**: `prompts/examples/` 에 5단 계층(특히 design_doc.layout) 이 채워진 슬라이드 예시 ≥1 개.
13. **Element 메타 보존 (결정 11)**: modify_component 가 element 교체 시 기존 `z_index` / `grid_cell` 을 보존 (단위 테스트로 검증).
14. **Cross-layer link lint (결정 12)**: `component-id-link` 규칙이 (a) 매칭 안 되는 component_id, (b) 0/2+ 개 참조되는 leaf, (c) textbox/shape 양쪽 매칭 ambiguous 를 검출.
15. **단계적 lint (결정 13a/b)**: `ALL_RULES` 가 layout → section → cross → content 순. `lint_slide_spec(stop_on_layer_error=True)` 가 layer 별 error 발견 시 다음 layer 를 스킵.
16. **Layout↔Section link (결정 13c)**: `grid-section-link-orphan-cell` 이 design_doc.layout.cell_id 가 GridPlan.cells.id 에 없는 케이스를 error 로 검출.
17. **Section↔Content bbox sync (결정 13d)**: `section-element-bbox-mismatch` 가 leaf bbox 와 component_id-linked element bbox 의 8px 초과 불일치를 error 로 검출.
18. **Cross-layer error 노출 (결정 13e)**: generate 결과 응답에 슬라이드별 cross-layer error 가 포함됨.
19. **외곽 정렬 (결정 13f)**: `slide-edge-alignment-{left,right,top,bottom}` 가 외곽 cluster 의 변 어긋남(4px 초과)을 warning 으로 보고.
20. **Section/Cell containment (결정 13g)**: `element-out-of-section` 이 element bbox 가 ancestor section bbox 를 8px 초과 벗어나면 error, `element-out-of-grid-cell` 이 grid_cell estimated bbox 를 16px 초과 벗어나면 warning.
21. **Layout-tree error 격상 (결정 13e')**: `layout-tree-sibling-overlap` / `containment` / `canvas-overflow` severity 가 error.

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
