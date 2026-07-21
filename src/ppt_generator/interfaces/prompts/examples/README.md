# Design Spec Examples

 5단 계층(Project / Slide / Layout / Section / Content)을 충실히 따르는
슬라이드 design spec 예시 모음. content 시스템 프롬프트는 이 디렉토리의 정식 예시
하나를 로드해 기존 inline `<examples>` 블록을 교체한다. 예시는 실제 응답 모델의
계약 테스트를 통과해야 한다.

각 예시는:
- `grid_layout` + `cell_assignment` (Layout 계층)
- `design_doc.layout` 트리 (Section 계층, bbox + parent_id)
- `textboxes` / `shapes` (Content 계층, `grid_cell` + `component_id` 링크)
를 모두 포함한다.

## 파일

- `two_column_diagram.json` — 2열 레이아웃: 좌측 설명 카드 + 우측 다이어그램.
  Section 트리 depth 2~3 활용 사례 (right_diagram 안에 functions 그룹).
