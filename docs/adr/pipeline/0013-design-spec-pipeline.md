# 13. 디자인 스펙 기반 슬라이드 생성 파이프라인

Date: 2026-02-13

## Status

Accepted

## Context

기존 PPTX 내보내기 과정은 HTML을 역분석하여 PPTX 요소로 변환하는 복잡한 3단계 폴백 체인(DOM 추출 → LLM 변환 → 룰 기반)을 사용하고 있다.

```
기존: Outline → Script → HTML (LLM 생성) → PPTX (DOM추출/LLM변환/룰기반 폴백)
```

이 방식의 문제점:

1. **복잡성**: Playwright DOM 추출, LLM 변환, 룰 기반 폴백의 3단계 체인이 복잡하고 유지보수 어려움
2. **부정확성**: HTML/CSS의 시각적 렌더링 결과를 역분석하여 좌표를 추출하므로, flex/grid 레이아웃 등의 계산 결과가 부정확할 수 있음
3. **의존성**: Playwright 브라우저 인스턴스가 필요하고, 추가 LLM 호출(Sonnet 4.6) 비용 발생
4. **정보 손실**: LLM이 자유 형식 HTML을 생성한 후 다시 LLM으로 PPTX 좌표를 추출하는 과정에서 디자인 의도가 손실됨

## Decision

**디자인 스펙(PptxSlideSpec JSON)**을 파이프라인의 중간 표현으로 도입하여, 단일 소스에서 HTML과 PPTX를 각각 결정론적으로 생성한다.

```
변경 후: Outline → Script → Design Spec (LLM 생성)
                                  ├──→ HTML (결정론적 변환, 브라우저 미리보기용)
                                  └──→ PPTX (SlideBuilder 직접 사용)
```

### Technical Details

#### 디자인 스펙 스키마

기존 `PptxSlideSpec` 데이터클래스에 `speaker_notes` 필드를 추가하고, 전체 프레젠테이션을 나타내는 `DesignSpec(slides: list[PptxSlideSpec])` 래퍼를 도입한다.

```python
@dataclass(frozen=True)
class PptxSlideSpec:
    background_color: str | None = None
    textboxes: list[PptxTextBox] = field(default_factory=list)
    shapes: list[PptxShape] = field(default_factory=list)
    images: list[PptxImage] = field(default_factory=list)
    speaker_notes: str = ""

@dataclass(frozen=True)
class DesignSpec:
    slides: list[PptxSlideSpec] = field(default_factory=list)
```

#### 새 MCP 도구

| 도구                          | 설명                                                                       |
| ----------------------------- | -------------------------------------------------------------------------- |
| `generate_slides_design_spec` | 전체/선택적 슬라이드 디자인 스펙 병렬 생성 ([ADR-0018](./0018-parallel-design-spec-and-prompt-caching.md)) |
| `modify_design_spec`          | 개별 슬라이드 추가/수정/삭제 ([ADR-0014](./0014-file-based-communication-and-per-slide-crud.md))           |
| `load_design_spec`            | 저장된 디자인 스펙 로드                                                    |

#### 기존 도구 변경

| 도구              | 변경 내용                                                        |
| ----------------- | ---------------------------------------------------------------- |
| `export_html`     | `design_spec_json` 파라미터 추가. 제공 시 결정론적 HTML 변환     |
| `export_pptx`     | `design_spec_json` 파라미터 추가. 제공 시 SlideBuilder 직접 사용 |

#### 디자인 스펙 생성 서비스 (DesignService)

- `tools/design/service.py` — `DesignService.generate_single_slide()`
- 슬라이드별 개별 LLM 호출
- 첫 슬라이드 생성 후 `extract_design_summary()` → 후속 슬라이드에 전달하여 일관성 유지
- `parse_slide_spec()` + `validate_slide_spec()` 재사용 (`interfaces/spec_utils/`)
- LLM structured_output용 Pydantic 모델: `interfaces/llm_output_models.py` — `SlideSpecOutput`
- Bedrock Claude Sonnet 4.6 사용 (`global.anthropic.claude-sonnet-4-6`, 64K tokens)
- 슬라이드 타입별 시스템 프롬프트 분리 ([ADR-0021](./0021-slide-type-specific-system-prompts.md))

#### 디자인 시스템 프롬프트 — 레이아웃 규칙

`design_system.prompt.md` (현재 slide_type별로 분리됨, [ADR-0021](./0021-slide-type-specific-system-prompts.md) 참조)에 다음 규칙들이 포함되어 있다:

**좌표 시스템:**

| 항목 | 값 |
|------|-----|
| 캔버스 | 1280 × 720px |
| 제목 위치 (content) | top=72, height=48 |
| 본문 시작 (content) | top=148 |
| 본문 영역 높이 | 508px (148~656) |
| 수직 그리드 셀 | 25px × 20행 |

