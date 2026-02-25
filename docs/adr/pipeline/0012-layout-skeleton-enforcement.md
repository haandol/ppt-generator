# 12. 레이아웃 골격(Skeleton) 기반 위치 강제

Date: 2026-02-11

## Status

Superseded by [ADR-0013](./0013-design-spec-pipeline.md)

## Summary

레거시 HTML 기반 골격 생성 경로는 제거되었다. `build_layout_skeleton()`, `LAYOUT_REGIONS`, `_validate_region_styles()`, `_detect_layout_index_from_html()` 등 관련 코드가 모두 삭제되었다. 현재는 디자인 스펙 파이프라인(ADR-0013)에서 LLM이 PptxSlideSpec JSON으로 좌표를 직접 생성하므로, 골격 기반 위치 강제가 불필요하다.

### 기존 접근 (제거됨)

- `LAYOUT_REGIONS` 좌표를 사용하여 `position:absolute` div 골격을 코드로 생성
- LLM은 각 `data-region` div 내부 컨텐츠만 채움
- `_validate_region_styles()`로 좌표 검증/복원하는 이중 안전장치

## References

- 대체 구현: [ADR-0013 디자인 스펙 파이프라인](./0013-design-spec-pipeline.md)
- ALPS: Section 7.3, Section 7.5
