# Architecture Decision Records (ADR)

이 디렉토리는 PPT Generator 프로젝트의 주요 아키텍처 결정을 카테고리별로 모아 둔다.

## ADR 이란?

소프트웨어 개발 과정에서 내린 중요한 아키텍처 결정의 *왜* 와 *무엇* 을 기록한다. 각 ADR 은:

- **Context** — 결정이 필요했던 배경/문제
- **Decision** — 내린 결정과 그 이유
- **Consequences** — 긍정/부정 영향

## 카테고리 구조

피쳐 단위 vertical slice 와 정렬한다. `docs/adr/.mapping.json` 이 카테고리별 ADR의
경로·상태·핵심 결정을 보관하는 단일 인덱스다. 코드 경로는 저장하지 않으며, ADR을 읽고
저장소를 검색해 매 실행 시점의 구현 범위를 찾는다.

```
docs/adr/
├── outline/    슬라이드 outline 생성 — tools/outline/, prompts/outline_*
├── design/     design spec 생성 + 5단 계층 — tools/design/, llm_output_models, schemas
├── lint/       lint rule + validator → lint 전환 — interfaces/spec_utils/lint*
├── modify/     슬라이드/component 부분 수정 — tools/design/handlers/modification.py
├── slides/     슬라이드 HTML 미리보기 — tools/slides/
├── pptx-export/ PPTX 내보내기 — tools/pptx/
├── import/     PPTX 임포트 — tools/pptx_import/
├── visual-qa/  스크린샷 기반 자동 QA — tools/visual_qa/
├── project/    파이프라인 인프라 (저장, 토큰/비용, 진행률, 안정성) — tools/project/, infra
├── script/     발표 스크립트 생성 (deprecated, 코드 제거 — speaker_notes 는 design_doc 로 흡수)
├── template/   PPTX 템플릿 분석 (proposed) — 미구현
├── chart/      차트/데이터 시각화 (proposed) — 미구현
└── offload/    LLM 생성을 클라이언트로 오프로딩 — 플러그인 + 스킬 + prepare/ingest
```

## ADRs

아래 목록은 사람이 빠르게 탐색하기 위한 목차다. 자동화가 사용하는 정식 인덱스와 상태는
`docs/adr/.mapping.json`을 기준으로 한다.

### outline — 슬라이드 outline 생성

- [0001 슬라이드 아웃라인 생성 (F1)](./outline/0001-outline-generation.md)
- [0002 Agenda Slide Optional Numbering](./outline/0002-agenda-optional-numbering.md)
- [0003 Outline 생성에 Medium Thinking 활성화](./outline/0003-outline-thinking-medium.md) — _Superseded by offload/0001_
- [0004 레이아웃 계획 단계 추가 (Layout Planning Phase)](./outline/0004-layout-planning-phase.md)
- [0005 load_outline 에 include_content 파라미터 추가](./outline/0005-load-outline-include-content.md)

### design — 디자인 스펙 생성 + 5단 계층

