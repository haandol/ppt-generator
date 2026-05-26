# 화살표·라벨 부착 검증 lint — arrow-endpoint-attachment, label-orphan

Date: 2026-05-25

## Status

Accepted (verified 2026-05-26: arrow_endpoint_attachment + label_orphan lint rule 정착)

## Context

다이어그램 슬라이드를 직접 좌표로 편집할 때 (특히 LLM 생성 후 수동 보정 / 사용자 요청에 따른 재배치) 다음 두 패턴의 시각 결함이 반복적으로 발생한다.

### 1. 화살표 끝점이 어디에도 닿지 않음 (floating arrow)

`end_arrow=True` 또는 `start_arrow=True`인 line shape 의 화살표 끝점이 어떤 박스 변에도 닿지 않아 허공에서 끝난다. 박스 위치를 옮긴 뒤 연결선 좌표를 잊고 그대로 두는 경우 자주 발생한다.

37 페이지 회귀선 사례:
- 박스 위치 재배치 후 회귀 점선이 `error` 박스 좌측 변에서 ~30px 떨어진 채 종료
- visual_qa 가 "Red dashed regression line ends in open space" 로 보고

기존 lint 는 line shape 좌표 자체가 0px 인지 (`zero-size-shape`) 만 검사하고, 끝점이 다른 shape 의 변에 정확히 붙는지는 보지 않는다.

### 2. 짧은 라벨이 어디에도 묶이지 않음 (orphan label)

`Yes`, `No`, `OK`, `↺` 같은 짧은 라벨 textbox 가 어떤 shape 에서도 멀리 떨어진 빈 공간에 위치한다. 박스를 재배치하면서 라벨 textbox 의 좌표 업데이트를 빠뜨리는 경우 발생한다.

37 페이지 사례:
- 박스 재배치 후 `Yes` / `No` textbox 가 박스 옆이 아닌 빈 공간에 floating
- visual_qa 가 "Yes label is squeezed / No label sits awkwardly in empty space" 로 보고

기존 lint 는 textbox 의 grid_cell 매핑만 검사하고, 의미적으로 묶일 수 있는 인접 shape 이 있는지는 보지 않는다.

### 왜 lint 로 잡아야 하는가

두 결함은 모두 **시각적으로는 즉시 보이지만 좌표 데이터만 봐서는 알기 어렵다.** visual_qa (이미지+비전 분석) 가 결국 잡아주지만:
- 비전 호출 토큰 비용이 큼 (스크린샷 1장 ~2000 토큰)
- 메인 컨텍스트에 이미지를 직접 읽으면 빠르게 컨텍스트 소진
- 자동 수정 (`auto_fix=true`) 신뢰도가 낮음 — 본 세션에서도 `slides_fixed: 0` 으로 종료

좌표 기반 결정적 검사로 사전 차단할 수 있다면 visual_qa 를 호출하지 않고도 회귀를 막을 수 있다.

## Decision

두 가지 lint 규칙을 신설한다. 둘 다 `severity=warning` 으로 generation/modification 을 차단하지 않되, 결과 dict 에 노출되어 사용자/LLM 이 후속 수정할 수 있게 한다.

### A. `arrow-endpoint-attachment`

`end_arrow=True` 또는 `start_arrow=True` 인 line shape 의 화살표 끝점이 다른 non-decorative shape (line/decorative 제외) 의 외곽 변에서 `_ATTACH_TOLERANCE_PX` (기본 8px) 이내에 위치하는지 검사한다.

### B. `label-orphan`

다음 조건을 모두 만족하는 textbox 를 "라벨" 로 간주한다:
- 텍스트 총 길이 ≤ 12 자 (공백 포함)
- font_size_pt ≤ 14 (모든 run 중 최대값 기준)
- height_px ≤ 32

라벨이 어떤 non-decorative shape 의 외곽 변에서 `_LABEL_PROXIMITY_PX` (기본 32px) 이내에 위치하지 않으면 경고한다. 제목 textbox (slide_index 0 등) 는 grid_cell 이 header region 에 매핑되어 있으면 검사 제외.

### Technical Details

#### 1. 신규 상수 (`interfaces/constants.py`)

```python
LINT_ARROW_ATTACH_TOLERANCE_PX = 8.0
LINT_LABEL_ORPHAN_PROXIMITY_PX = 32.0
LINT_LABEL_ORPHAN_MAX_CHARS = 12
LINT_LABEL_ORPHAN_MAX_FONT_PT = 14
LINT_LABEL_ORPHAN_MAX_HEIGHT_PX = 32.0
```

#### 2. 새 규칙 파일 (`lint_rules/arrow_endpoint_attachment.py`)

