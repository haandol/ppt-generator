# 개별 파일 기반 outline 저장 및 save_outline_slide 도구

Date: 2026-03-09

## Status

Accepted (2026-03-09)

## Context

임포트된 프로젝트(`source="imported"`)에는 outline 파일이 존재하지 않는다.
기존 `slide_edit`의 `add`/`update` 액션은 outline 파일에서 슬라이드 아웃라인을 읽어
LLM으로 디자인 스펙을 생성하는 구조였기 때문에, 임포트된 프로젝트에서는 사용이 불가능했다.

초기 해결책으로 `slide_edit`에 `outline_json` 인라인 파라미터를 추가하는 방안을
검토했으나, 클라이언트 LLM과 MCP 서버 LLM이 다른 환경에서 동일 컨텐츠가 두 번 전송되어
토큰 낭비가 발생하는 문제가 있었다.

## Decision

### 1. outline 저장 형식을 슬라이드별 개별 파일로 전환

JSONL 단일 파일 대신 `design_spec/` 패턴과 동일한 슬라이드별 개별 파일 구조를 사용한다.
기존 JSONL/legacy JSON은 fallback으로 계속 지원한다 (개별 파일 → JSONL → legacy JSON 순으로 탐색).

### 2. `save_outline_slide` MCP 도구 추가

개별 슬라이드 아웃라인을 파일로 저장하는 새 MCP 도구를 추가한다. 이를 통해 클라이언트가
아웃라인 데이터를 한 번만 전송하면, 이후 `slide_edit`은 파일에서 직접 읽어 처리한다.

### 3. 임포트 프로젝트 워크플로우

```
1. save_outline_slide(project_id, slide_index, title, content_summary, ...)
   → 개별 파일로 저장 (토큰 1회)
2. slide_edit(project_id, action="add", slide_index=N)
   → 서버가 파일에서 읽음 (토큰 0회 추가)
```

생성 프로젝트와 동일한 파일 기반 패턴이므로, `slide_edit`의 코드 변경이 불필요하다.

### 4. Outline–Design Spec 수 동기화 (Placeholder Padding)

임포트된 프로젝트에서 outline이 없거나 design_spec보다 적은 상태에서 `slide_edit`(add/update/delete) 또는 `move_slide`을 호출하면, outline과 design_spec의 인덱스가 불일치하여 에러가 발생했다.

**문제 시나리오:**
```
import 20장 → outline 0장, design_spec 20장
add(끝에) → outline/slide_01.json (1장만 sparse 생성)
move_slide(from=16, to=11) → outline에 index 15가 없어 IndexError
```

**해결: `sync_outline_to_design_spec_count`**

`slide_edit`(add/update/delete) 및 `move_slide` 실행 전에, outline 파일 수가 design_spec 파일 수보다 적으면 빈 placeholder로 패딩하여 양쪽 수를 일치시킨다.

```python
# placeholder outline
{"title": "", "content_summary": "", "slide_type": "content",
 "component_hint": "bullets", "speaker_notes": ""}
```

| outline 상태 | 동작 |
|---|---|
| outline 0장, design_spec 20장 | outline 20장 전체를 placeholder로 생성 |
| outline 10장, design_spec 20장 | 11~20번 슬롯에 placeholder 10장 추가 |
| outline == design_spec | 아무것도 안 함 |

이를 통해 기존의 sparse outline 방식을 제거하고, outline과 design_spec이 항상 1:1 대응하는 상태를 보장한다. `save_outline_slide`나 `slide_edit(update)`로 실제 내용이 입력되면 해당 placeholder가 실제 아웃라인으로 교체된다.

### Technical Details

- **저장소 리팩토링**: 개별 파일 기반 CRUD + JSONL/legacy fallback
- **삽입/삭제 시 재번호**: 파일명과 내부 `slide_index`를 동시 갱신 (2-pass tmp rename으로 충돌 방지)

### Alternatives Considered

1. **`slide_edit`에 `outline_json` 인라인 파라미터**: 클라이언트-서버 간 토큰 2배 소비 — 클라이언트 LLM이 컨텍스트에 내용을 보유한 채 MCP 서버에 동일 내용을 전송
2. **JSONL에 더미 라인 채우기**: 더미와 실제 데이터 구분 불가, 삽입/삭제 시 관리 복잡
3. **Sparse outline 유지 + controller에서 범위 체크**: outline 범위 밖 인덱스의 CRUD를 skip하는 방식. outline과 design_spec의 인덱스가 1:1 대응하지 않아, delete/move 시 잘못된 슬라이드가 영향받는 문제 발생 — 탈락

### Acceptance Criteria

- [x] 개별 파일 기반 outline 저장
- [x] JSONL/legacy JSON fallback 유지
- [x] `save_outline_slide` MCP 도구로 개별 슬라이드 아웃라인 저장
- [x] 임포트 프로젝트에서 `save_outline_slide` → `slide_edit` add/update 워크플로우
- [x] `sync_outline_to_design_spec_count`로 outline-design_spec 수 항상 일치
- [x] imported 프로젝트에서 add/update/delete/move가 에러 없이 동작
- [x] 전체 테스트 통과

## Consequences

**긍정적:**
- 임포트 프로젝트에서 LLM 기반 슬라이드 삽입/대체 가능
- design_spec과 동일한 개별 파일 패턴으로 구조적 일관성
- 파일 기반이므로 클라이언트-서버 간 토큰 낭비 없음
- 기존 JSONL 프로젝트 하위 호환성 유지
- outline과 design_spec 수가 항상 일치하여 인덱스 기반 CRUD가 안전하게 동작
- controller의 범위 체크 분기가 불필요해져 코드 단순화

**부정적:**
- 삽입/삭제 시 파일 재번호 오버헤드 (슬라이드 수 20~30장 이하로 미미)
- imported 프로젝트의 미수정 슬라이드에 빈 placeholder outline 파일이 생성됨 (디스크 공간 미미)

## References

- [0001: 파일 기반 통신, 슬라이드 단위 CRUD](./0001-file-based-communication-and-per-slide-crud.md)
- [import/0001 (import): PPTX 임포트](../import/0001-pptx-import-to-design-spec.md)
