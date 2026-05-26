# Design Spec Examples

ADR-0049 5단 계층(Project / Slide / Layout / Section / Content)을 충실히 따르는
슬라이드 design spec 예시 모음. 현재는 인-컨텍스트 학습용 reference 자료이며
프롬프트 빌더가 자동 주입하지 않는다 (base prompt 가 inline `<examples>` 블록을
유지). 향후 동적 예시 주입이 필요해지면 이 폴더를 loader 가 읽는다.

각 예시는:
- `grid_layout` + `cell_assignment` (Layout 계층)
- `design_doc.layout` 트리 (Section 계층, bbox + parent_id)
- `textboxes` / `shapes` (Content 계층, `grid_cell` + `component_id` 링크)
를 모두 포함한다.

## 파일

- `two_column_diagram.json` — 2열 레이아웃: 좌측 설명 카드 + 우측 다이어그램.
  Section 트리 depth 2~3 활용 사례 (right_diagram 안에 functions 그룹).
