# 14. 파일 기반 통신, 슬라이드 단위 CRUD 및 파일 분리

Date: 2026-02-13

## Status

Accepted

## Context

MCP 클라이언트(Claude Desktop, Kiro 등)에서 도구를 연쇄 호출할 때, 인라인 JSON 콘텐츠가 컨텍스트 윈도우를 낭비한다. 디자인 스펙 생성 도구가 반환하는 `design_spec_json`은 수십 KB에 달하며, 이를 `export_html`이나 `export_pptx`의 인자로 다시 전달하면 토큰이 중복 소비된다.

또한 디자인 스펙이 단일 `design_spec.json` 파일(13슬라이드 기준 약 9,000줄, 260KB)에 모든 슬라이드를 포함하고 있어, 1개 슬라이드만 수정해도 전체 파일을 읽고/파싱/재직렬화/저장해야 하는 비효율이 있었다.

## Decision

세 가지 아키텍처 원칙을 도입한다:

### 1. 파일 기반 통신

- 모든 도구는 결과를 파일로 저장하고, 반환값에 파일 경로와 `project_id`만 포함
- `export_html`과 `export_pptx`에 `project_id` 기반 자동 로드 추가
  - `project_id`만 제공 시 프로젝트 디렉토리에서 디자인 스펙을 자동 로드
  - 기존 `design_spec_json` 인라인 경로도 하위 호환 유지

### 2. 슬라이드별 파일 분리

디자인 스펙을 슬라이드별 개별 JSON 파일로 분리하여 `design_spec/` 디렉토리에 저장한다.

```
~/.ppt-generator/<UUID>/
├── design_spec/
│   ├── slide_01.json        # 단일 PptxSlideSpec (wrapper 없음)
│   ├── slide_02.json
│   ├── ...
│   └── design_summary.json   # 첫 슬라이드에서 추출한 디자인 테마 요약
```

**파일 명명 규칙**: `slide_{index+1:02d}.json` — 1-based, 2자리 zero-padded (slide_01.json ~ slide_99.json). sorted glob으로 순서 보장.

### 3. 슬라이드 단위 CRUD

#### generate_slide_design_spec

- MCP 도구 `generate_slide_design_spec(outline_json, slide_index, total_slides, project_id)` 추가
- 슬라이드를 하나씩 생성하고 검토/수정한 뒤 다음 슬라이드로 진행하는 점진적 워크플로우 지원
- `slide_index == 0` (첫 슬라이드): 디자인 요약 추출 → `design_summary.json` 저장
- `slide_index > 0` (후속 슬라이드): `design_summary.json` 로드 → 디자인 테마 일관성 유지

#### modify_design_spec

- MCP 도구 `modify_design_spec(project_id, action, slide_index, outline_json)` 추가
- `action`: "add" (삽입), "update" (교체), "delete" (삭제)

| action | slide_index | outline_json | 동작 |
|--------|-------------|-------------|------|
| add | -1 (끝) 또는 삽입 위치 | 필수 | 새 슬라이드 생성 후 삽입 |
| update | 대상 인덱스 | 필수 | 해당 슬라이드 재생성 후 교체 |
| delete | 대상 인덱스 | 불필요 | 해당 슬라이드 제거 |

### Technical Details

#### 도구 우선순위

```
export_html:     design_spec_json > project_id (자동 로드)
export_pptx:     design_spec_json > project_id (자동 로드)
```

#### project_id 기반 체이닝 (권장 흐름)

```
generate_outline → generate_script
    → for i in 0..N-1:
        generate_slide_design_spec(slide[i], slide_index=i, total_slides=N)
        (선택) modify_design_spec(action="update", slide_index=i)
    → export_html(project_id=...) → export_pptx(project_id=...)
```

#### DesignSpecStore (design_spec_store.py)

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

#### 유틸리티 함수 (spec_utils.py)

| 함수 | 설명 |
|------|------|
| `slide_spec_to_json(PptxSlideSpec) -> str` | 단일 슬라이드 직렬화 |
| `parse_slide_spec_json(str) -> PptxSlideSpec` | 단일 슬라이드 역직렬화 |

기존 `design_spec_to_json`, `parse_design_spec_json`은 인라인 파라미터 하위 호환용으로 유지.

#### 컨트롤러 반환값

