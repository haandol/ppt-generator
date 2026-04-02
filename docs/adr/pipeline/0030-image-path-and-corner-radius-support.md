# 30. 이미지 image_path 및 corner_radius_px 지원

Date: 2026-04-02

## Status

Accepted

## Context

디자인 스펙의 `PptxImage`는 PPTX 임포트로 추출된 이미지만 지원했다. 임포트 시 `image_bytes`가 `slides/images/`에 저장되고 `src` 상대경로로 참조하는 구조였다.

그러나 디자인 스펙 JSON에 외부 이미지를 직접 지정하려면 절대경로나 URL을 사용해야 하는데, 이를 처리하는 경로가 없었다:

- 디자인 스펙 JSON에 `image_path`(절대경로/URL)를 수동으로 넣어도 파서가 인식하지 못함
- `slides/images/`에 이미지가 복사되지 않아 HTML에서 플레이스홀더만 표시
- PPTX 내보내기 시 `image_bytes`가 비어 이미지가 누락
- `corner_radius_px` 필드가 없어 둥근 모서리 이미지를 표현할 수 없음

## Decision

`PptxImage`에 `image_path`와 `corner_radius_px` 필드를 추가하고, 파이프라인 전 구간에서 이를 지원한다.

### Technical Details

**스키마 변경 (`schemas.py`):**
- `PptxImage`에 `image_path: str = ""` 추가 (로컬 절대경로 또는 외부 URL)
- `PptxImage`에 `corner_radius_px: float | None = None` 추가

**파서 (`spec_utils/parser.py`):**
- `image_path`, `corner_radius_px` 필드 파싱 추가

**직렬화 (`spec_utils/serializer.py`):**
- `image_bytes` 제거 시 빈 `image_path`와 `None` `corner_radius_px`도 함께 정리

**이미지 동기화 (`project/service.py`):**
- `sync_image_paths()`: `image_path`가 있고 `src`가 없는 이미지를 `slides/images/`에 복사/다운로드하고 `src`를 설정. 디자인 스펙 파일도 업데이트.
  - 로컬 파일: `shutil.copy2()`로 복사
  - 외부 URL (`http://`, `https://`): `httpx`로 다운로드
- `_resolve_image_bytes()`: PPTX 내보내기 시 `src` → `image_path` → URL 순으로 `image_bytes` 복원
- `export_html` 컨트롤러에서 `sync_image_paths()`를 이미지 경로 조회 전에 호출

**HTML 렌더링 (`html_renderer.py`):**
- `image_to_html()`에서 `corner_radius_px`가 있으면 `border-radius` CSS 적용

### Alternatives Considered

1. **`src` 필드에 절대경로/URL을 직접 저장**: 기존 `src`는 `slides/images/` 기준 상대경로 규약이 있어 혼용하면 혼란. 별도 필드가 명확.
2. **이미지를 항상 base64로 인라인**: JSON 크기가 폭발적으로 증가하고, 이미지 업데이트 시 전체 JSON을 다시 써야 함.

### Acceptance Criteria

- 디자인 스펙 JSON에 `image_path`(로컬 절대경로)를 지정하면 HTML/PPTX에 이미지가 정상 렌더링됨
- 디자인 스펙 JSON에 `image_path`(외부 URL)를 지정하면 이미지가 다운로드되어 렌더링됨
- `corner_radius_px`가 있으면 HTML에서 둥근 모서리로 표시됨
- 기존 `src` 기반 이미지 동작에 영향 없음 (하위 호환)

### Out of Scope

- LLM 디자인 스펙 생성 시 `image_path` 자동 지정 (별도 기능)
- PPTX 내보내기 시 `corner_radius_px` 반영 (python-pptx 제약)

## Consequences

**긍정적:**
- 외부 이미지를 디자인 스펙에 직접 참조 가능 (로컬 파일, URL 모두 지원)
- `sync_image_paths()`가 자동으로 `slides/images/`에 복사하고 `src`를 설정하므로 이후 렌더링이 일관적
- `corner_radius_px`로 HTML 미리보기에서 둥근 모서리 이미지 표현 가능
- 모든 필드가 optional이므로 기존 디자인 스펙과 하위 호환

**부정적:**
- 외부 URL 다운로드 시 네트워크 지연 발생 가능
- PPTX 내보내기에서는 `corner_radius_px`가 미지원 (python-pptx 제약)

## References

- `src/ppt_generator/interfaces/schemas.py` — `PptxImage` dataclass
- `src/ppt_generator/interfaces/spec_utils/parser.py` — 디자인 스펙 파서
- `src/ppt_generator/interfaces/spec_utils/serializer.py` — 디자인 스펙 직렬화
- `src/ppt_generator/tools/project/service.py` — `sync_image_paths()`, `_resolve_image_bytes()`
- `src/ppt_generator/tools/slides/html_renderer.py` — `image_to_html()`
- `src/ppt_generator/tools/slides/controller.py` — `export_html()`