**slide_type별 메인 텍스트 위치:**

| slide_type | 메인 텍스트 top | 설명 |
|------------|----------------|------|
| content | 72 | 상단 제목 위치 |
| title | 260 | 수직 중앙 배치 |
| closing | 240 | 수직 중앙 배치 |

**주요 제약조건:**

- 서로 다른 역할의 요소도 bounding box 겹침 금지
- 같은 행 요소의 좌표 일관성 (예: 하단 info badge `top_px=626, height_px=30` 통일)
- 하단 보조 요소(`top_px >= 540`) 2개 이상 배치 시 수직/수평 분리 필수
- 블록 간 화살표 배치 시 수평/수직 모두 최소 28px gap 확보 필수
- 여백(negative space) 활용 — 빈 공간을 채우려 하지 말고 시각적 여유로 핵심 콘텐츠 강조
- 기존 shape 속성(border_color, fill_color 등) 조합으로 시각적 계층 구조 강화
- 장식용 라인(수평: height≤10px, 수직: width≤10px)과 카드 배치 시 동일 top_px/height_px, 라인 right edge = 카드 left edge
- `design_summary_user.prompt.md`에서 프레젠테이션 목적/톤(기술 교육 vs 의사결정 제안, 경영진 vs 엔지니어)을 파악하여 디자인 방향 조정

**렌더러/validator 안전망:**

- `html_renderer.py`의 `_line_shape_to_html()`에서 선 길이가 짧으면 화살표 머리(markerWidth/markerHeight)를 `line_length * 0.6`으로 자동 축소
- validator의 검증·보정 규칙 상세는 [ADR-0023](./0023-design-spec-validator.md) 참조

#### Design Spec → HTML 변환

- `SlidesService.generate_from_design_spec()` — LLM 호출 없는 결정론적 변환 (오케스트레이션)
- HTML 렌더링 로직은 `tools/slides/html_renderer.py`에 분리:
  - `spec_to_html_section()` — PptxSlideSpec → `<section>` HTML 변환
  - `shape_to_html()` — shapes → `<div>` (배경색, 테두리, border-radius)
  - `textbox_to_html()` — textboxes → `<div>` (text runs → `<span>` with inline font styles)
  - `paragraph_to_html()` — paragraphs/bullets → `<p>`, `<ul>/<li>` 구조
- `SlidesService._spec_to_html_document()`가 렌더러 + 템플릿 조합

#### Design Spec → PPTX 변환

- `ExportService.export_from_design_spec()` — SlideBuilder 직접 사용
- DOM 추출/LLM 변환/HTML 파싱 전혀 불필요
- `DesignSpec.slides` 순회 → `SlideBuilder.build_slide_from_spec()` 직접 호출
- run/paragraph 포매팅 공통 로직은 `tools/pptx/text_formatter.py`에 분리 (textbox/shape 간 중복 제거)
- `speaker_notes`는 `PptxSlideSpec`에서 직접 읽어 설정

#### 공유 유틸리티

`interfaces/spec_utils/` 패키지에 다음 함수를 통합:

- `parse_slide_spec()` / `validate_slide_spec()` — parser.py, validator.py
- `design_spec_to_json()` / `parse_design_spec_json()` — serializer.py, parser.py
- `slide_spec_to_json()` / `parse_slide_spec_json()` — serializer.py, parser.py

#### 프로젝트 영속화

- `~/.ppt-generator/<UUID>/design_spec/slide_NN.json` — 슬라이드별 개별 파일 저장 ([ADR-0014](./0014-file-based-communication-and-per-slide-crud.md))
- `~/.ppt-generator/<UUID>/design_spec/design_summary.json` — 첫 슬라이드에서 추출한 디자인 테마 요약 (슬라이드별 생성 시 테마 일관성 유지용)
- 디자인 스펙 파일 CRUD는 `DesignSpecStore` (`tools/project/design_spec_store.py`)에 전담:
  - `save_design_spec`, `load_design_spec`, 슬라이드별 CRUD, 디자인 요약 관리
- `ProjectService`는 `DesignSpecStore`에 위임 (composition)

### Alternatives Considered

| 대안                         | 설명                                            | 판단                                  |
| ---------------------------- | ----------------------------------------------- | ------------------------------------- |
| A. HTML → PPTX 변환 개선     | DOM 추출 정확도 향상, LLM 프롬프트 개선         | 근본적 한계(역분석) 해결 불가, 탈락   |
| B. LLM이 PPTX 코드 직접 생성 | python-pptx API 호출 코드를 LLM이 생성          | LLM의 API 코드 생성 정확도 부족, 탈락 |
| **C. 디자인 스펙 중간 표현** | PptxSlideSpec JSON을 단일 소스로 HTML/PPTX 생성 | **채택**                              |

