# 4. HTML 슬라이드 생성 (F3)

Date: 2026-02-11

## Status

Superseded by [ADR-0013](./0013-design-spec-pipeline.md)

## Summary

레거시 자유형식 HTML 생성 경로는 제거되었다. LLM이 직접 HTML을 생성하는 기존 방식(아웃라인 → 골격 → LLM 콘텐츠 채우기 → 좌표 검증)은 ADR-0013의 디자인 스펙 파이프라인으로 대체되었다. 현재 `export_html`는 디자인 스펙(PptxSlideSpec JSON)을 결정론적으로 HTML로 변환하는 단일 경로만 지원한다.

### 기존 접근 (제거됨)

- LLM이 `LAYOUT_REGIONS` 좌표 기반 `position:absolute` div 골격 내부 컨텐츠를 채우는 방식
- `build_layout_skeleton()`, `_validate_region_styles()`, `css_inliner.py`, `slides_prompts.py` 등 관련 코드 삭제

### 현재 구현

[ADR-0013](./0013-design-spec-pipeline.md) 참조. DesignSpec → position:absolute HTML 결정론적 변환 (LLM 미사용).

### MCP Tool Interface

| 항목 | 값 |
|------|-----|
| Tool | `export_html` |
| 입력 | `design_spec_json: str` (선택) 또는 `project_id: str` (선택, 디자인 스펙 자동 로드) |
| 출력 | session_id, slides_html_path, project_id를 포함하는 JSON |

## References

- 현재 구현: `src/ppt_generator/tools/slides/` (controller.py, service.py)
- HTML 렌더러: `src/ppt_generator/tools/slides/html_renderer.py`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0016-per-slide-html-iframe](./0016-per-slide-html-iframe.md)
- ALPS: Section 7.3
