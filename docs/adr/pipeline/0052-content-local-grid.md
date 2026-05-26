# ADR-0052: Content 로컬 그리드 — Section 컨텐츠 영역의 sub-grid 분할

Date: 2026-05-26 (updated 2026-05-26: 구현 진입 직전 Rejected)

## Status

**Rejected** (구현 시작 후 표현력 trade-off 재평가로 폐기)

## Rejection Rationale

구현을 시작하면서 "복잡한 다이어그램에서 local_grid 가 과연 도움이 되는가" 를
재검토한 결과, *카드 그리드 vs 자유형 다이어그램* 의 두 케이스에서 답이 갈라
지는데 자유형 쪽이 본 프로젝트의 주된 사용 패턴임을 확인했다.

- **로컬 그리드가 유리한 경우** (정형 슬롯): 3×3 매트릭스, 5×1 파이프라인,
  2×3 카드 그리드, 4×2 테이블형 다이어그램. 자식이 *균일 슬롯* 에 떨어지고
  슬롯 위치 자체가 의미를 가질 때.
- **자유 배치가 유리한 경우** (자유형 다이어그램): LLM 중심 + 함수 호출 다
  이어그램, 트리 다이어그램, 흐름도(분기/조건문), 네트워크 토폴로지. 자식
  위치가 의미적으로 비대칭이거나 화살표·라벨이 격자 사이를 가로지를 때.

본 프로젝트가 LLM·에이전트 · 아키텍처 다이어그램 등 *비대칭 자유형* 을 자주
다루기에, local_grid 도입은 자유형 케이스에서 표현력을 *제약* 하는 비용이 카드
그리드 케이스의 충돌 차단 이득보다 크다.

또한 카드 그리드 케이스의 충돌은 이미 다음 lint 가 충분히 강제한다:
- `sibling-grid-uniformity` (cross/warning)
- `sibling-gap-minimum` (cross/warning)
- `layout-tree-sibling-overlap` (section/error)
- `layout-tree-containment` (section/error)

→ 추가 schema 필드(LocalGrid + 4 개 LayoutNode 필드) 와 신규 lint 2 종 (`local-
grid-cell-collision`, `local-grid-bbox-derivation`) 의 가치 대비 LLM 학습 부담·
schema 토큰·자유형 표현력 손실이 크다. **컨텐츠 영역(section 내부) 은 자유 배치
유지** 가 결론.

## Decision (Withdrawn)

이하 5 개 결정은 *제안* 단계에서 종합 평가 후 채택하지 않는다. 코드 변경 없음.

(원본 결정 기록은 학습 가치가 있어 아래 그대로 보존한다.)

## Context

ADR-0049 가 5단 계층(Project / Slide / Layout / Section / Content) 을 정의하면서
**Layout(GridPlan)** 이 슬라이드 *전역 캔버스* 를 격자로 나누고, **Content(textbox/
shape)** 는 자유 픽셀로 배치된다. Section(design_doc.layout) 은 그 사이에서
의미 영역의 bbox 만 결정하고 자식 component 의 좌표는 LLM 이 *자유롭게* 픽셀로
정한다.

이 구조는 LLM 의 표현력을 크게 보장하지만 다음 부작용을 누적시켰다.

1. **겹침이 사후 lint 로만 잡힘**: 같은 Section 안 두 component 의 bbox 가 픽셀
   단위로 겹치는지 검사하기 위해 `textbox-textbox-overlap`, `decoration-shape-
   overlap`, `sibling-gap-minimum`, `sibling-grid-uniformity`, `element-out-of-
   section`, `section-element-bbox-mismatch` 등 6-8 개 cross-layer rule 이 누적됐다.
   각 규칙은 *결과* 의 충돌을 잡지만, *입력 schema* 차원에서 충돌이 *나올 수
   없게* 만드는 메커니즘은 없다.

