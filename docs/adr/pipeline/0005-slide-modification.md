# 5. 슬라이드 수정 (F4)

Date: 2026-02-11

## Status

Superseded by [ADR-0013](./0013-design-spec-pipeline.md) + [ADR-0014](./0014-file-based-communication-and-per-slide-crud.md)

## Summary

`modify_slides` 도구는 제거되었다. HTML 슬라이드를 LLM으로 직접 수정하는 기존 방식은 디자인 스펙 수준에서 수정하는 `modify_design_spec` 도구로 대체되었다. 디자인 스펙을 수정한 후 `export_html`로 HTML을 재생성하는 방식이 더 정확하고 일관된 결과를 제공한다.

## References

- 대체 구현: `src/ppt_generator/tools/design/controller.py` — `modify_design_spec` MCP 도구
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0014-file-based-communication-and-per-slide-crud](./0014-file-based-communication-and-per-slide-crud.md)
- ALPS: Section 7.4