- [0001 디자인 스펙 기반 슬라이드 생성 파이프라인](./design/0001-design-spec-pipeline.md)
- [0002 폰트 메트릭 기반 텍스트 오버플로우 방지](./design/0002-font-metric-text-overflow.md)
- [0003 디자인 스펙 병렬 생성 — Worker 스케줄링 + Thinking Budget](./design/0003-parallel-design-spec.md) — _Superseded by offload/0001_
- [0004 슬라이드 타입별 시스템 프롬프트 분리](./design/0004-slide-type-specific-prompts.md)
- [0005 타이틀 슬라이드 긴 제목 텍스트 잘림 수정](./design/0005-title-long-title-overflow-fix.md)
- [0006 텍스트 런 하이퍼링크 지원](./design/0006-text-run-hyperlink.md)
- [0007 이미지 image_path 및 corner_radius_px 지원](./design/0007-image-path-corner-radius.md)
- [0008 Design Spec Post-Generation LLM Review](./design/0008-design-spec-post-generation-review.md)
- [0009 슬라이드 추가 시 기존 디자인 스펙 참조 일관성](./design/0009-add-slide-design-consistency.md) — _Superseded by design/0010_
- [0010 기본 테마 색상 변경 + 다이어그램 활용 강화](./design/0010-theme-color-change.md)
- [0011 5단 디자인 스펙 계층 — Project / Slide / Layout / Section / Content](./design/0011-five-layer-design-spec-hierarchy.md)
- [0012 Content 로컬 그리드 — Section 내부 sub-grid](./design/0012-content-local-grid.md) — _Rejected_
- [0013 5단 계층 데이터 무결성](./design/0013-five-layer-data-integrity.md)
- [0014 PptxShape autofit 기본값 — shrink_text](./design/0014-shape-autofit-shrink-text.md)
- [0015 DESIGN.md — 사람이 편집하는 디자인 의도 단일 소스](./design/0015-design-md-source-of-truth.md)
- [0016 DESIGN.md 가 배경 이미지 자동 주입을 제어한다](./design/0016-design-md-background-policy.md)
- [0017 순환 다이어그램 마킹 + 화살표 방향 규칙](./design/0017-cycle-diagram-marking.md)
- [0018 DESIGN.md 의 taste 레이어를 파이프라인 안에서 생성한다](./design/0018-design-md-taste-in-pipeline.md)
- [0019 배경 이미지 선택을 프로젝트 단위로 결정론화](./design/0019-background-image-deterministic-per-project.md)

### lint — 디자인 스펙 lint

- [0001 디자인 스펙 Validator](./lint/0001-design-spec-validator.md) — _Superseded by lint/0003_
- [0002 Diagram Label-Line Overlap Prevention](./lint/0002-diagram-label-line-overlap-prevention.md)
- [0003 Validator 를 Lint 로 전환](./lint/0003-validator-to-lint.md)
- [0004 화살표·라벨 부착 검증 lint](./lint/0004-arrow-label-attachment-lint.md)
- [0005 5단 계층 Lint 정책 — cross-layer + 단계적 실행](./lint/0005-five-layer-lint-policy.md)
- [0006 순환 다이어그램 위상 일관성 lint — 선언 기반 사이클 마킹](./lint/0006-cycle-diagram-topology-lint.md)

### modify — 슬라이드/component 부분 수정

- [0001 파일 기반 통신, 슬라이드 단위 CRUD 및 파일 분리](./modify/0001-file-based-communication-and-per-slide-crud.md)
- [0002 개별 파일 기반 outline 저장 및 save_outline_slide 도구](./modify/0002-modify-design-spec-inline-outline.md)
- [0003 modify_component MCP 도구 — Section 단위 부분 수정](./modify/0003-modify-component-mcp-tool.md)
- [0004 Imported 슬라이드 design_doc lazy backfill](./modify/0004-imported-slide-lazy-backfill.md)

### slides — HTML 미리보기

- [0001 슬라이드별 HTML 파일 분리 + iframe 컨테이너](./slides/0001-per-slide-html-iframe.md)
- [0002 컨텍스트 안전 HTML 렌더링](./slides/0002-context-safe-html-rendering.md)

### pptx-export — PPTX 내보내기

- [0001 작은 뱃지 도형의 텍스트는 PPTX 에서 줄바꿈하지 않는다](./pptx-export/0001-shape-text-no-wrap-for-compact-badges.md)
- [0002 HTML·PPTX 렌더 패리티 게이트](./pptx-export/0002-html-pptx-render-parity-gate.md)

### import — PPTX 임포트

