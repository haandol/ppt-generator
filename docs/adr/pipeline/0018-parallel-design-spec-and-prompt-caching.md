# 18. 디자인 스펙 병렬 생성, 프롬프트 캐싱 및 Adaptive Effort

Date: 2026-02-21

## Status

Partially superseded by [ADR-0039](./0039-remove-prompt-cache-and-warmup-full-parallel.md).

프롬프트 캐싱(섹션 6), 캐시 워밍업(섹션 7), 복잡도 기반 Adaptive Thinking Effort(섹션 5) 는 실측에서 `cacheRead=0` 재현으로 인해 제거됨. ThreadPoolExecutor 기반 병렬 생성(섹션 1~3) 과 결정론적 복잡도 추정(섹션 4) 의 로깅 목적은 그대로 유효.

## Context

디자인 스펙 생성은 슬라이드당 1회 LLM 호출(Claude Sonnet 4.6)이 필요하며, 10장 기준 순차 처리 시 수 분이 소요된다. 또한 모든 슬라이드가 동일한 시스템 프롬프트를 사용하므로 반복 전송에 따른 토큰 비용이 발생한다.

추가로 슬라이드를 순차 인덱스 순서로 thread pool에 제출하면, `arch_diagram` 같은 복잡한 슬라이드가 뒤에 제출되어 마지막 워커가 혼자 오래 걸리는 작업을 처리하면서 다른 워커들은 idle 상태가 된다. 단순한 슬라이드에도 `high` thinking effort를 사용하면 불필요한 토큰 소비 및 지연이 발생한다.

## Decision

### 1. ThreadPoolExecutor 기반 병렬 생성

`generate_slides_design_spec` 도구에서 `concurrent.futures.ThreadPoolExecutor`를 사용하여 슬라이드를 병렬 생성한다.

```
generate_slides_design_spec(project_id, total_slides=10)
    ├── Step 1: design_summary 사전 생성 (순차, 1회)
    ├── Step 2: ThreadPoolExecutor(max_workers=DESIGN_SPEC_PARALLEL)
    │     ├── worker[0]: slide_00 생성 + HTML 렌더링 + 파일 저장
    │     ├── worker[1]: slide_01 생성 + HTML 렌더링 + 파일 저장
    │     └── ...
    └── Step 3: slides.html 컨테이너 생성 (순차)
```

- **환경변수**: `DESIGN_SPEC_PARALLEL` (기본값: 8)로 최대 동시 워커 수 제어
- **실제 워커 수**: `min(DESIGN_SPEC_PARALLEL, 대상 슬라이드 수)`
- **부분 실패 허용**: 일부 슬라이드 실패 시 나머지는 정상 저장. 실패 슬라이드는 `slide_indices` 파라미터로 재시도 가능

### 2. 워커별 독립 Agent 인스턴스

strands `Agent`는 내부에 대화 히스토리 등 상태를 가지므로 스레드 간 공유가 안전하지 않다.

- `DIContainer.create_design_service()` 팩토리 메서드가 호출될 때마다 새 `Agent` + `DesignService` 인스턴스를 생성
- `design_service_factory` 콜백을 `register_design_tools()`에 주입
- 각 워커가 `design_service_factory()`를 호출하여 독립 인스턴스 사용

### 3. 메타데이터 파일 동시 쓰기 보호

`ProjectService.update_step()`은 `project.json` 파일을 읽고-수정-쓰기하므로 `threading.Lock`으로 보호한다. 디자인 스펙 슬라이드 파일(`slide_NN.json`)은 슬라이드 인덱스별로 독립 파일이므로 별도 Lock 없이 안전하다.

### 4. 결정론적 복잡도 추정 및 Longest-Job-First 스케줄링

`component_hint` + `content_summary` 길이로 복잡도 점수를 결정론적으로 산출하여 LPT(Longest Processing Time first) 전략을 적용한다.

```python
COMPONENT_HINT_COMPLEXITY: dict[str, int] = {
    "arch_diagram": 10,  "process_flow": 9,   "pipeline": 8,
    "concept_list": 8,   "quote_code": 7,     "vs_comparison": 7,
    "summary_grid": 7,   "step_cards": 6,     "info_cards": 6,
    "code_block": 5,     "two_column": 5,     "feature_list": 4,
    "agenda": 3,         "cta": 3,            "bullets": 2,
    "quote": 1,
}

def estimate_slide_complexity(slide: SlideOutline) -> int:
    if slide.slide_type in ("title", "closing"):
        return 1
    base = COMPONENT_HINT_COMPLEXITY.get(slide.component_hint, 2)
    content_bonus = min(len(slide.content_summary) // 200, 3)
    return base + content_bonus  # 범위: 1~13
```

Thread pool에 슬라이드를 제출할 때 복잡도 내림차순으로 정렬하여 makespan을 최소화한다.

### 5. 복잡도 기반 Adaptive Thinking Effort

복잡도 점수에 따라 LLM의 thinking effort를 동적으로 조절한다.

| 복잡도 범위 | thinking_effort | 대상 |
|------------|-----------------|------|
| 9~13 (high) | `high` | arch_diagram, process_flow 등 |
| 4~8 (medium) | `medium` | pipeline, concept_list, step_cards, code_block 등 |
| 1~3 (low) | `low` | title, closing, bullets, quote, agenda 등 |

`DIContainer.create_design_service(thinking_effort, slide_type)` 팩토리가 effort와 slide_type을 인자로 받아 해당 설정의 Agent를 생성한다.

### 6. 프롬프트 캐싱

