# Visual QA 2-Phase 모델 분리 (Haiku 분석 + Sonnet 수정)

Date: 2026-04-15

## Status

Superseded by [offload/0001](../offload/0001-client-llm-offload-plugin.md)

Visual QA 의 분석·수정 LLM 호출이 클라이언트로 오프로딩되면서 서버가 모델을 고르지
않게 되었다. Haiku(분석)/Sonnet(수정) 이원화는 제거되었고, 스크린샷 캡처(Playwright)만
서버에 남았다. 어떤 모델로 분석·수정할지는 이제 클라이언트가 결정한다. 아래는 오프로딩
이전의 기록이다.

## Context

현재 Visual QA는 분석(analysis)과 수정(fix) 모두 Sonnet 4.6을 사용한다.
분석 단계는 스크린샷에서 시각적 이슈를 감지하는 분류 작업으로 Haiku로도 충분하며,
수정 단계만 정밀한 좌표/레이아웃 조정이 필요하여 Sonnet이 적합하다.

Sonnet 대비 Haiku는 비용이 ~5배 저렴하고 응답 속도가 빠르므로,
분석을 Haiku로 전환하면 비용 절감과 속도 향상을 동시에 달성할 수 있다.

## Decision

Visual QA를 2-Phase로 분리한다:

- **Phase 1 (분석)**: 전체 슬라이드를 Haiku로 병렬 분석하여 이슈 감지
- **Phase 2 (수정)**: 이슈가 발견된 슬라이드만 Sonnet으로 수정

### Technical Details

1. **model_factory.py**: 분석용 Haiku 모델 팩토리 `create_bedrock_visual_qa_analysis_model()` / `create_anthropic_visual_qa_analysis_model()` 추가. 기존 `create_bedrock_visual_qa_model()` / `create_anthropic_visual_qa_model()`은 수정(fix)용으로 유지.

2. **container.py**: `_create_visual_qa_analysis_agent()`가 Haiku 모델을 사용하도록 변경. `_create_visual_qa_fix_agent()`는 기존 Sonnet 모델 유지.

3. **service.py 흐름 변경 없음**: 기존 `run_qa()`의 iteration 루프 구조는 이미 분석→수정 2단계로 분리되어 있으므로, agent factory만 교체하면 동작한다.

### Acceptance Criteria

- 분석(analysis) 단계가 Haiku 모델로 실행된다
- 수정(fix) 단계는 Sonnet 모델로 유지된다
- 기존 iteration 루프 구조는 변경되지 않는다
- 기존 테스트가 통과한다

## Consequences

- **긍정적**: 분석 비용 ~80% 절감 (Sonnet input $3/1M → Haiku input $0.80/1M)
- **긍정적**: 분석 속도 향상 (Haiku의 빠른 응답)
- **부정적**: 분석 정확도가 소폭 하락할 가능성 (모니터링 필요)

## References

- 0002: Visual QA 브라우저 도구 fallback
