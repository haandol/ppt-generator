# 디자인 스펙 기반 슬라이드 생성 파이프라인

Date: 2026-02-13

## Status

Accepted

## Context

기존 PPTX 내보내기 과정은 HTML 을 역분석하여 PPTX 요소로 변환하는 복잡한 3단계 폴백 체인(Playwright DOM 추출 → LLM 변환 → 룰 기반)을 사용했다. 이 방식의 문제:

1. **복잡성** — 3단계 폴백 체인은 유지보수 부담이 크다.
2. **부정확성** — HTML/CSS 의 시각적 렌더링 결과를 역분석해 좌표를 추출하므로 flex/grid 레이아웃 등 계산 결과가 부정확.
3. **의존성** — Playwright 브라우저 인스턴스 + 변환용 추가 LLM 호출(Sonnet 4.6) 비용.
4. **정보 손실** — LLM 이 자유 형식 HTML 을 생성한 후 다시 LLM 으로 PPTX 좌표를 추출하는 과정에서 디자인 의도가 손실.

## Decision

**디자인 스펙(PptxSlideSpec JSON) 을 파이프라인의 중간 표현** 으로 도입해, 단일 소스에서 HTML 과 PPTX 를 각각 *결정론적* 으로 생성한다.

```
Outline → Design Spec (LLM 생성)
             ├──→ HTML (결정론적 변환, 브라우저 미리보기)
             └──→ PPTX (SlideBuilder 직접)
```

### LLM 의 역할은 디자인 스펙 생성에 한정

LLM 은 절대 좌표(left/top/width/height) 와 스타일을 가진 PptxSlideSpec JSON 만 생성한다. HTML 과 PPTX 는 그 spec 으로부터 결정론적으로 생성되며, 이 두 출력 경로 사이에는 LLM 호출이 없다. 디자인 의도가 두 출력에서 정확히 동일하게 보존된다.

### 슬라이드 단위 생성 + 디자인 일관성

슬라이드별 개별 LLM 호출이며, 첫 슬라이드 생성 후 그 결과에서 디자인 요약(`design_summary`) 을 추출해 후속 슬라이드 생성에 전달한다. 폰트/색상/레이아웃 톤이 슬라이드 간 일관되게 유지되는 보장. design_summary 의 `color_theme` 필드는 dark/light 분기에 사용되며, 생성 프로젝트는 호출자가 지정, 임포트 프로젝트는 배경색 휘도로 자동 판별.

### MCP 도구 분리

- `prepare_design_slide` / `ingest_design_slide` — 슬라이드 단위 디자인 스펙 생성 (병렬성은 클라이언트, offload/0001).
- `prepare_slide_edit` / `ingest_slide_edit` — 개별 슬라이드 추가/수정 (modify/0001).
- `load_design_spec` — 저장된 디자인 스펙 로드.
- `export_html` / `export_pptx` — design_spec 을 받아 결정론적 변환.

### 영속화 위치

`~/.ppt-generator/<UUID>/design_spec/` 아래에 슬라이드별 개별 파일(`slide_NN.json`) 과 디자인 요약(`design_summary.json`) 을 저장한다. CRUD 는 ProjectService 에 위임된 별도 store 에서 전담.

### 렌더 순서 의미 보존

명시적인 렌더 순서가 있는 spec은 HTML과 PPTX 모두 동일한 순서로 요소를 쌓는다.
명시적인 순서가 하나라도 있으면 요소 종류별 고정 순서로 재배치하지 않는다. 명시적인
순서가 전혀 없는 기존 spec만 레거시 기본 순서를 사용한다.

## 대안 검토

| 대안 | 설명 | 채택하지 않은 이유 |
|---|---|---|
| HTML → PPTX 변환 개선 | DOM 추출 정확도 향상, LLM 프롬프트 개선 | 근본 한계(역분석) 해결 불가 |
| LLM 이 PPTX 코드 직접 생성 | python-pptx API 호출 코드를 LLM 이 작성 | LLM 의 API 코드 정확도 부족 |
| **디자인 스펙 중간 표현** | PptxSlideSpec JSON 단일 소스 | **채택** |

## Consequences

### Positive

- **정확성 향상** — 단일 소스에서 HTML/PPTX 생성하므로 변환 정보 손실 없음.
- **단순성** — PPTX 생성 시 3단계 폴백 체인 대신 SlideBuilder 직접 호출.
- **속도/비용** — Playwright/추가 LLM 호출 불필요로 wall time 과 비용 모두 감소.
- **단일 파이프라인** — 레거시 HTML 기반 경로 완전 제거.
- **렌더 일치성** — 명시된 요소 순서가 HTML 미리보기와 PPTX 최종본에서 동일하게
  유지된다.

### Negative / Risks

- 디자인 스펙 생성에 LLM 호출(Sonnet Extended Thinking) 필요.
- HTML 미리보기가 position:absolute 기반이라 Tailwind 기반보다 시각적으로 단순.
- LLM 이 정밀한 좌표를 생성해야 하므로 프롬프트 품질이 중요.

## References

- [project/0001 (project): 파이프라인 결과물 저장/로드](../project/0001-pipeline-artifact-persistence.md)
- [project/0002 (project): 점진적 구체화 파이프라인](../project/0002-progressive-refinement-pipeline.md)
- [modify/0001 (modify): 파일 기반 통신 + 슬라이드 단위 CRUD](../modify/0001-file-based-communication-and-per-slide-crud.md)
- [slides/0001 (slides): 슬라이드별 HTML iframe](../slides/0001-per-slide-html-iframe.md)
- [0002: 폰트 메트릭 기반 텍스트 오버플로우 방지](./0002-font-metric-text-overflow.md)
- [0003: 디자인 스펙 병렬 생성](./0003-parallel-design-spec.md)
- [0004: 슬라이드 타입별 시스템 프롬프트 분리](./0004-slide-type-specific-prompts.md)
- [lint/0003 (lint): Validator 를 Lint 로 전환](../lint/0003-validator-to-lint.md)
- [0011: 5단 디자인 스펙 계층](./0011-five-layer-design-spec-hierarchy.md)