2. **부분 수정 식별성의 한계**: 사용자가 "이 카드 그룹의 두 번째 슬롯" 이라고
   할 때, LLM 은 leaf id 매칭으로 element 1 개를 찾을 수는 있지만 *그 element
   가 격자의 어느 슬롯에 속한다* 는 의미 정보는 component_id 에만 의존한다.
   "왼쪽 위 슬롯" 같은 위치 기반 명령은 픽셀 좌표 추론에 의존.

3. **복잡한 컨텐츠 영역에서의 충돌 빈발**: 본 ADR 의 핵심 동기. 단순 카드
   묶음(2-3 개) 은 자유 배치로도 충돌이 드물지만, **다이어그램 등 컨텐츠가
   복잡한 section** (LLM 박스 + 도구 호출 화살표 + 결과 카드 + 라벨 다수가
   한 영역에 밀집) 에서는 자유 픽셀 배치가 거의 매번 lint 위반을 만든다.
   영역 복잡도가 올라갈수록 자유 배치의 *충돌 확률* 이 기하급수적으로 증가
   하고, 사후 lint 만으로는 LLM 을 안정적으로 가이드하기 어렵다.

ADR-0049 의 GridPlan 이 *전역* 격자를 도입해 슬라이드 거시 분할을 구조화한
것처럼, 본 ADR 은 **컨텐츠가 복잡한 Section 영역 내부** 에 **로컬 그리드**
를 도입해 그 안의 component 배치를 *구조적으로* 다룬다. 단순 영역은
local_grid=None 으로 두고 자유 배치를 유지하므로, 본 결정은 *복잡도가
임계 이상* 일 때만 발현되는 도구다.

## Decision

design_doc 의 `section` / `group` 노드에 **로컬 그리드** 를 옵션으로 정의해
자식 component 들이 그 로컬 격자의 cell 을 참조하도록 한다. Section bbox 가
*Content 영역의 외곽* 을 결정하고, 로컬 그리드가 그 내부를 격자로 *재분할* 한다.

구체 결정은 다음과 같이 5 가지로 모듈화 (구현 PR 시 결정 1~5 분리 가능).

### 결정 1 — `LayoutNode.local_grid` 필드 추가 (Optional)

```python
@dataclass
class LocalGrid:
    columns: int       # ≥ 1
    rows: int          # ≥ 1
    gap_px: float = 12.0  # cell 간 간격
    # 향후 확장: column_widths, row_heights (가변 폭/높이)

@dataclass
class LayoutNode:
    ...
    local_grid: LocalGrid | None = None
```

`section` / `group` 노드에서만 의미 있다 (component leaf 는 자기가 grid cell
이지 grid 를 *가질* 수 없다). LLM 이 영역 복잡도에 맞춰 1×1 (자유 1 슬롯) /
2×3 (카드 묶음) / 4×2 (다이어그램) 등을 선택.

`local_grid=None` 이면 기존 ADR-0049 의 자유 배치 fallback (하위 호환).

### 결정 2 — `LayoutNode.local_cell` 필드 (component leaf 가 부모 로컬 grid cell 참조)

```python
@dataclass
class LayoutNode:
    ...
    local_cell: tuple[int, int] | None = None  # (row, col), 1-based
    local_cell_span: tuple[int, int] = (1, 1)  # (row_span, col_span)
```

부모 노드에 `local_grid` 가 설정돼 있으면 자식 component leaf 는 `local_cell`
로 자기가 *어느 슬롯* 에 속하는지 명시한다. LLM 출력 단계에서 자식 bbox 는
여전히 픽셀로 박혀 있어야 하지만 (렌더 호환), `local_cell` 이 채워져 있으면
post-process 단계에서 그 cell 의 *기댓값 bbox* 와 비교해 자동 보정/lint 가
가능하다.

부모에 `local_grid=None` 이면 자식의 `local_cell` 은 무시 (자유 배치).

### 결정 3 — `local-grid-cell-collision` lint (cross layer, severity="error")

