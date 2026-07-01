# Design Spec Post-Generation LLM Review

Date: 2026-04-02

## Status

Accepted

## Context

디자인 스펙 생성 시 LLM이 프롬프트 규칙(폰트 크기 하한, 카드 높이 균일성, 좌우 영역 일관성 등)을 위반하는 경우가 빈번하다. 특히 복잡한 레이아웃(two_column, arch_diagram 등)에서 공간이 부족하면 LLM이 임의로 폰트를 10pt까지 줄이거나, 수직 스택 카드 간 겹침/마진 불일치를 만드는 문제가 반복된다.

현재 대응 방식의 한계:
- **프롬프트 규칙 강화**: 규칙을 추가해도 LLM이 무시하는 경우가 있음
- **서버 사이드 validation**: 하드코딩된 규칙은 edge case가 많고, 잘못된 자동 수정으로 레이아웃을 오히려 망칠 리스크가 큼
- **Visual QA**: 렌더링 후 스크린샷 기반으로 정확하지만, opt-in이고 Playwright 의존성 필요

디자인 스펙 JSON 단계에서 LLM 리뷰를 추가하면, 렌더링 없이도 규칙 위반을 감지하고 재생성할 수 있다.

## Decision

디자인 스펙 생성 직후 LLM 리뷰 단계를 둔다. 리뷰 태스크 조립과 결과 검증은 서버가
`prepare_review` / `ingest_review` 쌍으로 소유하고, 리뷰 판단(토큰 생성)은 클라이언트 LLM이
수행한다 ([offload/0001](../offload/0001-client-llm-offload-plugin.md)).

### 핵심 설계

1. **디자인 스펙 JSON 단계 리뷰**: 렌더링 없이 spec JSON 만으로 규칙 위반을 감지한다 — Visual QA(픽셀 렌더링 결함)와 목적이 다르다.
2. **lint 힌트 전달**: 기계적 lint 결과를 리뷰 프롬프트에 힌트로 실어, LLM 판단이 결정론적 검사와 어긋나지 않게 한다.
3. **슬라이드 단위 stateless**: 슬라이드별로 독립적인 prepare→생성→ingest 체인이라, 여러 슬라이드 리뷰를 클라이언트가 병렬로 진행한다.
4. **재생성 정책**: 리뷰에서 high severity 이슈가 나오면 해당 슬라이드만 1회 재생성하도록 유도한다(`ingest_review` 는 재생성을 자동 수행하지 않고 fix 피드백만 돌려준다). 재생성 후 재리뷰는 하지 않는다 — 무한 루프 방지.

### 리뷰 체크리스트

| 항목 | 기준 | Severity |
|------|------|----------|
| 폰트 크기 하한 | 카드 제목 < 18pt, 카드 본문 < 16pt, 섹션 라벨 < 14pt, 모든 텍스트 < 10pt | high |
| 좌우 폰트 일관성 | 동일 역할 텍스트의 좌우 영역 간 폰트 크기 차이 > 4pt | high |
| 수직 스택 겹침 | 인접 카드 간 gap < 0 (겹침) | high |
| 수직 스택 높이 균일 | 같은 열의 카드 height_px가 불균일 | medium |
| 수직 스택 간격 균일 | 같은 열의 카드 간 gap이 불균일 (최대-최소 > 4px) | medium |
| 좌우 bottom 정렬 | 좌우 영역의 bottom edge 차이 > 8px | medium |
| 요소 겹침 | 같은 레벨 요소 간 bounding box 겹침 | high |

### 리뷰 결과 처리

- **이슈 없음**: 그대로 저장, HTML 렌더링 진행
- **high severity 이슈 존재**: 해당 슬라이드를 1회 재생성하도록 fix 피드백을 반환 (원래 생성 파라미터 + 리뷰 피드백을 user prompt에 추가)
- **medium only**: 경고만 남기고 저장 진행 (minor 이슈는 Visual QA에서 잡을 수 있음)
- **재생성 후**: 재리뷰 없이 바로 저장 (최대 1회 재생성으로 제한)

### Alternatives Considered

1. **서버 사이드 하드코딩 validation**: 규칙이 정적이고 edge case 처리가 어려움. 잘못된 자동 수정 리스크가 큼.
2. **Visual QA로 통합**: 스크린샷 기반이라 정확하지만 Playwright 필수, opt-in, 비용이 더 높음. 디자인 스펙 리뷰와 목적이 다름 (JSON 규칙 준수 vs 픽셀 렌더링 결함).
3. **프롬프트만 강화**: 이미 시도했으나 LLM이 규칙을 무시하는 경우가 있어 한계가 명확함.

### Acceptance Criteria

- 디자인 스펙 생성 후 슬라이드에 대해 `prepare_review` → `ingest_review` 리뷰가 수행됨
- 리뷰에서 high severity 이슈 발견 시 `ingest_review` 가 재생성용 fix 피드백을 반환함
- lint 결과가 리뷰 프롬프트에 힌트로 전달됨
- 기존 테스트가 깨지지 않음

### Out of Scope

- 리뷰 후 자동 수정 (재생성으로 대체, 리뷰 LLM이 직접 수정하지 않음)
- 리뷰 비활성화 옵션 (필수이므로 비활성화 불가)
- Visual QA 대체 (목적이 다르므로 별도 유지)

## Consequences

### 긍정적

- 폰트 크기 위반, 겹침 등 반복적인 규칙 위반을 렌더링 전에 감지
- 슬라이드 단위 stateless 라 클라이언트가 리뷰를 병렬로 진행 가능
- Visual QA 실행 전에 명백한 결함을 제거하여 Visual QA 효율 향상

### 부정적

- 슬라이드당 1회 추가 LLM 호출 (리뷰) + 이슈 시 1회 재생성 = 최대 2회 추가 호출
- 리뷰가 false positive를 반환할 경우 불필요한 재생성 발생 가능

## Related

- [design/0003](./0003-parallel-design-spec.md) — 디자인 스펙 생성 흐름 (Superseded by offload/0001)
- [visual-qa/0001](../visual-qa/0001-visual-qa-pipeline.md) — 픽셀 렌더링 결함을 잡는 별도 QA
- [offload/0001](../offload/0001-client-llm-offload-plugin.md) — 리뷰의 LLM 호출이 클라이언트로 이동
