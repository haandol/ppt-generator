# 파이프라인 전체 진행률 보고 및 로깅 강화

Date: 2026-04-15

## Status

Accepted

## Context

`generate_slides_design_spec` 호출이 10~20분 이상 소요될 수 있는데, 현재 MCP progress 보고가 디자인 스펙 병렬 생성 단계에만 한정되어 있어 사용자가 파이프라인이 멈춘 것인지 진행 중인지 구분할 수 없다.

### 현재 상태

| 단계 | MCP progress | 로그 |
|------|-------------|------|
| generate_outline | ❌ 없음 | 토큰 사용량만 INFO |
| generate_script | ❌ 없음 | 토큰 사용량만 INFO |
| design_summary 사전 생성 | ✅ 완료 시 1회 | INFO |
| 슬라이드 병렬 생성 | ✅ 슬라이드 완료 시 N회 | 시작/완료/실패 INFO |
| export_html | ❌ 없음 | 컨테이너 생성 INFO |

### 해결해야 할 문제

1. **진행 여부 불투명**: outline/script 생성 중에는 아무런 피드백이 없어 20분 멈춤과 구분 불가
2. **단계 전환 불투명**: 현재 어느 단계를 실행 중인지 MCP 클라이언트에서 확인 불가
3. **로그 상세도 부족**: outline/script/export_html 단계의 시작/소요시간 로그가 없음

## Decision

### 1. MCP `report_progress` 전체 파이프라인 확장

`generate_slides_design_spec` 핸들러에서 전체 파이프라인 단계를 아우르는 progress를 보고한다. 현재 이 핸들러가 이미 `ctx: Context | None`을 받고 있으므로, 기존 구조를 확장한다.

**변경 범위**: `handle_generate()` 내부에서 각 주요 단계 진입/완료 시 progress 보고 추가

```
[Step 1] design_summary 사전 생성 중...
[Step 2] 슬라이드 디자인 생성 중 (1/10 완료)...
[Step 2] 슬라이드 디자인 생성 중 (10/10 완료)
[Step 3] HTML 내보내기 완료
```

`generate_outline`과 `generate_script`는 별도 MCP 도구 호출이므로 (한 번의 `generate_slides_design_spec` 내에서 호출되지 않음), 각 컨트롤러에 `ctx` 파라미터를 추가하여 독립적으로 progress를 보고한다.

### 2. outline/script 컨트롤러에 `ctx` 주입 및 progress 보고

`generate_outline`과 `generate_script` 도구에 `ctx: Context | None = None` 파라미터를 추가한다.

- **generate_outline**: LLM 호출 전 `"아웃라인 생성 중..."`, 완료 후 `"아웃라인 생성 완료"`
- **generate_script**: LLM 호출 전 `"스크립트 생성 중..."`, 완료 후 `"스크립트 생성 완료"`

단일 LLM 호출이므로 total=1로 시작/완료 2회 보고한다.

### 3. design_spec 핸들러 progress 메시지 개선

기존 progress 메시지를 더 명확하게 개선한다:

- design_summary 생성 전: `"디자인 테마 생성 중..."`
- design_summary 생성 후: 기존 메시지 유지
- 슬라이드 병렬 생성 중: 기존 `"슬라이드 N/M 완료"` 유지
- HTML 컨테이너 생성 후: `"HTML 내보내기 완료"` 추가

### 4. 로깅 강화

각 단계에 시작/완료/소요시간 로그를 추가한다:

- **outline controller**: `"outline 생성 시작"`, `"outline 생성 완료 (%.1fs, slides=%d)"`
- **script controller**: `"script 생성 시작"`, `"script 생성 완료 (%.1fs, slides=%d)"`
- **design_spec handler**: design_summary 시작 로그에 소요시간 추가
- **export_html controller**: `"HTML export 시작 (slides=%d)"`, `"HTML export 완료 (%.1fs)"`

## Consequences

### 장점

- 사용자가 Claude Code UI에서 모든 파이프라인 단계의 진행 상황을 실시간 확인 가능
- 파이프라인이 멈춘 것인지 진행 중인지 즉시 구분 가능
- `PPT_LOG_DIR`/`PPT_LOG_FILE` 설정 시 각 단계의 소요시간을 로그로 확인 가능
- 기존 병렬 생성의 progress 보고 구조를 그대로 활용하므로 변경 최소화

### 단점

- outline/script 컨트롤러 시그니처에 `ctx` 파라미터 추가 (MCP FastMCP가 자동 주입하므로 호환성 문제 없음)

## Related

- [design/0003 (design): 디자인 스펙 병렬 생성, 프롬프트 캐싱 및 Adaptive Effort](../design/0003-parallel-design-spec.md)
- [0003: 토큰 사용량 추적 및 비용 추정](./0003-token-usage-cost-estimation.md)
