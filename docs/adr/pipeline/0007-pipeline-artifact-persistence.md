# 7. 파이프라인 결과물 저장/로드

Date: 2026-02-11

## Status

Accepted (Updated: 디자인 스펙 영속화 추가, [ADR-0013](./0013-design-spec-pipeline.md) 참조)

## Context

현재 파이프라인(F1→F2→F3/F4)의 각 단계 결과물은 메모리(`SlidesService._sessions`)나 OS 임시 디렉토리(`tempfile.mkdtemp`)에만 존재하여, 서버 재시작 시 모두 소실된다.

사용자는 각 단계의 결과물을 지정된 디렉토리에 저장하고, 나중에 불러와서 원하는 단계부터 수정/재진행하고 싶어한다.

## Decision

전용 `ProjectService`가 모든 파일 I/O를 담당하고, 기존 각 도구에 `project_id` 옵션 파라미터를 추가하여 생성 시 자동 저장한다. `list_projects`로 프로젝트 목록을 조회하고, `load_*` 도구들로 재개를 지원한다.

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. 별도 save/load 도구만 추가 | 생성과 저장이 분리되어 매번 2번 호출 필요 | UX 저하, 탈락 |
| B. 각 도구에 직접 파일 I/O 삽입 | 컨트롤러에 persistence 로직 혼재 | 관심사 분리 위반, 탈락 |
| **C. ProjectService + project_dir 옵션** | ProjectService가 파일 I/O 전담, 컨트롤러는 위임만 | **채택** |

### Technical Details

프로젝트 디렉토리 구조:
```
~/.ppt-generator/<UUID>/
  project.json        # 메타데이터 (topic, num_slides, 각 단계 완료 상태/타임스탬프)
  outline.json        # F1 출력
  script.json         # F2 출력
  design_spec.json    # 디자인 스펙 출력 (PptxSlideSpec JSON, ADR-0013)
  slides.html         # F3/F4 출력
  slides_meta.json    # 세션 메타 (session_id)
  presentation.pptx   # F5 출력
```

MCP 도구:
- `list_projects()` → 프로젝트 목록 JSON (파이프라인 시작 전 호출 권장)
- `load_project_status(project_id)` → 메타데이터 JSON
- `load_outline(project_id)` → 아웃라인 JSON
- `load_script(project_id)` → 스크립트 JSON (speaker_notes 포함 아웃라인)
- `load_design_spec(project_id)` → 디자인 스펙 JSON (PptxSlideSpec 배열, [ADR-0013](./0013-design-spec-pipeline.md))
- `load_slides_html(project_id)` → `{"session_id", "html"}` JSON (세션 복원 포함)

기존 generate 도구 변경: 모두 `project_id: str = ""` 파라미터 추가.

### Acceptance Criteria

1. `project_id` 지정 시 각 단계 결과물이 `~/.ppt-generator/<UUID>/`에 자동 저장된다
2. `project_id` 미지정 시 UUID가 자동 생성되어 저장된다
3. `list_projects`로 기존 프로젝트 목록을 조회할 수 있다
4. `load_*` 도구로 저장된 결과물을 불러올 수 있다
5. 불러온 결과물을 다음 단계의 입력으로 사용할 수 있다

### Out of Scope

- 동시 접근 제어 (단일 사용자 MVP)
- 수정 이력 버저닝

## Consequences

### Positive

- 서버 재시작 후에도 결과물 보존
- 임의 단계부터 재개/수정 가능
- 기존 도구의 하위 호환성 유지

### Negative

- 모든 기존 컨트롤러에 파라미터 추가 필요 (5개 파일)
- `~/.ppt-generator/` 디렉토리 정리는 사용자 책임

### Risks

| 리스크 | 완화 방안 |
|--------|----------|
| 세션 HTML 메모리 소실 | `save_slides_html`로 디스크 영속화, `load_slides_html`로 세션 복원 |

## References

- 구현: `src/ppt_generator/tools/project/service.py`, `src/ppt_generator/tools/project/controller.py`
- 수정: 각 `tools/*/controller.py`, `di/container.py`, `server.py`
- 스키마: `interfaces/schemas.py` (`ProjectMetadata`)
- 테스트: `tests/test_project_service.py`
- 관련 ADR: [0001](./0001-outline-generation.md)~[0006](./0006-pptx-export.md) 전체, [0013-design-spec-pipeline](./0013-design-spec-pipeline.md)
