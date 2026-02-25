# 7. 파이프라인 결과물 저장/로드 및 프로젝트 디렉토리 통합

Date: 2026-02-11

## Status

Accepted

## Context

파이프라인(F1→F2→Design Spec→HTML/PPTX)의 각 단계 결과물은 메모리나 OS 임시 디렉토리(`tempfile.mkdtemp`)에만 존재하여, 서버 재시작 시 모두 소실된다. 또한 `ExportService`가 OS 임시 디렉토리에 파일을 생성하여 OS 정리 시 소실 가능하고, `project_dir`을 명시적으로 지정해야만 보존되는 문제가 있었다.

사용자는 각 단계의 결과물을 지정된 디렉토리에 저장하고, 나중에 불러와서 원하는 단계부터 수정/재진행하고 싶어한다.

## Decision

### 프로젝트 디렉토리 통합

모든 중간 파일을 `~/.ppt-generator/<UUID>/`에 통합 저장한다.

- `PPT_GENERATOR_HOME = Path.home() / ".ppt-generator"` 상수 추가
- `ProjectService.resolve_project_dir(project_id)` 메서드로 project_id → (project_id, project_dir) 변환. 빈 ID면 UUID 자동 생성
- 모든 컨트롤러의 `project_dir: str` 파라미터를 `project_id: str`로 변경

### ProjectService 기반 영속화

전용 `ProjectService`가 모든 파일 I/O를 담당하고, 각 도구에 `project_id` 옵션 파라미터를 추가하여 생성 시 자동 저장한다.

### Technical Details

프로젝트 디렉토리 구조:
```
~/.ppt-generator/<UUID>/
  project.json         # 메타데이터 (topic, num_slides, 각 단계 완료 상태/타임스탬프)
  outline.json         # F1 출력
  script.json          # F2 출력
  design_spec/         # 디자인 스펙 출력 (슬라이드별 개별 파일, ADR-0014)
    slide_01.json      # 단일 PptxSlideSpec (wrapper 없음)
    slide_02.json
    ...
    design_summary.json # 디자인 테마 요약
  slides/              # HTML 슬라이드 출력 (슬라이드별 개별 파일, ADR-0016)
    slide_01.html      # 슬라이드별 완전한 HTML 문서
    slide_02.html
    ...
  slides.html          # iframe 컨테이너 (ADR-0016)
  slides_meta.json     # 세션 메타 (session_id)
  presentation.pptx    # PPTX 출력 (직접 생성)
```

MCP 도구:
- `list_projects()` → 프로젝트 목록 JSON (파이프라인 시작 전 호출 권장)
- `load_project_status(project_id)` → 메타데이터 JSON
- `load_outline(project_id)` → 아웃라인 JSON
- `load_script(project_id)` → 스크립트 JSON (speaker_notes 포함 아웃라인)
- `load_design_spec(project_id)` → 디자인 스펙 정보 (design_spec_dir, slide_count, slide_files)

기존 generate 도구 변경: 모두 `project_id: str = ""` 파라미터 추가.

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. 별도 save/load 도구만 추가 | 생성과 저장이 분리되어 매번 2번 호출 필요 | UX 저하, 탈락 |
| B. 각 도구에 직접 파일 I/O 삽입 | 컨트롤러에 persistence 로직 혼재 | 관심사 분리 위반, 탈락 |
| C. project_dir 경로 유지 | 사용자가 임의 경로를 지정 | 파일 소실 위험과 경로 관리 복잡성, 탈락 |
| **D. ProjectService + project_id 기반** | ProjectService가 파일 I/O 전담, project_id로 식별 | **채택** |

### Acceptance Criteria

1. `project_id` 지정 시 각 단계 결과물이 `~/.ppt-generator/<UUID>/`에 자동 저장된다
2. `project_id` 미지정 시 UUID가 자동 생성되어 저장된다
3. `list_projects`로 기존 프로젝트 목록을 조회할 수 있다
4. `load_*` 도구로 저장된 결과물을 불러올 수 있다
5. 불러온 결과물을 다음 단계의 입력으로 사용할 수 있다
6. PPTX 파일이 프로젝트 디렉토리에 직접 생성된다

### Out of Scope

- 동시 접근 제어 (단일 사용자 MVP)
- 수정 이력 버저닝

## Consequences

### Positive

- 서버 재시작 후에도 결과물 보존
- 임의 단계부터 재개/수정 가능
- 모든 중간 파일이 `~/.ppt-generator/`에 통합되어 관리 용이
- project_id 기반으로 프로젝트 식별이 단순화됨

### Negative

- 모든 기존 컨트롤러에 파라미터 추가 필요
- `~/.ppt-generator/` 디렉토리 정리는 사용자 책임

## References

- 구현: `src/ppt_generator/tools/project/service.py`, `src/ppt_generator/tools/project/controller.py`
- 상수: `src/ppt_generator/interfaces/constants.py` — `PPT_GENERATOR_HOME`
- 수정: 각 `tools/*/controller.py`, `di/container.py`, `server.py`
- 스키마: `interfaces/schemas.py` (`ProjectMetadata`)
- 테스트: `tests/test_project_service.py`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0014-file-based-communication-and-per-slide-crud](./0014-file-based-communication-and-per-slide-crud.md)
