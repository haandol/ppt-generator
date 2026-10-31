# Design Spec Examples

슬라이드 응답과 선 좌표의 검증 가능한 예시다. `two_column`에만 해당 레이아웃
예시를 붙이며, 다른 구성에 두 열 배치를 유도하지 않는다. 선 방향 예시는 생성·부분
수정·시각 분석이 공유한다. 예시의 좌표와 스타일은 그대로 복사할 레시피가 아니다.

전체 슬라이드 예시는:
- `grid_layout` + `cell_assignment` (Layout 계층)
- `design_doc.layout` 트리 (Section 계층, parent_id; bbox는 서버가 파생)
- `textboxes` / `shapes` (Content 계층, `grid_cell` + `component_id` 링크)
를 모두 포함한다.

## 파일

- `two_column_diagram.json` — 2열 레이아웃: 좌측 설명 카드 + 우측 다이어그램.
  Section 트리 depth 2~3 활용 사례 (right_diagram 안에 functions 그룹).
- `line_directions.json` — 위·왼쪽·대각선으로 향하는 선과 얕은 대각선. ShapeOutput
  검증 후 실제 HTML·PPTX의 시작·끝점과 비교한다.