같은 부모의 `local_grid` 안에서 두 자식 component 의 `local_cell` (+ span) 이
서로 겹치면 위반. 픽셀 비교가 아니라 **격자 좌표 비교** 라 가짜 양성이 거의
없고 LLM 이 schema 단계에서 충돌을 사전 차단할 수 있다.

이 규칙이 성공적으로 보고되는 슬라이드에서는 다음 cross-layer rule 들이
이론상 *조건부 무력화* 가능 (cluttered cell 이 0 이면 픽셀 겹침도 없음):
- `textbox-textbox-overlap`
- `decoration-shape-overlap`
- `sibling-gap-minimum`
- `sibling-grid-uniformity`
- `textbox-shape-intrusion`

단, free-form element (화살표/라벨/SVG path) 는 cell 슬롯이 없을 수 있어
**전면 무력화는 안 한다** — 위 lint 들은 그대로 유지하고, local-grid 가 잡는
violations 와 *중복 보고* 만 회피하는 정도로 이후 별도 ADR 에서 다룬다.

### 결정 4 — `local-grid-bbox-derivation` lint (section layer, severity="warning")

`local_grid` 가 정의된 section/group 의 자식 component leaf bbox 는 다음 두
가지 방식 중 하나여야 한다.

(a) 자식 bbox 가 부모 bbox + local_grid 격자 슬롯 + gap 으로 *유도* 되는
    값과 ±8px 안에 있다 (정렬된 격자).
(b) 명시적으로 `local_cell=None` 으로 표시된 free-form 자식 (격자 외 자유
    배치, 예: 슬롯들 위로 가로지르는 화살표).

(a) 와 (b) 어느 쪽도 아닌 자식이 있으면 warning. *errror 가 아닌 이유*: LLM
이 의도적으로 grid 를 깨고 싶은 케이스 (강조 카드 1 개를 약간 더 넓게) 를
완전히 차단하면 표현력이 떨어진다.

### 결정 5 — 프롬프트 가이드 (`design_system_base`)

다음을 base prompt 에 추가:

1. **언제 local_grid 를 쓰는가**: 자식 component 가 3 개 이상이고 균일한
   슬롯 배치가 자연스러울 때. 단일 자식 / free-form 다이어그램은 None 유지.
2. **로컬 grid → 자식 bbox 도출 공식**: parent.left + col_index × (cell_w +
   gap), 등.
3. **free-form 표시법**: 격자 위로 가로지르는 화살표는 `local_cell=None` 으로
   명시.

### Out of Scope (이 ADR 범위 밖)

- 가변 column widths / row heights (현재는 균일 분할만)
- nested local_grid (group 안의 group 이 또 자체 local_grid 를 가짐)
- LLM 다단 호출로 local_grid 결정 → 자식 bbox 결정 분리 (현재는 단일 호출
  유지, schema 순서로 self-conditioning)
- modify_component 가 local_cell 을 인자로 받는 도구 변형

## Technical Details

### 영향 범위

- **schemas.py**
  - `LocalGrid` dataclass 신설
  - `LayoutNode.local_grid: LocalGrid | None`, `local_cell: tuple[int,int] | None`,
    `local_cell_span: tuple[int,int]` 추가
- **llm_output_models.py**
  - `LocalGridOutput`, `LayoutNodeOutput.local_grid / local_cell / local_cell_span`
- **spec_utils/parser.py**
  - LayoutNode 파싱에 새 필드 추가
