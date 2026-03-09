# 28. 개별 파일 기반 outline/script 저장 및 save_outline_slide 도구

Date: 2026-03-09

## Status

Accepted

## Context

임포트된 프로젝트(`source="imported"`)에는 outline/script 파일이 존재하지 않는다.
기존 `modify_design_spec`의 `add`/`update` 액션은 outline/script 파일에서 슬라이드 아웃라인을 읽어
LLM으로 디자인 스펙을 생성하는 구조였기 때문에, 임포트된 프로젝트에서는 사용이 불가능했다.

초기 해결책으로 `modify_design_spec`에 `outline_json` 인라인 파라미터를 추가하는 방안을
검토했으나, 클라이언트 LLM과 MCP 서버 LLM이 다른 환경에서 동일 컨텐츠가 두 번 전송되어
토큰 낭비가 발생하는 문제가 있었다.

## Decision

### 1. outline/script 저장 형식을 슬라이드별 개별 파일로 전환

JSONL 단일 파일 대신 `design_spec/` 패턴과 동일한 슬라이드별 개별 파일 구조를 사용한다.
기존 JSONL/legacy JSON은 fallback으로 계속 지원한다 (개별 파일 → JSONL → legacy JSON 순으로 탐색).

### 2. `save_outline_slide` MCP 도구 추가

개별 슬라이드 아웃라인을 파일로 저장하는 새 MCP 도구를 추가한다. 이를 통해 클라이언트가
아웃라인 데이터를 한 번만 전송하면, 이후 `modify_design_spec`은 파일에서 직접 읽어 처리한다.

### 3. 임포트 프로젝트 워크플로우

```
1. save_outline_slide(project_id, slide_index, title, content_summary, ...)
   → 개별 파일로 저장 (토큰 1회)
2. modify_design_spec(project_id, action="add", slide_index=N)
   → 서버가 파일에서 읽음 (토큰 0회 추가)
```

생성 프로젝트와 동일한 파일 기반 패턴이므로, `modify_design_spec`의 코드 변경이 불필요하다.

### Technical Details

- **저장소 리팩토링**: 개별 파일 기반 CRUD + JSONL/legacy fallback
- **Sparse 파일 지원**: `save_outline_slide`로 특정 인덱스만 저장 가능 (임포트 프로젝트에서 전체 슬라이드의 아웃라인이 없어도 특정 슬라이드만 저장)
- **삽입/삭제 시 재번호**: 파일명과 내부 `slide_index`를 동시 갱신 (2-pass tmp rename으로 충돌 방지)

### Alternatives Considered

1. **`modify_design_spec`에 `outline_json` 인라인 파라미터**: 클라이언트-서버 간 토큰 2배 소비 — 클라이언트 LLM이 컨텍스트에 내용을 보유한 채 MCP 서버에 동일 내용을 전송
2. **JSONL에 더미 라인 채우기**: 더미와 실제 데이터 구분 불가, 삽입/삭제 시 관리 복잡

### Acceptance Criteria

- [x] 개별 파일 기반 outline/script 저장
- [x] JSONL/legacy JSON fallback 유지
- [x] `save_outline_slide` MCP 도구로 개별 슬라이드 아웃라인 저장
- [x] 임포트 프로젝트에서 `save_outline_slide` → `modify_design_spec` add/update 워크플로우
- [x] 전체 테스트 통과

## Consequences

**긍정적:**
- 임포트 프로젝트에서 LLM 기반 슬라이드 삽입/대체 가능
- design_spec과 동일한 개별 파일 패턴으로 구조적 일관성
- 파일 기반이므로 클라이언트-서버 간 토큰 낭비 없음
- 기존 JSONL 프로젝트 하위 호환성 유지

**부정적:**
- 삽입/삭제 시 파일 재번호 오버헤드 (슬라이드 수 20~30장 이하로 미미)

## References

- [ADR-0014: 파일 기반 통신, 슬라이드 단위 CRUD](./0014-file-based-communication-and-per-slide-crud.md)
- [ADR-0027: PPTX 임포트](./0027-pptx-import-to-design-spec.md)
