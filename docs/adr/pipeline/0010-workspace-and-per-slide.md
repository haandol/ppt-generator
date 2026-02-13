# 10. 워킹 디렉토리 통합 및 슬라이드 개별 생성/수정

Date: 2026-02-11

## Status

Accepted

## Context

두 가지 문제가 있었다:

1. **중간 파일이 OS 임시 디렉토리에 흩어짐**: `ExportService`가 `tempfile.mkdtemp()`로 OS 임시 디렉토리에 파일을 생성하여, OS 정리 시 소실 가능하고 `project_dir`을 명시적으로 지정해야만 보존됨.
2. **전체 슬라이드 일괄 생성/수정 시 토큰 부족**: `generate_slides`가 최대 10장을 한 번에 생성하고, `modify_slides`가 전체 HTML을 LLM에 전달하여 토큰 한도 초과.

## Decision

### 워킹 디렉토리 전환

- 모든 중간 파일을 `~/.ppt-generator/<UUID>/`에 통합 저장
- `PPT_GENERATOR_HOME = Path.home() / ".ppt-generator"` 상수 추가
- `ProjectService.resolve_project_dir(project_id)` 메서드로 project_id → (project_id, project_dir) 변환. 빈 ID면 UUID 자동 생성
- 6개 컨트롤러의 `project_dir: str` 파라미터를 `project_id: str`로 변경
- `ExportService.export()`에 `output_dir` 파라미터 추가하여 PPTX를 프로젝트 디렉토리에 직접 생성

### 슬라이드 개별 생성/수정

- `SLIDES_MAX_PER_BATCH`를 10에서 1로 변경하여 슬라이드를 1장씩 개별 생성
- `modify_slides`에 `slide_index` 파라미터 추가 (-1이면 전체 수정, 0 이상이면 해당 슬라이드만 수정)
- `SlidesService._modify_single_slide()` 메서드 추가: BeautifulSoup으로 대상 슬라이드만 추출 → LLM에 단일 div 수정 요청 → 원본 HTML에 replace_with

### Technical Details

프로젝트 디렉토리 구조:
```
~/.ppt-generator/<UUID>/
  project.json         # 메타데이터
  outline.json         # F1 출력
  script.json          # F2 출력
  design_spec/         # 디자인 스펙 출력 (ADR-0013, ADR-0015)
    slide_01.json      # 슬라이드별 PptxSlideSpec JSON
    slide_02.json
    ...
    design_summary.json # 디자인 테마 요약 (슬라이드별 생성 시)
  slides.html          # F3/F4 출력
  slides_meta.json     # 세션 메타 (session_id)
  presentation.pptx    # F5 출력 (직접 생성)
```

### Alternatives Considered

- **project_dir 경로 유지**: 사용자가 임의 경로를 지정할 수 있지만, 파일 소실 위험과 경로 관리 복잡성이 남음
- **SLIDES_MAX_PER_BATCH=3~5**: 배치 크기를 줄이되 완전한 개별 생성은 아님. 1로 설정하면 기존 배치 로직이 그대로 동작하면서 토큰 문제 해결

## Consequences

**긍정적:**
- 모든 중간 파일이 `~/.ppt-generator/`에 통합되어 관리 용이
- project_id 기반으로 프로젝트 식별이 단순화됨
- 슬라이드 개별 생성으로 토큰 한도 초과 방지
- 슬라이드 단위 수정으로 불필요한 토큰 소비 감소
- PPTX 파일이 프로젝트 디렉토리에 직접 생성되어 파일 복사 오버헤드 제거

**부정적:**
- 슬라이드 개별 생성 시 LLM 호출 횟수 증가 (N장 → 1 + 1(디자인 요약) + (N-1) = N+1회)
- 기존 `project_dir` 파라미터를 사용하던 MCP 클라이언트는 `project_id`로 전환 필요
- `~/.ppt-generator/` 디렉토리 정리는 사용자 책임

## References

- [ADR 0007: 파이프라인 결과물 저장/로드](./0007-pipeline-artifact-persistence.md)
- `src/ppt_generator/interfaces/constants.py` — `PPT_GENERATOR_HOME`
- `src/ppt_generator/tools/project/service.py` — `resolve_project_dir()`, `list_projects()`

> **Note**: 슬라이드 개별 생성/수정 관련 구현은 ADR-0013(디자인 스펙 파이프라인)으로 대체되었습니다. `SLIDES_MAX_PER_BATCH` 상수와 `_modify_single_slide()` 메서드는 레거시 HTML 경로와 함께 제거되었습니다.
