# 14. 파일 기반 통신 및 슬라이드 단위 CRUD

Date: 2026-02-13

## Status

Accepted (Updated: 슬라이드별 파일 분리 [ADR-0015](./0015-per-slide-file-separation.md))

## Context

MCP 클라이언트(Claude Desktop, Kiro 등)에서 도구를 연쇄 호출할 때, 인라인 JSON 콘텐츠가 컨텍스트 윈도우를 낭비한다. 예를 들어 디자인 스펙 생성 도구가 반환하는 `design_spec_json`은 수십 KB에 달하며, 이를 `generate_slides`나 `export_pptx`의 인자로 다시 전달하면 토큰이 중복 소비된다.

또한 디자인 스펙의 개별 슬라이드를 수정하려면 전체를 재생성해야 하는 문제가 있었다 (ADR-0013의 Out of Scope).

## Decision

두 가지 아키텍처 원칙을 도입한다:

### 1. 파일 기반 통신

- 모든 도구는 결과를 파일로 저장하고, 반환값에 파일 경로와 `project_id`만 포함
- 디자인 스펙 생성 도구의 반환에서 `design_spec_json` 인라인 키 제거, `design_spec_dir` + `slide_count` 반환
- `generate_slides`와 `export_pptx`에 `project_id` 기반 자동 로드 추가
  - `project_id`만 제공 시 프로젝트 디렉토리에서 디자인 스펙을 자동 로드
  - 기존 `design_spec_json`, `outline_json`, `session_id` 경로도 하위 호환 유지

### 2. 슬라이드 단위 CRUD (modify_design_spec)

- 새 MCP 도구 `modify_design_spec(project_id, action, slide_index, outline_json)` 추가
- `action`: "add" (삽입), "update" (교체), "delete" (삭제)
- 기존 디자인 스펙의 첫 슬라이드에서 디자인 요약을 추출하여 일관성 유지
- `DesignService.generate_single_slide()` 메서드로 단일 슬라이드 생성

### 3. 슬라이드별 디자인 스펙 생성 (generate_slide_design_spec)

- 새 MCP 도구 `generate_slide_design_spec(outline_json, slide_index, total_slides, project_id)` 추가
- 슬라이드를 하나씩 생성하고 검토/수정한 뒤 다음 슬라이드로 진행하는 점진적 워크플로우 지원
- `slide_index == 0` (첫 슬라이드): 디자인 요약 추출 → `design_spec/design_summary.json` 저장
- `slide_index > 0` (후속 슬라이드): `design_summary.json` 로드 → 디자인 테마 일관성 유지
- `ProjectService.create_design_spec_slide()` — 파일 유무 무관하게 슬라이드 저장 (디렉토리 자동 생성)
- `ProjectService.save_design_summary()` / `load_design_summary()` — 디자인 요약 영속화

### Technical Details

#### 도구 우선순위

```
generate_slides: design_spec_json > project_id (자동 로드)
export_pptx:     design_spec_json > project_id (자동 로드)
```

#### project_id 기반 체이닝 (권장 흐름)

```
generate_outline → generate_script
    → for i in 0..N-1:
        generate_slide_design_spec(slide[i], slide_index=i, total_slides=N)
        (선택) modify_design_spec(action="update", slide_index=i)
    → generate_slides(project_id=...) → export_pptx(project_id=...)
```

#### modify_design_spec 동작

| action | slide_index | outline_json | 동작 |
|--------|-------------|-------------|------|
| add | -1 (끝) 또는 삽입 위치 | 필수 | 새 슬라이드 생성 후 삽입 |
| update | 대상 인덱스 | 필수 | 해당 슬라이드 재생성 후 교체 |
| delete | 대상 인덱스 | 불필요 | 해당 슬라이드 제거 |

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. 인라인 JSON 유지 + 압축 | gzip 등으로 인라인 JSON 크기 축소 | MCP 프로토콜이 바이너리를 지원하지 않아 탈락 |
| B. 전체 재생성만 지원 | modify_design_spec 없이 전체 디자인 스펙 재생성 | 비용/시간 비효율, 탈락 |
| **C. 파일 기반 통신 + 슬라이드 CRUD** | project_id 참조 + 개별 슬라이드 CRUD | **채택** |

### Acceptance Criteria

1. `generate_slide_design_spec` 반환에 `design_spec_json` 인라인 키가 없다
2. `generate_slides(project_id=...)` 만으로 HTML 슬라이드가 생성된다
3. `export_pptx(project_id=...)` 만으로 PPTX가 생성된다
4. `modify_design_spec`으로 개별 슬라이드 add/update/delete가 동작한다
5. `design_spec_json` 직접 전달 경로도 동작한다 (인라인 파라미터 하위 호환)
6. `generate_slide_design_spec`으로 슬라이드를 하나씩 생성할 수 있다
7. 첫 슬라이드 생성 시 `design_summary.json`가 생성되고, 후속 슬라이드에서 로드된다

## Consequences

### Positive

- **토큰 절감**: 인라인 JSON 제거로 MCP 클라이언트의 컨텍스트 윈도우 낭비 방지
- **슬라이드 단위 반복**: 전체 재생성 없이 개별 슬라이드 추가/수정/삭제 가능
- **단순한 체이닝**: project_id만으로 도구 연쇄 호출 가능
- **하위 호환**: `design_spec_json` 인라인 파라미터 방식도 동작

### Negative

- `modify_design_spec`의 add/update 시 디자인 요약 추출을 위한 추가 LLM 호출 필요
- project_id를 통한 암묵적 파일 의존성으로 디버깅 시 파일 상태 확인 필요

## References

- 구현: `src/ppt_generator/tools/design/controller.py` — `modify_design_spec`, `generate_slide_design_spec`
- 서비스: `src/ppt_generator/tools/design/service.py` — `generate_single_slide(slide_outline, design_summary, slide_index, total_slides)`
- 프로젝트 서비스: `src/ppt_generator/tools/project/service.py` — 슬라이드별 CRUD 메서드, `create_design_spec_slide()`, `save_design_summary()`, `load_design_summary()`
- 슬라이드 컨트롤러: `src/ppt_generator/tools/slides/controller.py` — project_id 자동 로드
- PPTX 컨트롤러: `src/ppt_generator/tools/pptx/controller.py` — project_id 자동 로드
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0007-pipeline-artifact-persistence](./0007-pipeline-artifact-persistence.md), [0015-per-slide-file-separation](./0015-per-slide-file-separation.md)