| 도구 | 반환 |
|------|------|
| `generate_slide_design_spec` | `design_spec_dir` + `slide_count` |
| `modify_design_spec` | `design_spec_dir` + `slide_count` |
| `load_design_spec` | `design_spec_dir` + `slide_count` + `slide_files` |

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. 인라인 JSON 유지 + 압축 | gzip 등으로 인라인 JSON 크기 축소 | MCP 프로토콜이 바이너리를 지원하지 않아 탈락 |
| B. 전체 재생성만 지원 | modify_design_spec 없이 전체 디자인 스펙 재생성 | 비용/시간 비효율, 탈락 |
| C. 단일 파일 유지 + 부분 읽기 | JSON streaming parser로 필요한 슬라이드만 읽기 | JSON 구조상 부분 수정 불가, 탈락 |
| D. SQLite 기반 저장 | 슬라이드별 row로 관리 | 파일 기반 통신 원칙에 어긋남, 디버깅 어려움, 탈락 |
| **E. 파일 기반 통신 + 슬라이드별 파일 + CRUD** | project_id 참조 + 개별 파일 + 슬라이드 CRUD | **채택** |

### Acceptance Criteria

1. `generate_slide_design_spec` 반환에 `design_spec_json` 인라인 키가 없다
2. `export_html(project_id=...)` 만으로 HTML 슬라이드가 생성된다
3. `export_pptx(project_id=...)` 만으로 PPTX가 생성된다
4. `modify_design_spec`으로 개별 슬라이드 add/update/delete가 동작한다
5. `design_spec_json` 직접 전달 경로도 동작한다 (인라인 파라미터 하위 호환)
6. `save_design_spec`으로 저장 시 design_spec/ 디렉토리에 슬라이드별 파일이 생성된다
7. `load_design_spec`으로 design_spec/ 디렉토리에서 DesignSpec을 복원할 수 있다
8. 첫 슬라이드 생성 시 `design_summary.json`가 생성되고, 후속 슬라이드에서 로드된다

### Out of Scope

- 기존 `design_spec.json` 단일 파일에서의 자동 마이그레이션
- 99슬라이드 초과 시 3자리 파일명 (현 MVP에서 충분)

## Consequences

### Positive

- **토큰 절감**: 인라인 JSON 제거로 MCP 클라이언트의 컨텍스트 윈도우 낭비 방지
- **슬라이드 단위 반복**: 전체 재생성 없이 개별 슬라이드 추가/수정/삭제 가능
- **단순한 체이닝**: project_id만으로 도구 연쇄 호출 가능
- **수정 성능 개선**: 1개 슬라이드 수정 시 해당 파일(약 20KB)만 읽기/쓰기
- **디버깅 용이**: 개별 슬라이드 파일을 직접 확인/편집 가능
- **하위 호환**: `design_spec_json` 인라인 파라미터 방식도 동작

### Negative

- `modify_design_spec`의 add/update 시 디자인 요약 추출을 위한 추가 LLM 호출 필요
- project_id를 통한 암묵적 파일 의존성으로 디버깅 시 파일 상태 확인 필요
- 파일 삽입/삭제 시 재번호 로직 필요 (O(n) 파일 rename)

## References

- 디자인 스펙 저장소: `src/ppt_generator/tools/project/design_spec_store.py` — `DesignSpecStore` (파일 CRUD 전담)
- 프로젝트 서비스: `src/ppt_generator/tools/project/service.py` — `DesignSpecStore`에 위임하는 메서드 제공
- 디자인 서비스: `src/ppt_generator/tools/design/service.py` — `generate_single_slide()`, `extract_design_summary()`
- 유틸리티: `src/ppt_generator/interfaces/spec_utils.py` — `slide_spec_to_json()`, `parse_slide_spec_json()`
- 컨트롤러: `src/ppt_generator/tools/design/controller.py`, `tools/slides/controller.py`, `tools/pptx/controller.py`, `tools/project/controller.py`
- 테스트: `tests/test_project_service.py` — `TestSaveAndLoadDesignSpec`, `TestDesignSpecSlideCRUD`
- 관련 ADR: [0007-pipeline-artifact-persistence](./0007-pipeline-artifact-persistence.md), [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0016-per-slide-html-iframe](./0016-per-slide-html-iframe.md)