| 프로바이더 | 캐싱 방식 | 구현 |
|-----------|----------|------|
| **Bedrock** | `SystemContentBlock`에 `cachePoint` 직접 포함 + `CacheConfig(strategy="auto")`로 assistant 메시지 캐싱 | `_with_cache_point()` 헬퍼 + `BedrockModel` 파라미터 |
| **Anthropic** | `CachingAnthropicModel` — `format_request()` 오버라이드로 system 필드에 `cache_control: {"type": "ephemeral"}` 적용 | `AnthropicModel` 서브클래스 |

Bedrock의 `cache_prompt` 파라미터는 deprecated이므로, Agent 생성 시 `system_prompt`를 `[{"text": "..."}, {"cachePoint": {"type": "default"}}]` 형태의 `SystemContentBlock` 리스트로 전달한다.

### 7. 캐시 워밍업 (Cache Warmup)

Bedrock prompt caching은 동일 계정·모델·prefix 기준으로 서버 측에서 캐시되지만, **첫 번째 요청의 응답이 완료된 후**에야 캐시가 생성된다. 모든 슬라이드를 동시에 병렬 시작하면 첫 완료 전에 나머지도 이미 처리 중이므로 전부 `cache_write`만 발생하고 `cache_read`가 없다.

또한 Bedrock의 캐시 키는 `additionalModelRequestFields`를 포함하므로, **thinking effort가 다르면 동일한 시스템 프롬프트라도 별도의 캐시로 취급**된다. 따라서 content 슬라이드를 effort별로 그룹핑하여 각 그룹에서 1개씩 워밍업해야 cache hit를 극대화할 수 있다.

```
generate_slides_design_spec(project_id, total_slides=10)
    ├── Step 1: design_summary 사전 생성 (순차, 1회)
    ├── Step 2: cache warmup — content 슬라이드를 effort별로 1개씩 순차 생성
    │     ├── effort=low 워밍업 (해당 그룹 2개 이상일 때)
    │     ├── effort=medium 워밍업 (해당 그룹 2개 이상일 때)
    │     └── effort=high 워밍업 (해당 그룹 2개 이상일 때)
    ├── Step 3: ThreadPoolExecutor — 나머지 슬라이드 병렬 생성 (effort별 cache_read 활용)
    └── Step 4: slides.html 컨테이너 생성 (순차)
```

- content system prompt가 ~12,852 토큰으로 가장 크므로 content를 워밍업 대상으로 선택
- title/closing은 system prompt가 다르므로(~4,400 토큰) content 캐시와 무관
- 각 effort 그룹에 슬라이드가 1개만 있으면 워밍업 스킵 (캐시를 읽을 후속 슬라이드가 없으므로)
- content 슬라이드가 1개 이하면 워밍업 없이 즉시 병렬 처리

## Consequences

### Positive

- **처리 시간 단축**: 10장 기준 순차 ~5분 → 병렬 ~1분 (워커 8개 기준)
- **Wall-clock time 최적화**: 복잡한 슬라이드가 먼저 시작되어 워커 idle time 감소
- **토큰 비용 절감**: 시스템 프롬프트 캐싱 + 캐시 워밍업으로 cache_read 극대화 + 단순 슬라이드에 `low` effort 사용
- **품질 유지**: 복잡한 슬라이드는 여전히 `high` effort로 충분한 추론 수행
- **부분 실패 복구**: 실패 슬라이드만 `slide_indices`로 재시도 가능
- **스레드 안전**: Agent 인스턴스 격리 + 메타데이터 Lock으로 race condition 방지

### Negative

- **메모리 사용량 증가**: 워커당 독립 Agent/boto3 클라이언트 인스턴스 생성
- **API 쓰로틀링 위험**: 동시 요청 수가 많으면 rate limit에 도달 가능 (`DESIGN_SPEC_PARALLEL`로 제어)
- **복잡도 추정 오차**: `component_hint` 기반 정적 매핑이므로 실제 내용에 따라 난이도가 다를 수 있음
- **캐시 최소 토큰 요건**: Anthropic prompt caching은 시스템 프롬프트가 최소 1,024 토큰 이상이어야 활성화됨
- **캐시 워밍업 지연**: effort별 content 슬라이드를 순차 생성하므로 전체 wall-clock time이 워밍업 슬라이드 수만큼 증가 (최대 3개, 각 effort 그룹에서 가장 단순한 슬라이드 선택으로 최소화)

## References

- 병렬 생성 구현: `src/ppt_generator/tools/design/controller.py` — `generate_slides_design_spec()`
- 병렬 러너: `src/ppt_generator/tools/design/parallel_runner.py`
- 팩토리 메서드: `src/ppt_generator/di/container.py` — `create_design_service(thinking_effort, slide_type)`
- Bedrock 캐싱: `src/ppt_generator/di/container.py` — `_create_bedrock_model()` (`cache_config`)
- Anthropic 캐싱: `src/ppt_generator/di/container.py` — `CachingAnthropicModel`
- 메타데이터 Lock: `src/ppt_generator/tools/project/service.py` — `_metadata_lock`
- 복잡도 매핑: `src/ppt_generator/interfaces/constants.py` — `COMPONENT_HINT_COMPLEXITY`, `DESIGN_SPEC_PARALLEL`
- 복잡도 추정/변환 함수: `src/ppt_generator/interfaces/utils.py` — `estimate_slide_complexity()`, `complexity_to_thinking_effort()`
- 테스트: `tests/test_complexity.py`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0014-file-based-communication-and-per-slide-crud](./0014-file-based-communication-and-per-slide-crud.md), [0020-token-usage-tracking-and-cost-estimation](./0020-token-usage-tracking-and-cost-estimation.md)
