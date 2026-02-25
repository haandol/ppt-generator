# 15. 디자인 스펙 슬라이드별 파일 분리

Date: 2026-02-13

## Status

Accepted

## Context

디자인 스펙이 단일 `design_spec.json` 파일(13슬라이드 기준 약 9,000줄, 260KB)에 모든 슬라이드를 포함하고 있었다. `modify_design_spec`으로 1개 슬라이드만 수정해도 전체 파일을 읽고 → 파싱 → 재직렬화 → 저장해야 하는 비효율이 있었다.

기존 구조:
```
~/.ppt-generator/<UUID>/
  design_spec.json    # 전체 슬라이드 배열 (DesignSpec wrapper)
```

문제점:
1. **I/O 비효율**: 1개 슬라이드 수정에 전체 260KB 파일 읽기/쓰기
2. **메모리 사용**: 전체 DesignSpec을 파싱한 후 수정 대상 슬라이드만 변경하고 다시 직렬화
3. **확장성**: 슬라이드 수 증가 시 파일 크기가 선형 증가하여 수정 비용도 비례 증가

## Decision

디자인 스펙을 슬라이드별 개별 JSON 파일로 분리하여 `design_spec/` 디렉토리에 저장한다. 각 파일은 단일 `PptxSlideSpec` 객체만 포함한다 (DesignSpec wrapper 없음).

변경 후 구조:
```
~/.ppt-generator/<UUID>/
├── design_spec/
│   ├── slide_01.json        # 단일 PptxSlideSpec
│   ├── slide_02.json
│   ├── ...
│   └── design_summary.json   # 첫 슬라이드에서 추출한 디자인 테마 요약 (슬라이드별 생성 시)
├── slides.html
└── project.json
```

### Technical Details

#### 파일 명명 규칙

- `slide_{index+1:02d}.json` — 1-based, 2자리 zero-padded (slide_01.json ~ slide_99.json)
- sorted glob으로 순서 보장

#### 새 유틸리티 함수 (spec_utils.py)

| 함수 | 설명 |
|------|------|
| `slide_spec_to_json(PptxSlideSpec) -> str` | 단일 슬라이드 직렬화 |
| `parse_slide_spec_json(str) -> PptxSlideSpec` | 단일 슬라이드 역직렬화 |

기존 `design_spec_to_json`, `parse_design_spec_json`은 인라인 파라미터 하위 호환용으로 유지.

#### DesignSpecStore (design_spec_store.py) — 디자인 스펙 파일 CRUD 전담

디자인 스펙 파일 I/O 로직은 `tools/project/design_spec_store.py`의 `DesignSpecStore` 클래스에 전담한다. `ProjectService`는 동일 시그니처의 위임 메서드를 제공하여 기존 호출자의 변경을 최소화한다.

| 메서드 | 설명 |
|--------|------|
| `save_design_spec(dir, DesignSpec)` | design_spec/ 디렉토리에 개별 파일 저장 |
| `load_design_spec(dir) -> DesignSpec` | slide_*.json glob으로 읽기 |
| `save_design_spec_slide(dir, index, slide)` | 개별 슬라이드 덮어쓰기 (파일 존재 필수) |
| `create_design_spec_slide(dir, index, slide)` | 개별 슬라이드 저장 (파일 유무 무관, 디렉토리 자동 생성) |
| `load_design_spec_slide(dir, index)` | 개별 슬라이드 로드 |
| `delete_design_spec_slide(dir, index)` | 삭제 + 재번호 |
| `insert_design_spec_slide(dir, index, slide)` | 삽입 + 재번호 |
| `get_design_spec_slide_count(dir)` | 슬라이드 파일 수 반환 |
| `save_design_summary(dir, dict)` | design_summary.json 저장 |
| `load_design_summary(dir) -> dict \| None` | design_summary.json 로드 (없으면 None) |

#### 컨트롤러 반환값 변경