### Acceptance Criteria

1. `generate_slide_design_spec`으로 아웃라인에서 PptxSlideSpec JSON이 생성된다
2. `export_html(design_spec_json=...)`으로 결정론적 HTML이 생성된다
3. `export_pptx(design_spec_json=...)`으로 PPTX가 직접 생성된다
4. 디자인 스펙이 프로젝트 디렉토리에 영속화된다
5. 후속 슬라이드가 첫 슬라이드와 일관된 디자인을 유지한다

### Out of Scope

- ~~디자인 스펙 수정 도구 (modify_design_spec)~~ → [ADR-0014](./0014-file-based-communication-and-per-slide-crud.md)에서 구현됨
- ~~기존 HTML → PPTX 폴백 경로 제거~~ → 레거시 경로 완전 제거 완료

## Consequences

### Positive

- **정확성 향상**: 단일 소스에서 HTML/PPTX를 생성하므로 변환 과정의 정보 손실 없음
- **단순성**: PPTX 생성 시 3단계 폴백 체인 대신 SlideBuilder 직접 호출
- **속도**: PPTX 생성 시 Playwright/추가 LLM 호출 불필요
- **비용 절감**: PPTX 변환용 Sonnet 4.6 호출 제거
- **단일 파이프라인**: 레거시 HTML 기반 경로를 완전 제거하여 코드 단순화 달성

### Negative

- 디자인 스펙 생성에 추가 LLM 호출(Sonnet 4.6 Extended Thinking) 필요
- HTML 미리보기가 position:absolute 기반이라 기존 Tailwind CSS 기반보다 시각적으로 단순할 수 있음
- LLM이 정밀한 좌표를 생성해야 하므로 프롬프트 품질이 중요

## References

- 디자인 서비스: `src/ppt_generator/tools/design/` (service.py, controller.py)
- LLM 출력 모델: `src/ppt_generator/interfaces/llm_output_models.py` — `SlideSpecOutput`
- 도메인 스키마: `src/ppt_generator/interfaces/schemas.py` — `DesignSpec`, `PptxSlideSpec`
- 유틸리티: `src/ppt_generator/interfaces/spec_utils/` — `parse_slide_spec`, `validate_slide_spec`, `slide_spec_to_json`, `parse_slide_spec_json`, `design_spec_to_json`, `parse_design_spec_json`
- 텍스트 측정: `src/ppt_generator/interfaces/text_measurement.py` — 폰트 메트릭 기반 줄바꿈/높이 계산 ([ADR-0017](./0017-font-metric-text-overflow-prevention.md))
- 프롬프트: `src/ppt_generator/interfaces/prompts/` — slide_type별 시스템 프롬프트 ([ADR-0021](./0021-slide-type-specific-system-prompts.md))
- 슬라이드 서비스: `src/ppt_generator/tools/slides/service.py` — `generate_from_design_spec()`
- HTML 렌더러: `src/ppt_generator/tools/slides/html_renderer.py` — `spec_to_html_section()`
- PPTX 서비스: `src/ppt_generator/tools/pptx/service.py` — `export_from_design_spec()`
- 텍스트 포매터: `src/ppt_generator/tools/pptx/text_formatter.py` — run/paragraph 공통 포매팅
- 프로젝트 서비스: `src/ppt_generator/tools/project/service.py` — `save_design_spec()`, `load_design_spec()` (DesignSpecStore에 위임)
- 디자인 스펙 저장소: `src/ppt_generator/tools/project/design_spec_store.py` — 디자인 스펙 파일 CRUD
- DI 컨테이너: `src/ppt_generator/di/container.py` — `_create_design_agent()`, `design_service` 프로퍼티
- MCP 서버: `src/ppt_generator/server.py` — `register_design_tools()` 호출
- Spec 검증: `src/ppt_generator/interfaces/spec_utils/validator.py` — [ADR-0023](./0023-design-spec-validator.md) 참조
- 관련 ADR: [0007-pipeline-artifact-persistence](./0007-pipeline-artifact-persistence.md), [0011-progressive-refinement-pipeline](./0011-progressive-refinement-pipeline.md), [0014-file-based-communication-and-per-slide-crud](./0014-file-based-communication-and-per-slide-crud.md), [0016-per-slide-html-iframe](./0016-per-slide-html-iframe.md), [0017-font-metric-text-overflow-prevention](./0017-font-metric-text-overflow-prevention.md), [0021-slide-type-specific-system-prompts](./0021-slide-type-specific-system-prompts.md), [0023-design-spec-validator](./0023-design-spec-validator.md)
