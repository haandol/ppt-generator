# ADR-0027: PPTX 임포트 → 디자인 스펙 변환

Date: 2026-03-04

## Status

Accepted

## Context

기존 파이프라인은 *생성 전용* 단방향 흐름(Outline → Script → Design Spec → HTML / PPTX) 만 지원했다. 사용자가 보유한 외부 PPTX 를 시스템에 가져와 수정하거나, HTML 미리보기로 확인하거나, 디자인 스펙 기반 도구(`modify_design_spec`, `visual_qa`) 를 활용하려면 **PPTX → DesignSpec 역변환** 경로가 필요하다.

핵심 요구사항:

1. **디자인 요소 최대 보존** — 위치, 크기, 색상, 폰트, 정렬, 패딩, 불릿, 도형 스타일 등 시각적 속성을 최대한 유지.
2. **전체 슬라이드 임포트** — 일부가 아닌 전체 프레젠테이션을 한 번에 변환.
3. **기존 파이프라인 통합** — 임포트 결과가 DesignSpec 으로 저장되어 기존 도구들과 즉시 호환.

## Decision

**python-pptx 오브젝트 모델 기반의 결정론적 변환기** 를 구현한다. LLM 호출 없이 순수 파싱 로직으로 변환하며, 새 MCP 도구 `import_pptx` 를 통해 노출한다. 변환은 기존 PPTX 내보내기(SlideBuilder) 의 정확한 역변환으로 설계해 라운드트립(Import → 수정 → Export) 정확도를 높인다.

### 슬라이드 크기 정규화

외부 PPTX 의 슬라이드 크기가 1280×720px 이 아닌 경우 좌표를 비례 스케일링해 캔버스에 맞춘다.

### 요소별 보존 전략

**배경(Background)** — solid fill 은 hex 색상으로, blipFill(이미지 배경) 은 슬라이드 단위 이미지 필드로 보존한다. blipFill 을 도형/이미지 배열로 평탄화하지 않는 이유: OOXML 의미상 배경은 슬라이드 속성이지 도형이 아니다. 도형 배열에 섞으면 z-index/레이아웃에 의도치 않은 영향을 준다. 탐색 우선순위는 slide → slide_layout → slide_master 로, 최초 발견한 blipFill 의 이미지 파트를 사용한다. background_color 와 공존 가능하며 렌더 시 *이미지가 우선*, 색상은 이미지 로드 실패 시 폴백.

**텍스트박스 / 도형 / 선** — 위치/크기는 EMU↔px 단위 변환으로 추출. 도형은 22 종 shape_type 매핑(Basic / Arrows / Polygons / Stars / Flowchart / Line) 후 미매핑은 `rectangle` 폴백. 커스텀 freeform(custGeom) 은 OOXML path 명령을 SVG path data 로 변환해 보존하고, 렌더 시 HTML 은 `<svg><path>`, PPTX export 는 역변환해 custGeom 으로 복원.

**텍스트 서식 상속** — placeholder 의 run 에 font_size/color/bold 가 직접 지정되지 않은 경우 OOXML 상속 체인(run rPr → para defRPr → layout defRPr → master style defRPr) 을 순회해 resolve. 마스터의 txStyle 은 placeholder type 에 따라 titleStyle / bodyStyle / otherStyle 분기. 테마 색상(`a:clrScheme`) 은 별도 캐시로 추출. 마스터/레이아웃 스타일도 미리 캐시해 상속 조회 비용 절감.

**이미지 라운드트립** — 이미지 데이터를 파일로 저장하고 상대경로(`src`) 를 spec 에 기록. JSON 직렬화 시 바이너리 제거되지만 export 시 src 경로에서 바이너리 복원해 PPTX 에 포함.

**slide_type 추론** — 외부 PPTX 에는 slide_type 이 없으므로 휴리스틱: 첫 슬라이드 + 텍스트 ≤3 + 대형 폰트(≥32pt) → title, 마지막 슬라이드 + "감사"/"Thank"/"Q&A" 키워드 → closing, 그 외 → content.

**color_theme 자동 판별** — design_summary 의 background_color 휘도 분석으로 dark/light 결정. 후속 modify/export 호출이 동일 테마를 사용.

### 미지원 요소 graceful degradation