```python
def check_arrow_endpoint_attachment(spec, result):
    box_edges = _collect_box_edges(spec)  # list of (x_min, x_max, y_min, y_max) for non-line, non-decorative shapes
    for idx, shape in enumerate(spec.shapes):
        if shape.shape_type != "line":
            continue
        endpoints = _arrow_endpoints(shape)  # [(x, y, "start"|"end"), ...]
        for x, y, which in endpoints:
            if not _within_any_box_edge(x, y, box_edges, _ATTACH_TOLERANCE_PX):
                result.violations.append(
                    LintViolation(
                        rule="arrow-endpoint-attachment",
                        severity="warning",
                        message=f"line shape[{idx}] 의 {which} 화살표 끝점 ({x:.0f},{y:.0f}) 이 어떤 박스 변에도 닿지 않음 (>={_ATTACH_TOLERANCE_PX:.0f}px 이내 필요)",
                        ...
                    )
                )
```

화살표 끝점 좌표 계산:
- `start_arrow=True` → `(left_px, top_px)` (line 시작점에 화살표)
- `end_arrow=True` → `(left_px + width_px, top_px + height_px)` (line 끝점에 화살표)

박스 변 근접 판정 — 끝점이 박스의 외곽 사각형 (`left_px-tol ≤ x ≤ right+tol AND top-tol ≤ y ≤ bottom+tol`) 안에 있고, 4 변 중 한 변에서 `tol` 이내인지.

#### 3. 새 규칙 파일 (`lint_rules/label_orphan.py`)

```python
def check_label_orphan(spec, result):
    boxes = [s for s in spec.shapes if not is_decorative(s) and s.shape_type != "line"]
    for idx, tb in enumerate(spec.textboxes):
        if not _is_label(tb):
            continue
        if _is_in_header_region(tb, spec.grid_plan):
            continue  # 제목은 검사 제외
        if not _near_any_box(tb, boxes, _LABEL_PROXIMITY_PX):
            result.violations.append(...)
```

`_is_label`: 글자수, 폰트, 높이 게이트.
`_near_any_box`: textbox 의 4 변 중 한 점이 박스의 외곽 사각형에서 32px 이내인지.

#### 4. ALL_RULES 등록 (`lint_rules/__init__.py`)

```python
from ppt_generator.interfaces.spec_utils.lint_rules.arrow_endpoint_attachment import (
    check_arrow_endpoint_attachment,
)
from ppt_generator.interfaces.spec_utils.lint_rules.label_orphan import (
    check_label_orphan,
)
ALL_RULES = [..., check_arrow_endpoint_attachment, check_label_orphan]
```

#### 5. 테스트 (`tests/test_spec_utils_lint.py`)

`TestArrowEndpointAttachment`:
- 화살표 끝점이 박스 변에 정확히 닿음 → pass
- 끝점이 박스에서 5px 떨어짐 (tolerance 8 이내) → pass
- 끝점이 박스에서 30px 떨어짐 → fail
- `end_arrow=False, start_arrow=False` line → 검사 제외

`TestLabelOrphan`:
- "Yes" 12pt height=22 박스 옆 10px → pass
- "Yes" 12pt height=22 빈 공간 100px 떨어짐 → fail
- "긴 본문 텍스트입니다" 16pt → 라벨 게이트 통과 못 함, 검사 제외
- 제목 textbox (header region) → 검사 제외

## Consequences

### Positive
- 화살표 floating, 라벨 orphan 두 결함이 좌표 기반으로 사전 차단됨
- visual_qa 호출 빈도 감소 → 토큰/시간 절약
- 박스 위치 재배치 시 연결선/라벨 갱신 누락을 즉시 발견
- 메인 컨텍스트에 이미지 디코딩을 안 들고 와도 됨

### Negative / Trade-offs
- **Arrow false positive**: 의도적으로 박스 밖에서 끝나는 화살표 (예: "외부로 흐름이 빠져나감" 표현) 사용 시 경고 발생. 빈도 낮음, severity=warning 으로 차단은 안 함.
- **Label false positive**: 슬라이드 한쪽에 의도적으로 떠있는 짧은 caption 이 있는 경우. 글자수 ≤12 + 폰트 ≤14 + 높이 ≤32 의 좁은 게이트로 일반 본문은 거의 잡히지 않음.
- 새 규칙 두 개 추가로 lint 호출 시간 미세 증가 (실질적 영향 없음, O(N×M) shape×box 검사).

### 마이그레이션
- 기존 spec 호환성 영향 없음 (검사만 추가).
- severity=warning 이라 generation/modification 차단 안 함.
- 기존 47 슬라이드에 대해 lint 재실행 시 false positive 발견되면 `expected` 메시지를 참고해 좌표 수정.
