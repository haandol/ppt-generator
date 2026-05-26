# 8. PPTX 템플릿 분석 및 동적 디자인 반영 (F8)

Date: 2026-02-11

## Status

Proposed

> **Note (2026-02-11)**: AWS 기본 템플릿에 대해서는 정적 추출을 적용했고, 기존 `build_layout_skeleton()` / `LAYOUT_REGIONS` 기반 접근은 ADR-0013(디자인 스펙 파이프라인) 으로 대체되어 제거됐다. 동적 `analyze_template` 도구 구현은 추후 진행 예정.

## Context

현재 시스템은 AWS 전용 PPTX 템플릿에 하드코딩 종속되어 있다 — 레이아웃 인덱스가 AWS 템플릿 기준으로 고정, 폰트(맑은 고딕/Pretendard)·디자인 가이드가 상수로 박혀 있고, DI 컨테이너의 PPTX 템플릿 경로도 고정.

사용자가 자기 회사 PPTX 템플릿을 제공해 자동으로 그 디자인(색상/폰트/레이아웃) 이 HTML 미리보기와 PPTX 내보내기에 반영되어야 기업별 브랜드 가이드라인을 준수하는 프레젠테이션을 생성할 수 있다.

## Decision

새 MCP 도구 `analyze_template(template_path)` 을 추가해 python-pptx 로 PPTX 를 분석하고 *결정론적 규칙 기반* 으로 레이아웃을 자동 매핑한다. 분석 결과는 `TemplateAnalysis` JSON 으로 반환되며, 기존 도구(export_html / generate_pptx) 가 선택적 `template_analysis_json` 파라미터로 받아 동적 적용한다.

### 분석 대상

- **색상 테마** — `theme.xml` 에서 accent1~accent6 / dk1·dk2 / lt1·lt2 추출.
- **폰트 테마** — `theme.xml` 의 majorFont / minorFont 에서 한글(ea) / 라틴(latin) 폰트명 추출.
- **레이아웃 목록** — 모든 slide_layouts 를 순회해 각 레이아웃의 이름과 placeholder 타입/인덱스/크기 매핑.

### 규칙 기반 layout_type 자동 매핑

placeholder 타입과 레이아웃 이름 패턴으로 `title` / `text_image` / `text_only` / `chart` / `closing` / `freeform` 중 하나를 결정. 매핑되지 않는 비표준 레이아웃은 `mapped_type: null` 로 명시 반환 — 호출자가 기존 LAYOUT_MAP 으로 폴백.

### 적용 경로

- **export_html** — 분석 결과를 받아 user prompt 에 *디자인 컨텍스트 블록* (색상 팔레트, 폰트, 사용 지침) 을 동적 추가. system prompt 자체는 변경하지 않음.
- **generate_pptx** — 분석 결과로 사용자 템플릿을 로드하고 동적 LayoutInfo 맵 + FontTheme 추출 폰트 적용. 분석 없으면 기존 AWS 템플릿 + LAYOUT_MAP 폴백 (하위 호환).

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| LLM 기반 매핑 (레이아웃 정보를 LLM 에 전달) | 비결정적 + API 비용 + 지연. 규칙 기반으로 충분히 해결 가능 |
| 사용자 수동 매핑 (인덱스/타입 직접 지정) | 사용자가 PPTX 내부 구조를 알아야 함. UX 저하 |
| **규칙 기반 자동 매핑** | 결정적, 추가 비용 없음, 빠르고 폴백 용이 — **채택** |

## Consequences

### Positive

- 사용자가 기업 브랜드 템플릿을 제공하면 자동 반영.
- 기존 AWS 템플릿 워크플로우는 변경 없이 유지 (하위 호환).
- 비표준 레이아웃은 `mapped_type: null` 로 명시 처리 — 폴백 흐름이 자연스러움.
- LLM 호출 0 — 비용/결정성 모두 좋음.

### Negative / Risks

- `theme.xml` 에 색상/폰트가 정의되지 않은 템플릿은 Office 기본 테마로 폴백.
- python-pptx 의 `oxml` 레이어에 접근하여 테마를 파싱하므로 내부 API 변경에 영향을 받을 수 있음.
- 슬라이드 마스터 이미지/배경 패턴의 HTML 재현 한계.

## Out of Scope

- 슬라이드 마스터 이미지/배경 패턴의 HTML 재현.
- 테마 색상 외 개별 슬라이드의 커스텀 색상 분석.
- 여러 슬라이드 마스터가 있는 템플릿의 마스터별 분석.
- .pptm(매크로 포함) 파일 지원.
- 분석 결과의 사용자 수동 보정 UI.

## References

- [ADR-0013: 디자인 스펙 기반 슬라이드 생성 파이프라인](./0013-design-spec-pipeline.md)
- [ADR-0027: PPTX 임포트 → 디자인 스펙](./0027-pptx-import-to-design-spec.md) — 외부 PPTX 를 spec 으로 변환하는 별도 경로 (본 ADR 은 *디자인 가이드만* 추출하는 보조 경로)
