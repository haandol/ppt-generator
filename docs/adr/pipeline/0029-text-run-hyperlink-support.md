# 29. 텍스트 런 하이퍼링크 지원

Date: 2026-03-31

## Status

Accepted

## Context

디자인 스펙의 텍스트 런(`PptxTextRun`)에 하이퍼링크(URL) 속성이 없어서, LLM이 생성하거나 PPTX에서 임포트한 텍스트에 걸린 하이퍼링크가 모두 손실되었다.

- LLM이 디자인 스펙 생성 시 링크가 있는 텍스트를 표현할 수 없음
- PPTX 임포트 시 원본 파일의 하이퍼링크가 무시됨
- HTML/PPTX 내보내기 모두 링크 렌더링 불가

## Decision

`PptxTextRun` dataclass와 `TextRunOutput` Pydantic 모델에 `href: str | None` 필드를 추가하고, 파이프라인 전 구간(프롬프트, PPTX 임포트, HTML 렌더링, PPTX 내보내기)에서 이를 지원한다.

### Technical Details

**스키마 변경:**
- `PptxTextRun` (dataclass): `href: str | None = None` 추가
- `TextRunOutput` (Pydantic): `href: str | None = None` 추가
- `SlideSpecOutput.to_dataclass()`: `href` 필드 전달

**LLM 프롬프트:**
- `design_system_base.prompt.md`의 `output_schema` runs 항목에 `"href": "https://..."|null` 추가

**HTML 렌더링** (`text_renderer.py`):
- `href`가 있으면 `<a href="..." target="_blank" rel="noopener noreferrer">` 태그로 감싸기
- `color:inherit; text-decoration:underline` 스타일 적용

**PPTX 내보내기** (`text_formatter.py`):
- `href`가 있으면 `run_obj.hyperlink.address = run_spec.href` 설정 (python-pptx 내장 API)

**PPTX 임포트** (`text_extractor.py`):
- `run.hyperlink.address`에서 URL 추출하여 `href` 필드에 저장

### Acceptance Criteria

- 디자인 스펙 JSON에 `href` 필드가 포함될 수 있다
- HTML 미리보기에서 하이퍼링크가 클릭 가능한 `<a>` 태그로 렌더링된다
- PPTX 내보내기에서 하이퍼링크가 보존된다
- PPTX 임포트 시 원본의 하이퍼링크가 추출된다

## Consequences

**긍정적:**
- 하이퍼링크가 포함된 프레젠테이션을 완전히 지원
- 임포트/내보내기 간 하이퍼링크 라운드트립 보존
- `href`는 optional 필드이므로 기존 디자인 스펙과 하위 호환

**부정적:**
- LLM이 불필요한 상황에서 `href`를 생성할 가능성 (프롬프트로 제어)

## References

- `src/ppt_generator/interfaces/schemas.py` — `PptxTextRun` dataclass
- `src/ppt_generator/interfaces/llm_output_models.py` — `TextRunOutput` Pydantic 모델
- `src/ppt_generator/interfaces/prompts/design_system_base.prompt.md` — 디자인 시스템 프롬프트
- `src/ppt_generator/tools/slides/text_renderer.py` — HTML 렌더러
- `src/ppt_generator/tools/pptx/text_formatter.py` — PPTX 텍스트 포매터
- `src/ppt_generator/tools/pptx_import/text_extractor.py` — PPTX 텍스트 추출기
