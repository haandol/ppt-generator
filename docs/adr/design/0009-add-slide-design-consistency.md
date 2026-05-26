# 슬라이드 추가 시 기존 디자인 스펙 참조를 통한 일관성 향상

Date: 2026-04-03

## Status

Superseded (2026-04-15)

> **Superseded reason**: `reference_specs`(인접 슬라이드의 전체 design spec JSON)를 프롬프트에 포함하면
> LLM이 reference의 좌표/요소를 그대로 재현하려 output tokens가 2-4배(38K-58K) 증가하여
> 슬라이드 1장 추가에 ~10분이 소요되는 성능 문제를 유발했다.
> Bulk 경로(`generate_slides_design_spec`)는 `reference_specs` 없이 `design_summary`만으로
> 충분한 일관성을 유지하고 있으므로 reference_specs를 제거한다.
> `adjacent_context`(prev/next outline) 전달은 유지된다.

## Context

`modify_design_spec(action="add")`로 슬라이드를 추가할 때, LLM에 전달되는 디자인 컨텍스트가 부족하여 기존 슬라이드와 시각적 일관성이 떨어지는 문제가 있다.

현재 전달되는 정보:
- `design_summary`: 배경색, 텍스트 색상, 폰트 크기, 카드 색상 등의 요약 정보
- `color_theme`: dark/light 모드

전달되지 않는 정보:
- 인접 슬라이드의 아웃라인 (`prev_outline`, `next_outline`) — 병렬 생성 시에는 전달되지만, 단일 추가 시에는 누락됨
- 기존 슬라이드의 실제 디자인 스펙 — 구체적인 좌표, 폰트, 색상, 레이아웃 패턴을 LLM이 직접 참고할 수 없음

`design_summary`만으로는 추상적인 테마 정보만 전달되므로, 추가된 슬라이드가 기존 슬라이드와 좌표 배치, 패딩, 요소 간격 등에서 불일치하는 경우가 발생한다.

## Decision

슬라이드 추가 시 LLM 프롬프트에 기존 디자인 스펙 샘플을 포함하여 디자인 일관성을 향상시킨다.

### Technical Details

1. **인접 슬라이드 아웃라인 전달 보완**: `_add_slide()`에서 `prev_outline`, `next_outline`을 로드하여 `generate_single_slide()`에 전달한다. 이미 인프라가 구현되어 있으므로 호출부만 수정한다.

2. **기존 디자인 스펙 샘플 전달**: 삽입 위치 인접의 기존 디자인 스펙(최대 2개: 앞/뒤) JSON을 로드하여 프롬프트에 `<reference_specs>` 섹션으로 포함한다. LLM이 실제 좌표, 폰트 크기, 색상, 패딩, 레이아웃 패턴을 직접 참고할 수 있다.

3. **프롬프트 업데이트**: `design_batch_user.prompt.md` 템플릿에 `{reference_specs}` 플레이스홀더를 추가한다. 레퍼런스 스펙이 없으면 빈 문자열로 대체한다.

4. **토큰 절약**: 레퍼런스 스펙에서 `speaker_notes`, `images` 필드를 제외하고 핵심 레이아웃 정보만 포함한다. 또한 content 타입 슬라이드만 레퍼런스로 선택하여 title/closing 슬라이드의 특수 레이아웃이 일반 슬라이드에 영향을 주지 않도록 한다.

### Alternatives Considered

- **design_summary 강화**: 좌표, 패딩 등 세부 정보를 design_summary에 추가하는 방안. 모든 슬라이드의 정보를 하나의 요약으로 압축하면 슬라이드별 레이아웃 다양성을 반영하기 어렵다.
- **전체 디자인 스펙 전달**: 모든 기존 슬라이드의 스펙을 전달하면 토큰 비용이 과도하게 증가한다.

### Acceptance Criteria

- 슬라이드 추가 시 인접 슬라이드의 아웃라인이 프롬프트에 포함된다
- 인접 content 슬라이드(최대 2개)의 디자인 스펙이 레퍼런스로 프롬프트에 포함된다
- 기존 병렬 생성 플로우에는 영향을 주지 않는다
- 레퍼런스 스펙에서 speaker_notes, images 필드가 제외된다

### Out of Scope

- update 액션에 대한 레퍼런스 스펙 전달 (추후 필요시 별도 ADR)
- 전체 슬라이드 디자인 스펙 전달 (토큰 비용 문제)

## Consequences

- **긍정적**: 추가된 슬라이드가 기존 슬라이드와 좌표, 패딩, 폰트, 색상 등에서 더 높은 일관성을 가짐
- **긍정적**: design_summary의 추상적 정보 + 실제 스펙의 구체적 정보가 상호보완
- **부정적**: 프롬프트 토큰 증가 (레퍼런스 스펙 2개 추가, 슬라이드당 약 1-3K 토큰)

## References

- ADR-0001 (modify): 파일 기반 통신, 슬라이드 단위 CRUD
- ADR-0003: 디자인 스펙 병렬 생성, 프롬프트 캐싱
- ADR-0004: 슬라이드 타입별 시스템 프롬프트 분리
