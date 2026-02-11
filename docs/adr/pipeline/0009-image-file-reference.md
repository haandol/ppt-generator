# 9. 이미지 파일 참조 방식 전환 (base64 임베딩 제거)

Date: 2026-02-11

## Status

Accepted

## Context

F3(generate_slides)가 이미지를 base64 data URI로 HTML에 임베딩하고 있어, 이미지 포함 시 HTML이 수 MB로 커지는 문제가 발생한다:

- MCP 응답 토큰 한도 초과
- F4(modify_slides)에서 LLM에 전달되는 HTML의 토큰 급증
- 세션 메모리 사용량 증가

## Decision

이미지를 워킹 디렉토리에 파일로 유지하고, HTML에서는 `file://` 절대 경로로 참조하도록 전환한다.

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. base64 data URI 유지 | 현행 방식, 단일 HTML 파일로 완결 | 토큰/메모리 문제 심각, 탈락 |
| B. HTTP 서버로 이미지 서빙 | 로컬 서버를 띄워 이미지 URL 제공 | 추가 인프라 필요, 과도, 탈락 |
| **C. file:// 절대 경로 참조** | 파일 시스템 경로를 직접 참조 | **채택** |

### Technical Details

변경 포인트:

1. `SlidesService._replace_image_placeholders()`: `{IMAGE_N}` → `file://<절대경로>`로 치환 (base64 인코딩 제거)
2. `SlidesService._sessions`: `dict[str, str]` → `dict[str, tuple[str, dict[int, str]]]` (HTML + image_paths 저장)
3. `ExportService._add_picture()`: `file://` 경로에서 파일 직접 읽기
4. `ProjectService.save_slides_html()` / `load_slides_html()`: image_paths도 함께 저장/복원
5. `SLIDES_MODIFY_SYSTEM_PROMPT`: data URI → file:// 경로 안내로 변경

### Acceptance Criteria

1. generate_slides 결과 HTML에 `file://` 경로가 포함된다 (base64 data URI 없음)
2. export_pptx가 file:// 경로에서 이미지를 읽어 PPTX에 삽입한다
3. modify_slides에서 file:// 경로가 유지된다
4. 프로젝트 저장/로드 시 image_paths가 함께 보존된다
5. 기존 테스트가 모두 통과한다

### Out of Scope

- 원격 URL(http/https) 이미지 참조
- 이미지 캐싱/정리 정책

## Consequences

### Positive

- MCP 응답 크기 대폭 감소 (수 MB → 수 KB)
- F5 modify_slides 시 LLM 토큰 비용 절감
- 세션 메모리 사용량 감소

### Negative

- 이미지 원본 파일이 삭제되면 HTML에서 참조 깨짐 (프로젝트 저장 기능으로 완화)
- 브라우저에서 직접 HTML 미리보기 시 file:// 프로토콜 제한 가능

## References

- 수정: `src/ppt_generator/tools/slides/service.py`, `src/ppt_generator/tools/pptx/service.py`, `src/ppt_generator/tools/project/service.py`
- 상수: `src/ppt_generator/interfaces/constants.py`
- 관련 ADR: [0004](./0004-html-slide-generation.md), [0006](./0006-pptx-export.md), [0007](./0007-pipeline-artifact-persistence.md)
