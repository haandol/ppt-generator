# 파일 기반 통신, 슬라이드 단위 CRUD 및 파일 분리

Date: 2026-02-13

## Status

Accepted (2026-07-21)

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

#### 디자인 스펙 생성 (prepare_design_slide / ingest_design_slide)

- 슬라이드를 하나씩 생성하고 검토/수정한 뒤 다음 슬라이드로 진행하는 점진적 워크플로우 지원
- 첫 슬라이드 생성 시 디자인 요약 추출·저장, 후속 슬라이드에서 로드하여 테마 일관성 유지

#### 슬라이드 편집 (prepare_slide_edit / ingest_slide_edit)

- `action`: "add" (삽입), "update" (교체), "delete" (삭제)
- **add**: 인라인 파라미터(`title`, `content_summary`, `component_hint`, `slide_type`, `speaker_notes`)를 받아 단일 호출로 모든 작업을 수행한다. 내부적으로 outline 파일 shift → outline 삽입 → HTML shift → 디자인 스펙 LLM 생성 → 디자인 스펙 삽입 → HTML 렌더링을 자동 처리한다. 호출자가 사전에 `save_outline_slide`을 호출할 필요가 없다.
- **update**: 인라인 파라미터(`title`, `content_summary`)를 전달하면 outline을 자동 업데이트한다. 또는 사전에 `save_outline_slide`로 수정 후 호출할 수 있다.
- **color_theme 자동 참조**: `design_summary.json`에 `color_theme`이 저장되어 있으면 해당 값을 LLM 디자인 스펙 생성과 배경 이미지 선택에 사용한다. 이를 통해 임포트된 프로젝트의 라이트/다크 테마가 슬라이드 추가/수정 시 자동으로 유지된다.
- **delete**: 디자인 스펙, HTML, outline를 함께 삭제한다.

| action | slide_index | 사전 조건 | 동작 |
|--------|-------------|----------|------|
| add | -1 (끝) 또는 삽입 위치 | 없음 (인라인 파라미터 필수: `title`, `content_summary`) | **outline sync** → outline shift → outline 삽입 → HTML shift → LLM 디자인 스펙 생성 → 디자인 스펙 삽입 + `num_slides` 동기화 |
| update | 대상 인덱스 | 없음 (인라인 `title`/`content_summary` 제공 시 자동 업데이트, 또는 `save_outline_slide`로 사전 수정) | **outline sync** → outline 읽기 → 디자인 스펙 재생성 후 교체 + `num_slides` 동기화 |
| delete | 대상 인덱스 | 없음 | **outline sync** → 디자인 스펙 제거 + outline 해당 슬라이드 삭제 + HTML 삭제 + `num_slides` 동기화 |

#### prepare 무부작용과 ingest 원자 커밋

생성이 필요한 add/update의 prepare 단계는 현재 프로젝트를 변경하지 않는다. prepare는
정규화된 편집 의도, 대상 위치, 생성 프롬프트, 응답 스키마와 현재 프로젝트 revision을
담은 편집 컨텍스트만 반환한다.

ingest는 다음 순서로 처리한다.

1. 서버가 서명한 편집 컨텍스트인지 확인하고 현재 revision과 일치하는지 검증한다.
2. 생성 결과를 완전히 검증한다.
3. outline, design spec, 이미지, HTML, 메타데이터 변경을 하나의 논리적 트랜잭션으로
   적용한다.
4. 중간 실패 시 기존 프로젝트 상태로 복원한다.
5. 동일 편집 컨텍스트가 재전송되면 중복 적용하지 않고 이전 결과를 반환한다.

이 정책은 생성 실패, 클라이언트 재시도, 네트워크 재전송이 프로젝트 파일을 미리
변경하거나 같은 슬라이드를 두 번 삽입하지 않도록 한다.
같은 프로젝트에 대한 ingest의 검증, 이전 결과 확인과 커밋은 직렬화하여 동시
재전송도 하나의 편집만 적용되도록 한다.

편집 컨텍스트의 서명과 직렬화는 프로세스 수명에 의존하지 않는다. 서버 재시작 뒤에도
prepare 결과를 검증할 수 있는 지속 가능한 서버 비밀을 사용하고, 같은 프로젝트를
다루는 여러 프로세스는 운영체제 수준의 프로젝트 락으로 커밋을 직렬화한다.

슬라이드 이동도 같은 원자성 정책을 적용한다. outline, 이미지, 디자인 스펙, HTML 중
하나라도 재정렬에 실패하면 전체 프로젝트를 이전 상태로 복원한다.

#### 인덱스 계약

모든 공개 슬라이드 인덱스는 문서화된 예외값을 제외하고 1-based 양수이며, 파일 I/O
전에 범위를 검증한다. 유효하지 않은 인덱스는 새 파일을 만들거나 기존 파일을
변경하지 않고 명확한 오류를 반환한다.