- **spec_utils/lint_rules/local_grid_collision.py** (신규, layer="cross")
- **spec_utils/lint_rules/local_grid_bbox.py** (신규, layer="section")
- **spec_utils/lint_types.py::RULE_LAYER_MAP** entry 2 개 추가
- **prompts/design_system_base.prompt.md** 가이드 추가
- **prompts/examples/** 에 local_grid 가 채워진 예시 1-2 개 추가
- **tests/lint/test_local_grid.py** (신규)

### 하위 호환성

- 기존 generated 슬라이드는 `local_grid=None` 으로 graceful fallback (ADR-0049
  와 동일 패턴).
- HTML / PPTX 렌더러는 `local_grid` / `local_cell` 을 *무시* 한다 (자식 bbox 의
  픽셀 좌표가 여전히 진실의 원천).
- Imported PPTX 는 `local_grid=None` 으로 들어감 (LLM 후처리 backfill 은 별도
  PR).

### Acceptance Criteria

1. `LayoutNode.local_grid` 가 schema/dataclass/parser/serializer round-trip 으로
   보존됨.
2. `local-grid-cell-collision` 이 같은 격자 슬롯에 2 개 이상 자식이 들어간
   케이스를 error 로 검출.
3. `local-grid-bbox-derivation` 이 자식 bbox 가 격자 슬롯 도출값에서 8px 초과
   어긋난 케이스를 warning 으로 검출 (단, `local_cell=None` 자식은 제외).
4. `local_grid=None` 인 기존 슬라이드는 신규 lint 가 모두 skip (조건부).
5. 회귀: ADR-0049 의 21 개 Acceptance Criteria 가 모두 그대로 통과.

## Consequences

긍정적:
- **격자 충돌 사전 차단**: 픽셀 비교가 아니라 격자 좌표 비교라 LLM 이 *schema
  단계* 에서 충돌을 차단하기 쉽다.
- **부분 수정 위치 식별**: "두 번째 슬롯" 같은 위치 명령이 `(row, col)` 매칭
  으로 정확히 식별 가능. modify_component 의 표현력이 의미 단위 → 의미 + 위치
  단위로 확장.
- **복잡도 적응**: section 별로 1×1 ~ N×M 까지 grid 를 자유롭게 골라 LLM 이
  복잡도에 맞춰 표현 가능.

부정적/리스크:
- **schema 토큰 증가**: LayoutNode 에 3 필드 추가. ContentSlideSpecOutput
  토큰 ~5-8% 증가 추정.
- **LLM 학습 부담**: 새 개념 1 개 (로컬 격자) 가 base prompt + examples 에
  추가됨. 초기 슬라이드 품질이 일시적으로 떨어질 수 있음 (ADR-0049 도입 시와
  같은 학습 곡선).
- **자유 배치 손실 우려**: 다이어그램 화살표·라벨 같은 free-form element 는
  local_cell=None 처리가 필요. 프롬프트가 이를 충분히 가르치지 못하면 LLM 이
  모든 자식을 강제로 grid 에 끼워 넣어 표현력이 줄 수 있음.

## Resolved Questions (Rejected 직전, 학습 기록용)

본 ADR 이 Accepted 였을 때 결정된 답들. Rejected 후에는 구현되지 않으나, 향후
유사 결정에 참고하기 위해 보존한다.

1. **`local_grid` 강제 vs 권장 → 옵션**: section/group 마다 자유 선택. 단순
   영역(자식 1-2 개 또는 다이어그램 free-form) 은 None 유지. graceful
   fallback (ADR-0049 패턴) 과 일관.
2. **렌더러가 local_grid 를 정답으로 쓸지 → 자식 bbox 필수 유지**: 자식의
   left/top/width/height 는 여전히 spec 에 박혀 있어야 한다 (렌더링은 자식
   bbox 가 진실). local_grid + local_cell 은 *검증·식별 메타* 로 한정. 렌더러/
   parser/serializer/HTML/PPTX 변경 최소화.
3. **modify_component 와의 관계 → 본 ADR 범위 밖**: modify_component 는
   기존대로 element 1 개 교체에 한정. local_cell 변경은 향후 별도 도구
   (modify_grid_slot 등) 에서 검토. 현재는 LLM 이 update 호출로 슬라이드
   재생성 시 새 local_cell 도 함께 출력하는 구조.

## References

- [ADR-0049: 5단 디자인 스펙 계층 — Layout/Section/Content 책임 분리, GridPlan, 점진적 추상화 출력](./0049-five-layer-design-spec-hierarchy.md)
- [ADR-0050: modify_component MCP 도구](./0050-modify-component-mcp-tool.md)
