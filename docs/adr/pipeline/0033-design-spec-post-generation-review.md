# ADR-0033: Design Spec Post-Generation LLM Review

Date: 2026-04-02

## Status

Proposed

## Context

디자인 스펙 생성 시 LLM이 프롬프트 규칙(폰트 크기 하한, 카드 높이 균일성, 좌우 영역 일관성 등)을 위반하는 경우가 빈번하다. 특히 복잡한 레이아웃(two_column, arch_diagram 등)에서 공간이 부족하면 LLM이 임의로 폰트를 10pt까지 줄이거나, 수직 스택 카드 간 겹침/마진 불일치를 만드는 문제가 반복된다.

현재 대응 방식의 한계:
- **프롬프트 규칙 강화**: 규칙을 추가해도 LLM이 무시하는 경우가 있음
- **서버 사이드 validation**: 하드코딩된 규칙은 edge case가 많고, 잘못된 자동 수정으로 레이아웃을 오히려 망칠 리스크가 큼
- **Visual QA**: 렌더링 후 스크린샷 기반으로 정확하지만, opt-in이고 Playwright 의존성 필요

디자인 스펙 JSON 단계에서 LLM 리뷰를 추가하면, 렌더링 없이도 규칙 위반을 감지하고 재생성할 수 있다.

## Decision

디자인 스펙 생성 직후 **필수(mandatory)** LLM 리뷰 단계를 추가한다.

### 핵심 설계

1. **필수 실행**: Visual QA와 달리 opt-in이 아니라, 모든 디자인 스펙 생성 후 자동 실행
2. **모델**: Adaptive thinking 없는 Sonnet (비용/속도 절감, 리뷰는 단순 체크리스트 판단이므로 thinking 불필요)
3. **프롬프트 캐싱 활용**: 디자인 스펙 생성 시스템 프롬프트(design_system_content.prompt.md 등)와 동일한 규칙을 참조하므로, system prompt에 캐시 마커를 적용하여 cache hit로 비용 절감
4. **병렬 실행**: 슬라이드별 생성 직후 동일 스레드에서 리뷰 실행 (기존 병렬 구조 활용)
5. **재생성 정책**: 리뷰에서 high severity 이슈 발견 시 해당 슬라이드만 1회 재생성. 재생성 후 재리뷰는 하지 않음 (무한 루프 방지)

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
- **high severity 이슈 존재**: 해당 슬라이드를 1회 재생성 (원래 생성과 동일 파라미터 + 리뷰 피드백을 user prompt에 추가)
- **medium only**: 로그 경고만 남기고 저장 진행 (minor 이슈는 Visual QA에서 잡을 수 있음)
- **재생성 후**: 재리뷰 없이 바로 저장 (최대 1회 재생성으로 제한)

### 토큰 비용 추정

- 리뷰 input: system prompt (~5K tokens, 캐시 hit 시 90% 절감) + slide spec JSON (~2K tokens)
- 리뷰 output: ~200 tokens (체크리스트 결과 JSON)
- 슬라이드당 추가 비용: 캐시 hit 시 ~$0.003, 캐시 miss 시 ~$0.02
- 재생성 발생 시: 기존 생성 비용과 동일한 비용이 1회 추가

### Alternatives Considered

1. **서버 사이드 하드코딩 validation**: 규칙이 정적이고 edge case 처리가 어려움. 잘못된 자동 수정 리스크가 큼.
2. **Visual QA로 통합**: 스크린샷 기반이라 정확하지만 Playwright 필수, opt-in, 비용이 더 높음. 디자인 스펙 리뷰와 목적이 다름 (JSON 규칙 준수 vs 픽셀 렌더링 결함).
3. **프롬프트만 강화**: 이미 시도했으나 LLM이 규칙을 무시하는 경우가 있어 한계가 명확함.

### Acceptance Criteria

- 디자인 스펙 생성 후 모든 슬라이드에 대해 LLM 리뷰가 자동 실행됨
- 리뷰에서 high severity 이슈 발견 시 해당 슬라이드가 1회 재생성됨
- Adaptive thinking 없는 Sonnet 모델 사용
- 프롬프트 캐싱이 적용되어 system prompt가 캐시됨
- 리뷰 결과(이슈 수, 재생성 여부)가 generate_slides_design_spec 응답에 포함됨
- 토큰 사용량이 기존 추적 시스템에 합산됨
- 기존 테스트가 깨지지 않음

### Out of Scope

- 리뷰 후 자동 수정 (재생성으로 대체, 리뷰 LLM이 직접 수정하지 않음)
- 리뷰 비활성화 옵션 (필수이므로 비활성화 불가)
- Visual QA 대체 (목적이 다르므로 별도 유지)

## Consequences

### 긍정적

- 폰트 크기 위반, 겹침 등 반복적인 규칙 위반을 렌더링 전에 감지
- 프롬프트 캐싱으로 추가 비용이 최소화됨
- 기존 병렬 구조를 활용하므로 latency 증가가 제한적
- Visual QA 실행 전에 명백한 결함을 제거하여 Visual QA 효율 향상

### 부정적

- 슬라이드당 1회 추가 LLM 호출 (리뷰) + 이슈 시 1회 재생성 = 최대 2회 추가 호출
- 전체 생성 시간이 약간 증가 (리뷰 ~2-3초/슬라이드)
- 리뷰가 false positive를 반환할 경우 불필요한 재생성 발생 가능

## References

- ADR-0018: 디자인 스펙 병렬 생성, 프롬프트 캐싱 및 Adaptive Effort
- ADR-0026: Visual QA Pipeline
