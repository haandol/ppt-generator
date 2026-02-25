# 16. 슬라이드별 HTML 파일 분리 및 iframe 컨테이너

Date: 2026-02-13

## Status

Accepted

## Context

디자인 스펙은 ADR-0015에서 `design_spec/slide_NN.json`으로 슬라이드별 파일 분리가 완료되었다. 그러나 HTML 슬라이드는 여전히 단일 `slides.html` 파일에 모든 슬라이드가 포함되어 있다.

기존 구조:
```
~/.ppt-generator/<UUID>/
  slides.html          # 모든 슬라이드 <section>이 포함된 단일 HTML 파일
  slides_meta.json     # 세션 메타 (session_id)
```

문제점:
1. **비대칭**: 디자인 스펙은 슬라이드별 파일(`design_spec/slide_NN.json`)인데, HTML은 단일 파일
2. **재생성 비효율**: `modify_design_spec`으로 1개 슬라이드만 수정해도 전체 HTML을 재생성해야 함
3. **파일 크기**: 슬라이드 수 증가 시 단일 HTML 파일이 비대해짐

## Decision

HTML 슬라이드를 슬라이드별 개별 파일로 분리하고, `slides.html`은 iframe으로 개별 슬라이드를 참조하는 컨테이너로 변경한다.

변경 후 구조:
```
~/.ppt-generator/<UUID>/
├── slides/
│   ├── slide_01.html       # 단일 슬라이드 HTML (완전한 HTML 문서)
│   ├── slide_02.html
│   └── ...
├── slides.html             # iframe 컨테이너 (각 슬라이드를 iframe으로 참조)
├── slides_meta.json        # 세션 메타 (session_id)
└── ...
```

### Technical Details

#### 파일 명명 규칙

- `slides/slide_{index+1:02d}.html` — design_spec과 동일한 규칙 (1-based, 2자리 zero-padded)

#### SlidesService 변경

| 메서드 | 변경 내용 |
|--------|-----------|
| `generate_from_design_spec()` | 반환타입 변경: `SlidesResponse(html=...)` → `SlidesResponse(slide_htmls=[...], container_html=...)`. 슬라이드별 개별 HTML 생성 + iframe 컨테이너 생성 |
| `_spec_to_html_document()` | 신규: 단일 PptxSlideSpec → 완전한 HTML 문서 변환 (`html_renderer.spec_to_html_section()` + 개별 슬라이드용 템플릿 래핑) |
| `_build_container_html()` | 신규: iframe 컨테이너 HTML 생성 |
| `_wrap_with_template()` | 제거: 단일 HTML 래핑 불필요 |

#### HTML 렌더러 분리 (html_renderer.py)

HTML 변환 로직은 `tools/slides/html_renderer.py`로 분리:
- `spec_to_html_section()` — PptxSlideSpec → `<section>` HTML 변환 (SlidesService에서 호출)
- `textbox_to_html()`, `shape_to_html()`, `paragraph_to_html()`, `run_to_html()`, `escape_html()` — 각 요소별 변환 함수

#### SlidesResponse 변경

```python
@dataclass(frozen=True)
class SlidesResponse:
    session_id: str
    slide_htmls: list[str]      # 슬라이드별 완전한 HTML 문서 리스트
    container_html: str          # iframe 컨테이너 HTML
```

#### ProjectService 변경

| 메서드 | 변경 내용 |
|--------|-----------|
| `save_slides_html()` | `slides/` 디렉토리에 슬라이드별 HTML 저장 + `slides.html` 컨테이너 저장 |

#### 슬라이드별 HTML 템플릿

각 슬라이드는 자체 `<head>`를 가진 완전한 HTML 문서이다. 기존 `slides.html` 템플릿의 CSS를 슬라이드별 인라인 스타일로 포함한다:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;600;800&display=swap" rel="stylesheet"/>
    <style>
        /* 슬라이드 공통 CSS (기본 리셋 + 폰트) */
    </style>
</head>
<body style="margin:0;overflow:hidden;">
    <section>...</section>