| 미지원 요소 | 처리 |
|---|---|
| 그룹 도형(GroupShape) | 평탄화 — 그룹 좌표계를 슬라이드 절대 좌표로 변환 |
| 표(Table) | 셀별 텍스트 격자형 Shape 배열로 변환 |
| 차트(Chart) | 이미지로 래스터화 |
| 비디오/오디오 | 무시 (경고 로그) |
| SmartArt | 내부 shape 분해 시도, 실패 시 무시 |
| 마스터/레이아웃 배경 | 슬라이드에 직접 적용된 것처럼 병합 |
| 애니메이션/전환 효과 | 무시 (정적 스냅샷만) |

### 임포트 시 autofit 비활성화

임포트된 PPTX 는 원본에서 레이아웃이 확정된 상태이므로 텍스트 측정 기반 autofit 을 적용하면 폰트가 원본보다 축소된다(특히 line_spacing_pt=None 이면 줄 높이 과대 추정). 임포트 경로에선 autofit 을 비활성화해 원본 텍스트 크기를 보존한다. 임포트 프로젝트 판별은 ProjectMetadata.steps_completed 에 `"import"` 키 존재 여부.

### 색상 대비·정렬은 LLM 영역으로 분리

색상 대비 부족, 폰트 사이즈 불일치, 정렬 불일치 같은 *컨텍스트 의존적* 결함은 임포트 변환기가 보정하지 않는다 — Visual QA(LLM) 가 사용자 요청 시 처리. 변환기는 *시각 속성을 그대로 옮기는* 책임만 진다.

## 대안 검토

| 대안 | 채택하지 않은 이유 |
|---|---|
| OOXML(ZIP) 직접 파싱 | python-pptx 가 이미 안정적 추상화 제공 — 직접 XML 파싱은 유지보수 부담 |
| LLM 기반 변환 (스크린샷 → 디자인 스펙) | 비용 높음, 좌표 정확도 낮음, 텍스트 내용 손실 가능 |
| LibreOffice headless 중간 포맷 | 추가 외부 의존성 + 변환 정보 손실 |

## 하위 호환성

- 기존 generated 슬라이드는 영향 없음 (변환기는 새 경로).
- 임포트된 슬라이드는 grid_plan/design_doc=None 으로 들어옴 — 5단 계층 가치(부분 수정 식별성) 는 ADR-0051 의 lazy backfill 로 후속 활용.

## Consequences

### Positive

- 양방향 파이프라인 — 기존 PPTX 를 시스템에 가져와 수정/재내보내기 가능.
- 기존 도구 재활용 — modify_design_spec / visual_qa / export_html / export_pptx 즉시 호환.
- 변환에 LLM 호출 0 — 비용·결정성 모두 좋음.
- Export 와 Import 가 서로의 역변환으로 설계되어 라운드트립 정확도 높음.
- 이미지 src 보존으로 라운드트립 시 누락 없음.
- 임포트 시 autofit 비활성화로 원본 텍스트 크기 보존.

### Negative / Risks

- DesignSpec 스키마에 없는 속성(그라디언트, 텍스처, 3D, 애니메이션 등) 은 손실.
- 그룹 도형 평탄화/표→도형 변환은 편집 편의성을 일부 떨어뜨림.
- PowerPoint/Google Slides/Keynote 등 다양한 생성 도구의 비표준 요소에서 엣지 케이스 발생 가능.
- 차트 래스터화·배경 이미지로 프로젝트 디스크 사용량 증가 가능.

## Out of Scope

- PPT(레거시 .ppt 포맷) — python-pptx 는 .pptx 만 지원.
- PPTX 매크로(VBA) 보존.
- 슬라이드 마스터/레이아웃 테마 자체의 임포트 (적용 결과만 추출).
- 애니메이션/전환 효과 보존.
- ODP(LibreOffice) 포맷.
- 원본 PPTX 와의 pixel-perfect 일치 보장 (DesignSpec 스키마 표현 한계 내에서 최대한 유사).

## References

- [ADR-0013: 디자인 스펙 기반 슬라이드 생성 파이프라인](./0013-design-spec-pipeline.md)
- [ADR-0014: 파일 기반 통신 + 슬라이드별 CRUD](./0014-file-based-communication-and-per-slide-crud.md)
- [ADR-0026: Visual QA 파이프라인](./0026-visual-qa-pipeline.md)
- [ADR-0041: Validator 를 Lint 로 전환](./0041-validator-to-lint.md)
- [ADR-0051: Imported 슬라이드 design_doc lazy backfill](./0051-imported-slide-lazy-design-doc-backfill.md)
