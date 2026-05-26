# load_outline에 include_content 파라미터 추가

Date: 2026-04-27

## Status

Accepted

## Context

기존 `load_outline` MCP 도구는 outline 경로(path)만 반환한다. MCP 클라이언트가 아웃라인 내용을 확인하려면 반환된 경로의 파일을 직접 읽어야 하는데, MCP 프로토콜에서는 파일 시스템 접근이 도구를 통해서만 가능하므로 별도 도구 호출이 필요하다.

두 가지 접근 방식을 검토했다:
1. **기존 도구에 optional 파라미터 추가**: `load_outline(project_id, include_content=False)`
2. **별도 도구 분리**: `load_outline` + `load_outline_content`

Anthropic의 도구 설계 가이드라인에 따르면:
- 같은 도메인의 상세도만 다른 경우 별도 도구로 분리하지 않고, response format 플래그로 제어
- 도구 수가 적을수록 LLM의 tool selection 정확도가 높음
- 거의 동일한 이름의 도구 두 개는 모호성을 유발

## Decision

`load_outline` 도구에 `include_content: bool = False` 파라미터를 추가한다.

- `include_content=False` (기본값): 기존과 동일하게 `outline_path`만 반환
- `include_content=True`: `outline_path`와 함께 각 슬라이드의 아웃라인 내용(`slides` 배열)을 반환

### 응답 형식

```json
// include_content=False (기본)
{
  "outline_path": "/path/to/outline",
  "slide_count": 8
}

// include_content=True
{
  "outline_path": "/path/to/outline",
  "slide_count": 8,
  "slides": [
    {
      "slide_index": 0,
      "title": "...",
      "content_summary": "...",
      "component_hint": "...",
      "slide_type": "...",
      "speaker_notes": "...",
      "layout_plan": "..."
    }
  ]
}
```

기존 호출은 파라미터 변경 없이 동일하게 동작하므로 하위 호환성이 유지된다.

## Consequences

### Positive

- MCP 클라이언트가 단일 도구 호출로 아웃라인 내용 확인 가능
- 기존 호출과 하위 호환
- 도구 수 증가 없이 기능 확장

### Negative

- `include_content=True` 시 응답 크기 증가 (슬라이드 수에 비례)