#### move_slide

슬라이드 위치를 변경하는 **별도 도구**. LLM 호출 없이 순수 파일 재정렬만 수행한다.

- `from_index`: 현재 슬라이드 위치 (1-based)
- `to_index`: 이동할 위치 (1-based)
- 실행 전 **outline sync**로 outline 수를 design_spec에 맞춘 뒤, 모든 관련 파일(outline, design_spec, slide HTML)을 원자적으로 재정렬한다.
- `slide_edit`과 분리된 독립 도구로 등록하여 LLM 클라이언트의 혼동을 방지한다.
- 호출 후 `export_html`로 HTML을 새로 내보내야 한다.

| 파라미터 | 설명 |
|----------|------|
| from_index | 이동할 슬라이드의 현재 인덱스 |
| to_index | 이동 목표 인덱스 |

> **설계 근거**: 슬라이드 이동은 기존에 `delete` + `add` 조합으로만 가능했으나, `add`가 LLM 디자인 스펙 재생성을 수반하여 불필요한 비용과 시간이 발생했다. 이동은 콘텐츠 변경 없이 순서만 바꾸는 연산이므로 파일 rename만으로 충분하다.

> **save_outline_slide**: 기존 슬라이드를 덮어쓰는 용도로만 사용한다. 삽입은 `slide_edit(action="add")`가 내부적으로 처리한다.

> **읽기**: outline 파일에서 슬라이드 내용을 읽는다. 없으면 에러를 발생시킨다.

> **outline sync (`sync_outline_to_design_spec_count`)**: `slide_edit`(add/update/delete) 및 `move_slide` 실행 전에 outline 파일 수를 design_spec 파일 수에 맞춘다. outline이 design_spec보다 적으면 부족한 슬롯을 빈 placeholder(`title: "", content_summary: ""`)로 채워서 양쪽 수를 일치시킨다. 이를 통해 imported 프로젝트처럼 outline이 없거나 불완전한 상태에서도 인덱스 기반 CRUD가 안전하게 동작한다.

> **num_slides 동기화**: `slide_edit` 완료 시 `project.json`의 `num_slides`를 실제 디자인 스펙 파일 수와 자동 동기화한다.

### Technical Details

#### 도구 우선순위

```
export_html:     design_spec_json > project_id (자동 로드)
export_pptx:     design_spec_json > project_id (자동 로드)
```

#### project_id 기반 체이닝 (권장 흐름)

```
prepare_outline → ingest_outline
    → for i in 0..N-1:
        prepare_design_slide(slide_index=i) → ingest_design_slide(spec[i])
        (선택) prepare_slide_edit(action="update", slide_index=i) → ingest_slide_edit
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
| B. 전체 재생성만 지원 | slide_edit 없이 전체 디자인 스펙 재생성 | 비용/시간 비효율, 탈락 |
| C. 단일 파일 유지 + 부분 읽기 | JSON streaming parser로 필요한 슬라이드만 읽기 | JSON 구조상 부분 수정 불가, 탈락 |
| D. SQLite 기반 저장 | 슬라이드별 row로 관리 | 파일 기반 통신 원칙에 어긋남, 디버깅 어려움, 탈락 |
| **E. 파일 기반 통신 + 슬라이드별 파일 + CRUD** | project_id 참조 + 개별 파일 + 슬라이드 CRUD | **채택** |
| prepare에서 실제 파일을 먼저 이동 | ingest가 단순해짐 | 생성 실패·재시도 시 부분 상태와 중복 삽입이 발생해 제외 |
| prepare는 읽기 전용, ingest에서 원자 적용 | 재시도 안전성과 실패 격리 | 편집 컨텍스트와 rollback 관리가 필요하지만 채택 |

### Acceptance Criteria

1. `design_slide (prepare/ingest)` 반환에 `design_spec_json` 인라인 키가 없다
2. `export_html(project_id=...)` 만으로 HTML 슬라이드가 생성된다
3. `export_pptx(project_id=...)` 만으로 PPTX가 생성된다
4. `slide_edit`으로 개별 슬라이드 add/update/delete가 동작한다
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

- `slide_edit`의 add/update 시 디자인 요약 추출을 위한 추가 LLM 호출 필요
- project_id를 통한 암묵적 파일 의존성으로 디버깅 시 파일 상태 확인 필요
- 파일 삽입/삭제 시 재번호 로직 필요 (O(n) 파일 rename)
- 원자 커밋과 재시도 멱등성을 위해 편집 컨텍스트 및 완료 기록을 관리해야 한다.

## References

- 관련 ADR: [0007-pipeline-artifact-persistence](../project/0001-pipeline-artifact-persistence.md), [0013-design-spec-pipeline](../design/0001-design-spec-pipeline.md), [0016-per-slide-html-iframe](../slides/0001-per-slide-html-iframe.md)
