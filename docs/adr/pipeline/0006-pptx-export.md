# 6. PPTX 내보내기 (F5)

Date: 2026-02-11

## Status

Superseded by [ADR-0013](./0013-design-spec-pipeline.md)

## Summary

레거시 HTML → PPTX 변환 경로는 제거되었다. HTML 세션 기반의 DOM 추출/LLM 변환/룰 기반 폴백 체인은 삭제되었다. 현재 `export_pptx`는 디자인 스펙(PptxSlideSpec JSON)에서 SlideBuilder를 직접 호출하여 PPTX를 생성하는 단일 경로만 지원한다. `session_id` 파라미터, Playwright 의존성, BeautifulSoup 의존성 등 관련 모듈이 모두 삭제되었다.

### 현재 구현

[ADR-0013](./0013-design-spec-pipeline.md) 참조. DesignSpec → SlideBuilder 직접 호출 → PPTX.

### MCP Tool Interface

| 항목 | 값 |
|------|-----|
| Tool | `export_pptx` |
| 입력 | `design_spec_json: str` (디자인 스펙 경로), `project_id: str` (선택) |
| 출력 | `project_id`와 `.pptx` 파일 경로를 포함하는 JSON |

## References

- 현재 구현: `src/ppt_generator/tools/pptx/service.py` — `ExportService.export_from_design_spec()`
- 슬라이드 빌더: `src/ppt_generator/tools/pptx/slide_builder.py` — `SlideBuilder`
- 스키마: `src/ppt_generator/interfaces/schemas.py` — `DesignSpec`, `PptxSlideSpec`, `PptxTextBox`, `PptxShape`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md)
- ALPS: Section 7.5