</body>
</html>
```

#### iframe 컨테이너 (`slides.html`)

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <title>Presentation</title>
    <style>
        body { background: #1a1a1a; display: flex; flex-direction: column; align-items: center; padding: 60px 20px; gap: 28px; }
        .slide-wrapper { display: flex; flex-direction: column; align-items: flex-start; width: 1280px; }
        .slide-number { font-size: 14px; color: #606366; padding: 0 12px 6px; }
        iframe { width: 1280px; height: 720px; border: none; border-radius: 8px; box-shadow: 0 4px 24px rgba(0,0,0,0.12); }
    </style>
</head>
<body>
    <div class="slide-wrapper">
        <div class="slide-number">1 / N</div>
        <iframe src="slides/slide_01.html"></iframe>
    </div>
    ...
</body>
</html>
```

#### 컨트롤러 반환값 변경

| 도구 | 이전 | 이후 |
|------|------|------|
| `export_html` | `slides_html_path` (단일 파일 경로) | `slides_html_path` (컨테이너 경로) + `slide_count` |

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. 단일 HTML 유지 | 현 구조 유지, modify_design_spec 후 전체 재생성 | 비대칭 해결 불가, 탈락 |
| B. SPA 방식 (JavaScript 네비게이션) | 단일 HTML에 JS로 슬라이드 전환 | 미리보기 용도에 과도, JavaScript 의존성 증가, 탈락 |
| **C. 슬라이드별 HTML + iframe 컨테이너** | 개별 HTML 파일 + iframe 참조 | **채택** |

### Acceptance Criteria

1. `export_html`로 생성 시 `slides/` 디렉토리에 슬라이드별 HTML 파일이 생성된다
2. `slides.html`이 iframe으로 각 슬라이드를 참조하는 컨테이너로 생성된다
3. 각 슬라이드 HTML은 단독으로 브라우저에서 열 수 있는 완전한 HTML 문서이다
4. 기존 `export_html` → `export_pptx` 체이닝이 정상 동작한다
5. `slides.html`을 브라우저에서 열면 모든 슬라이드가 iframe으로 표시된다

### Out of Scope

- 개별 슬라이드 HTML만 재생성하는 `modify_slides_html` 도구 (향후 필요 시 추가)
- iframe 대신 Shadow DOM 사용 (현 MVP에서 불필요)

## Consequences

### Positive

- **디자인 스펙과 대칭**: `design_spec/slide_NN.json` ↔ `slides/slide_NN.html` 1:1 대응
- **디버깅 용이**: 개별 슬라이드 HTML을 직접 열어 확인 가능
- **확장성**: 향후 개별 슬라이드 재생성 도구 추가 시 해당 파일만 덮어쓰면 됨
- **스타일 격리**: 각 슬라이드가 독립 문서이므로 CSS 충돌 없음

### Negative

- 파일 수 증가 (슬라이드당 1개 HTML 추가)
- 공통 CSS가 각 슬라이드 HTML에 중복 포함됨 (로컬 파일이므로 네트워크 비용 없음)
- iframe 사용으로 인한 미미한 렌더링 오버헤드

## References

- 슬라이드 서비스: `src/ppt_generator/tools/slides/service.py` — `generate_from_design_spec()`, `_spec_to_html_document()`, `_build_container_html()` (오케스트레이션)
- HTML 렌더러: `src/ppt_generator/tools/slides/html_renderer.py` — `spec_to_html_section()` 등 HTML 변환 함수
- 프로젝트 서비스: `src/ppt_generator/tools/project/service.py` — `save_slides_html()`
- 컨트롤러: `src/ppt_generator/tools/slides/controller.py`
- 스키마: `src/ppt_generator/interfaces/schemas.py` — `SlidesResponse`
- 템플릿: `src/ppt_generator/templates/slide.html` (슬라이드용), `src/ppt_generator/templates/slides_container.html` (iframe 컨테이너용)
- 테스트: `tests/test_slides_service.py`, `tests/test_slides_controller.py`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0015-per-slide-file-separation](./0015-per-slide-file-separation.md)