| 도구 | 이전 | 이후 |
|------|------|------|
| `generate_slide_design_spec` | `design_spec_path` | `design_spec_dir` + `slide_count` |
| `modify_design_spec` | `design_spec_path` | `design_spec_dir` + `slide_count` |
| `load_design_spec` | `design_spec_path` | `design_spec_dir` + `slide_count` + `slide_files` |

#### modify_design_spec 최적화

| action | 이전 (전체 파일) | 이후 (개별 파일) |
|--------|-----------------|-----------------|
| update | 전체 읽기 → 수정 → 전체 저장 | slide_01 읽기 (요약 추출) + 대상 파일만 덮어쓰기 |
| add | 전체 읽기 → 삽입 → 전체 저장 | slide_01 읽기 (요약 추출) + 파일 삽입 + 재번호 |
| delete | 전체 읽기 → 삭제 → 전체 저장 | 대상 파일 삭제 + 재번호 |

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. 단일 파일 유지 + 부분 읽기 | JSON streaming parser로 필요한 슬라이드만 읽기 | JSON 구조상 부분 수정 불가, 탈락 |
| B. SQLite 기반 저장 | 슬라이드별 row로 관리 | 파일 기반 통신 원칙에 어긋남, 디버깅 어려움, 탈락 |
| **C. 슬라이드별 개별 파일** | design_spec/ 디렉토리에 slide_NN.json | **채택** |

### Acceptance Criteria

1. `save_design_spec`으로 DesignSpec 저장 시 design_spec/ 디렉토리에 슬라이드별 파일이 생성된다
2. `load_design_spec`으로 design_spec/ 디렉토리에서 DesignSpec을 복원할 수 있다
3. `modify_design_spec`의 update/add/delete가 해당 파일만 다루고 전체 재직렬화하지 않는다
4. 기존 `export_html(project_id=...)`, `export_pptx(project_id=...)` 체이닝이 정상 동작한다
5. 인라인 `design_spec_json` 파라미터 경로는 하위 호환 유지된다

### Out of Scope

- 기존 `design_spec.json` 단일 파일에서의 자동 마이그레이션
- 99슬라이드 초과 시 3자리 파일명 (현 MVP에서 충분)

## Consequences

### Positive

- **수정 성능 개선**: 1개 슬라이드 수정 시 해당 파일(약 20KB)만 읽기/쓰기
- **메모리 효율**: 전체 파싱 없이 필요한 슬라이드만 로드
- **디버깅 용이**: 개별 슬라이드 파일을 직접 확인/편집 가능
- **확장성**: 슬라이드 수 증가해도 개별 수정 비용 일정

### Negative

- 파일 삽입/삭제 시 재번호 로직 필요 (O(n) 파일 rename)
- 디렉토리 구조가 한 단계 깊어짐

## References

- 디자인 스펙 저장소: `src/ppt_generator/tools/project/design_spec_store.py` — `DesignSpecStore` (파일 CRUD 전담)
- 프로젝트 서비스: `src/ppt_generator/tools/project/service.py` — `DesignSpecStore`에 위임하는 메서드 제공
- 유틸리티: `src/ppt_generator/interfaces/spec_utils.py` — `slide_spec_to_json()`, `parse_slide_spec_json()`
- 컨트롤러: `src/ppt_generator/tools/design/controller.py`, `tools/slides/controller.py`, `tools/pptx/controller.py`, `tools/project/controller.py`
- 테스트: `tests/test_project_service.py` — `TestSaveAndLoadDesignSpec`, `TestDesignSpecSlideCRUD`
- 관련 ADR: [0007-pipeline-artifact-persistence](./0007-pipeline-artifact-persistence.md), [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0014-file-based-communication-and-per-slide-crud](./0014-file-based-communication-and-per-slide-crud.md), [0016-per-slide-html-iframe](./0016-per-slide-html-iframe.md)
