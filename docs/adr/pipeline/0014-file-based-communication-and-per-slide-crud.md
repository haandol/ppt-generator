# 14. 파일 기반 통신, 슬라이드 단위 CRUD 및 파일 분리

Date: 2026-02-13

## Status

Accepted

## Context

MCP 클라이언트(Claude Desktop, Kiro 등)에서 도구를 연쇄 호출할 때, 인라인 JSON 콘텐츠가 컨텍스트 윈도우를 낭비한다. 디자인 스펙 생성 도구가 반환하는 `design_spec_json`은 수십 KB에 달하며, 이를 `export_html`이나 `export_pptx`의 인자로 다시 전달하면 토큰이 중복 소비된다.

또한 디자인 스펙이 단일 파일(13슬라이드 기준 약 9,000줄, 260KB)에 모든 슬라이드를 포함하고 있어, 1개 슬라이드만 수정해도 전체 파일을 읽고/파싱/재직렬화/저장해야 하는 비효율이 있었다.

## Decision

세 가지 아키텍처 원칙을 도입한다:

### 1. 파일 기반 통신

- 모든 도구는 결과를 파일로 저장하고, 반환값에 파일 경로와 `project_id`만 포함
- `export_html`과 `export_pptx`에 `project_id` 기반 자동 로드 추가
  - `project_id`만 제공 시 프로젝트 디렉토리에서 디자인 스펙을 자동 로드
  - 기존 `design_spec_json` 인라인 경로도 하위 호환 유지

### 2. 슬라이드별 파일 분리

디자인 스펙을 슬라이드별 개별 JSON 파일로 분리하여 저장한다. 1-based, 2자리 zero-padded 파일명을 사용하며 sorted glob으로 순서를 보장한다. 첫 슬라이드에서 추출한 디자인 테마 요약도 별도 파일로 저장한다.

### 3. 슬라이드 단위 CRUD

#### generate_slide_design_spec

- 슬라이드를 하나씩 생성하고 검토/수정한 뒤 다음 슬라이드로 진행하는 점진적 워크플로우 지원
- 첫 슬라이드 생성 시 디자인 요약 추출·저장, 후속 슬라이드에서 로드하여 테마 일관성 유지

#### modify_design_spec

- `action`: "add" (삽입), "update" (교체), "delete" (삭제)
- **add**: 인라인 파라미터(`title`, `content_summary`, `component_hint`, `slide_type`, `speaker_notes`)를 받아 단일 호출로 모든 작업을 수행한다. 내부적으로 outline/script 파일 shift → outline 삽입 → HTML shift → 디자인 스펙 LLM 생성 → 디자인 스펙 삽입 → HTML 렌더링을 자동 처리한다. 호출자가 사전에 `save_outline_slide`을 호출할 필요가 없다.
- **update**: 인라인 파라미터(`title`, `content_summary`)를 전달하면 outline을 자동 업데이트한다. 또는 사전에 `save_outline_slide`로 수정 후 호출할 수 있다.
- **delete**: 디자인 스펙, HTML, outline/script를 함께 삭제한다.

| action | slide_index | 사전 조건 | 동작 |
|--------|-------------|----------|------|
| add | -1 (끝) 또는 삽입 위치 | 없음 (인라인 파라미터 필수: `title`, `content_summary`) | outline/script shift → outline 삽입 → HTML shift → LLM 디자인 스펙 생성 → 디자인 스펙 삽입 + `num_slides` 동기화 |
| update | 대상 인덱스 | 없음 (인라인 `title`/`content_summary` 제공 시 자동 업데이트, 또는 `save_outline_slide`로 사전 수정) | outline 읽기 → 디자인 스펙 재생성 후 교체 + `num_slides` 동기화 |
| delete | 대상 인덱스 | 없음 | 디자인 스펙 제거 + outline/script 해당 슬라이드 삭제 + HTML 삭제 + `num_slides` 동기화 |

#### move_slide

슬라이드 위치를 변경하는 **별도 도구**. LLM 호출 없이 순수 파일 재정렬만 수행한다.

- `from_index`: 현재 슬라이드 위치 (0-based)
- `to_index`: 이동할 위치 (0-based)
- 모든 관련 파일(outline/script, design_spec, slide HTML)을 원자적으로 재정렬한다.
- `modify_design_spec`과 분리된 독립 도구로 등록하여 LLM 클라이언트의 혼동을 방지한다.
- 호출 후 `export_html`로 HTML을 새로 내보내야 한다.

| 파라미터 | 설명 |
|----------|------|
| from_index | 이동할 슬라이드의 현재 인덱스 |
| to_index | 이동 목표 인덱스 |

> **설계 근거**: 슬라이드 이동은 기존에 `delete` + `add` 조합으로만 가능했으나, `add`가 LLM 디자인 스펙 재생성을 수반하여 불필요한 비용과 시간이 발생했다. 이동은 콘텐츠 변경 없이 순서만 바꾸는 연산이므로 파일 rename만으로 충분하다.

> **save_outline_slide**: 기존 슬라이드를 덮어쓰는 용도로만 사용한다. 삽입은 `modify_design_spec(action="add")`가 내부적으로 처리한다.

> **save_outline_slide의 script 동기화**: outline 파일 저장 시 script 디렉토리에 동일 인덱스 파일이 존재하면 새 내용으로 동기화한다.

> **읽기 우선순위**: script가 존재하면 우선 읽고, 없으면 outline에서 읽는다. 둘 다 없으면 에러를 발생시킨다.

> **num_slides 동기화**: `modify_design_spec` 완료 시 `project.json`의 `num_slides`를 실제 디자인 스펙 파일 수와 자동 동기화한다.

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
    → (선택) move_slide(project_id, from_index, to_index)
    → export_html(project_id=...) → export_pptx(project_id=...)
```

#### DesignSpecStore

디자인 스펙 파일 I/O를 전담하는 저장소 클래스. 주요 기능:

- 전체 디자인 스펙 저장/로드
- 개별 슬라이드 CRUD (save/load/create/delete/insert/move)
- 슬라이드 수 조회
- 디자인 요약 저장/로드

`ProjectService`는 동일 시그니처의 위임 메서드를 제공하여 기존 호출자의 변경을 최소화한다.

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
4-1. `move_slide`로 슬라이드 순서 변경이 LLM 호출 없이 동작한다
5. `design_spec_json` 직접 전달 경로도 동작한다 (인라인 파라미터 하위 호환)
6. 디자인 스펙 저장 시 슬라이드별 개별 파일이 생성된다
7. 개별 파일에서 전체 DesignSpec을 복원할 수 있다
8. 첫 슬라이드 생성 시 디자인 요약이 생성되고, 후속 슬라이드에서 로드된다

### Out of Scope

- 기존 단일 파일에서의 자동 마이그레이션
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

- 관련 ADR: [0007-pipeline-artifact-persistence](./0007-pipeline-artifact-persistence.md), [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0016-per-slide-html-iframe](./0016-per-slide-html-iframe.md)