- [0001 PPTX 임포트 → 디자인 스펙 변환](./import/0001-pptx-import-to-design-spec.md)
- [0002 PPTX 이미지 종횡비 보존 (contain 방식)](./import/0002-pptx-image-aspect-ratio-preservation.md)
- [0003 PPTX 임포트 충실도 개선](./import/0003-pptx-import-fidelity-fixes.md)
- [0004 임포트 직후 소스 인식 Lint 프로필](./import/0004-post-import-lint-profile.md)

### visual-qa — 스크린샷 기반 자동 QA

- [0001 Visual QA Pipeline](./visual-qa/0001-visual-qa-pipeline.md)
- [0002 Visual QA 브라우저 도구 안내 개선](./visual-qa/0002-browser-tool-fallback.md) — _Proposed_
- [0003 Visual QA 2-Phase 모델 분리 (Haiku 분석 + Sonnet 수정)](./visual-qa/0003-two-phase-model-split.md) — _Superseded by offload/0001_

### project — 파이프라인 인프라

- [0001 파이프라인 결과물 저장/로드 + 프로젝트 디렉토리 통합](./project/0001-pipeline-artifact-persistence.md)
- [0002 점진적 구체화 파이프라인 설계](./project/0002-progressive-refinement-pipeline.md)
- [0003 토큰 사용량 추적 및 비용 추정](./project/0003-token-usage-cost-estimation.md) — _Superseded by offload/0001_
- [0004 파이프라인 전체 진행률 보고 및 로깅 강화](./project/0004-progress-reporting-and-logging.md) — _Superseded by offload/0001_
- [0005 MCP Server Stability Improvements](./project/0005-mcp-server-stability.md)

### script — 발표 스크립트 생성 (deprecated)

- [0001 발표 스크립트 생성 (F2)](./script/0001-script-generation.md) — _Deprecated (코드 제거, speaker_notes 는 design_doc 로 흡수)_

### template — PPTX 템플릿 분석 (proposed)

- [0001 PPTX 템플릿 분석 및 동적 디자인 반영 (F8)](./template/0001-template-analysis.md) — _Proposed_

### chart — 차트/데이터 시각화 (proposed)

- [0001 차트 및 데이터 시각화 지원](./chart/0001-chart-data-visualization.md) — _Proposed_

### offload — LLM 생성을 클라이언트로 오프로딩

- [0001 LLM 생성을 클라이언트로 오프로딩 — 플러그인 + 스킬 + prepare/ingest 핸드셰이크](./offload/0001-client-llm-offload-plugin.md)

## 작성 규칙

- ADR 에 **구현 코드 스니펫이나 파일 경로(폴더 이하) 를 포함하지 않는다.** 코드가 변경될 때마다 ADR 을 수정해야 하는 상황을 방지하려고, "왜(why)" 와 "무엇(what)" 수준의 설계 결정만 기록하고 "어떻게(how)" 의 구현 디테일은 코드와 docstring 으로 위임한다.
- 기존 ADR 중 코드 스니펫이나 파일 경로가 포함된 것은 해당 ADR 이 업데이트될 때 점진적으로 제거한다.
- ADR 번호 인용은 카테고리 prefix 와 함께 — `lint/0003`, `modify/0003` 처럼.

## 명명 규칙

- 파일명: `<카테고리>/XXXX-kebab-case-title.md`
- 번호는 카테고리 내에서 순차적으로 증가 (split·삭제 시 결번 허용, renumber 금지)
- 카테고리는 코드 vertical slice 와 정렬

## 새 카테고리 추가 시

1. `docs/adr/<new-category>/` 디렉토리 생성 + 첫 ADR `0001-...md` 작성
2. `docs/adr/.mapping.json` 의 `categories` 에 카테고리 entry와
   `adrs` 레코드(path·status·summary) 추가
3. 본 README 의 카테고리 트리·ADRs 섹션에 한 줄 추가
4. 필요한 선행 카테고리가 확인된 경우에만 `dependsOn` 추가

## 참고

- [Architecture](../harness/architecture.md)
- [ADR GitHub](https://adr.github.io/)
