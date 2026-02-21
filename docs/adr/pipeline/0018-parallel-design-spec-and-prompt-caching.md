# 18. 디자인 스펙 병렬 생성 및 프롬프트 캐싱

Date: 2026-02-21

## Status

Accepted

## Context

디자인 스펙 생성은 슬라이드당 1회 LLM 호출(Claude Opus 4.6)이 필요하며, 10장 기준 순차 처리 시 수 분이 소요된다. 또한 모든 슬라이드가 동일한 시스템 프롬프트(~수천 토큰)를 사용하므로, 반복 전송에 따른 토큰 비용이 발생한다.

### 해결해야 할 문제

1. **처리 시간**: 슬라이드 N장 × 평균 30~60초/장 = 순차 처리 시 수 분 대기
2. **토큰 비용**: 동일한 시스템 프롬프트를 매 요청마다 전송
3. **스레드 안전성**: 병렬 처리 시 공유 리소스(메타데이터 파일, Agent 인스턴스) 접근 제어

## Decision

### 1. ThreadPoolExecutor 기반 병렬 생성

`generate_slides_design_spec` 도구에서 `concurrent.futures.ThreadPoolExecutor`를 사용하여 슬라이드를 병렬 생성한다.

```
generate_slides_design_spec(project_id, total_slides=10)
    ├── Step 1: design_summary 사전 생성 (순차, 1회)
    ├── Step 2: ThreadPoolExecutor(max_workers=DESIGN_SPEC_PARALLEL)
    │     ├── worker[0]: slide_00 생성 + HTML 렌더링 + 파일 저장
    │     ├── worker[1]: slide_01 생성 + HTML 렌더링 + 파일 저장
    │     ├── ...
    │     └── worker[N]: slide_NN 생성 + HTML 렌더링 + 파일 저장
    └── Step 3: slides.html 컨테이너 생성 (순차)
```

- **환경변수**: `DESIGN_SPEC_PARALLEL` (기본값: 8)로 최대 동시 워커 수 제어
- **실제 워커 수**: `min(DESIGN_SPEC_PARALLEL, 대상 슬라이드 수)`
- **부분 실패 허용**: 일부 슬라이드 실패 시 나머지는 정상 저장. 실패 슬라이드는 `slide_indices` 파라미터로 재시도 가능

### 2. 워커별 독립 Agent 인스턴스

strands `Agent`는 내부에 대화 히스토리 등 상태를 가지므로 스레드 간 공유가 안전하지 않다. 이를 해결하기 위해:

- `DIContainer.create_design_service()` 팩토리 메서드가 호출될 때마다 새 `Agent` + `DesignService` 인스턴스를 생성
- `design_service_factory` 콜백을 `register_design_tools()`에 주입
- 각 워커가 `design_service_factory()`를 호출하여 독립 인스턴스 사용

```python
# server.py
register_design_tools(
    mcp, container.design_service, container.project_service,
    container.slides_service,
    design_service_factory=container.create_design_service,
)

# controller.py — 워커 내부
svc = design_service_factory() if design_service_factory else design_service
spec = svc.generate_single_slide(...)
```

### 3. 메타데이터 파일 동시 쓰기 보호

`ProjectService.update_step()`은 `project.json` 파일을 읽고-수정-쓰기하므로 race condition이 발생할 수 있다. `threading.Lock`으로 보호한다.

```python
class ProjectService:
    def __init__(self):
        self._metadata_lock = Lock()

    def update_step(self, project_dir, step_name):
        with self._metadata_lock:
            metadata = self.load_metadata(project_dir)
            metadata.steps_completed[step_name] = datetime.now(...)
            self.save_metadata(project_dir, metadata)
```

디자인 스펙 슬라이드 파일(`slide_NN.json`)은 슬라이드 인덱스별로 독립 파일이므로 별도 Lock 없이 안전하다.

### 4. 프롬프트 캐싱

동일한 시스템 프롬프트의 반복 전송 비용을 줄이기 위해 프로바이더별 캐싱을 적용한다.

| 프로바이더 | 캐싱 방식 | 구현 |
|-----------|----------|------|
| **Bedrock** | `CacheConfig(strategy="auto")` — BedrockModel이 시스템 프롬프트, 메시지에 자동으로 cache point 주입 | `_create_bedrock_model()` 파라미터 |
| **Anthropic** | `CachingAnthropicModel` — `format_request()` 오버라이드로 system 필드에 `cache_control: {"type": "ephemeral"}` 적용 | `AnthropicModel` 서브클래스 |

## Consequences

### Positive

- **처리 시간 단축**: 10장 기준 순차 ~5분 → 병렬 ~1분 (워커 8개 기준)
- **토큰 비용 절감**: 시스템 프롬프트 캐싱으로 반복 입력 토큰 비용 감소
- **부분 실패 복구**: 실패 슬라이드만 `slide_indices`로 재시도 가능
- **스레드 안전**: Agent 인스턴스 격리 + 메타데이터 Lock으로 race condition 방지

### Negative

- **메모리 사용량 증가**: 워커당 독립 Agent/boto3 클라이언트 인스턴스 생성
- **API 쓰로틀링 위험**: 동시 요청 수가 많으면 Bedrock/Anthropic rate limit에 도달 가능 (`DESIGN_SPEC_PARALLEL`로 제어)
- **캐시 최소 토큰 요건**: Anthropic prompt caching은 시스템 프롬프트가 최소 1,024 토큰 이상이어야 활성화됨 (현재 디자인 스펙 시스템 프롬프트는 이 요건 충족)

## References

- 병렬 생성 구현: `src/ppt_generator/tools/design/controller.py` — `generate_slides_design_spec()`
- 팩토리 메서드: `src/ppt_generator/di/container.py` — `create_design_service()`
- Bedrock 캐싱: `src/ppt_generator/di/container.py` — `_create_bedrock_model()` (`cache_config`)
- Anthropic 캐싱: `src/ppt_generator/di/container.py` — `CachingAnthropicModel`
- 메타데이터 Lock: `src/ppt_generator/tools/project/service.py` — `_metadata_lock`
- 환경변수: `src/ppt_generator/interfaces/constants.py` — `DESIGN_SPEC_PARALLEL`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0015-per-slide-file-separation](./0015-per-slide-file-separation.md), [0019-complexity-based-scheduling-and-adaptive-effort](./0019-complexity-based-scheduling-and-adaptive-effort.md)
