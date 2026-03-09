# ADR-0027: PPTX 임포트 → 디자인 스펙 변환

Date: 2026-03-04

## Status

Accepted

## Context

현재 파이프라인은 "생성 전용" 단방향 흐름만 지원한다:

```
Outline → Script → Design Spec → HTML / PPTX
```

사용자가 기존에 보유한 PPTX 파일을 시스템에 가져와서 수정하거나, HTML 미리보기로 확인하거나, 디자인 스펙 기반 도구(`modify_design_spec`, `visual_qa`)를 활용하려면 **PPTX → DesignSpec 역변환** 경로가 필요하다.

핵심 요구사항:

1. **디자인 요소 최대 보존**: 위치, 크기, 색상, 폰트, 정렬, 패딩, 불릿, 도형 스타일 등 시각적 속성을 최대한 유지
2. **전체 슬라이드 임포트**: 일부가 아닌 전체 프레젠테이션을 한 번에 변환
3. **기존 파이프라인 통합**: 임포트 결과가 DesignSpec으로 저장되어 기존 도구(`export_html`, `export_pptx`, `modify_design_spec`, `visual_qa`)와 즉시 호환

색상 대비와 요소 간 간격은 validator가 아닌 디자인 서머리의 테마/색상 팔레트와 프롬프트를 통해 LLM이 올바르게 출력하도록 가이드한다.

## Decision

### 1. PPTX → DesignSpec 변환기

**python-pptx 오브젝트 모델 기반의 결정론적 변환기**를 구현한다. LLM 호출 없이 순수 파싱 로직으로 변환하며, 새 MCP tool `import_pptx`를 통해 노출한다.

#### 변환 방향

기존 PPTX 내보내기(SlideBuilder)의 정확한 역변환을 구현한다:

```
PPTX Export:  PptxSlideSpec  ──→  python-pptx objects  ──→  .pptx file
PPTX Import:  .pptx file    ──→  python-pptx objects  ──→  PptxSlideSpec
```

#### 단위 변환 (EMU → px)

| 방향 | 변환식 |
|------|--------|
| Export: px → inches | `px * (13.333 / 1280)` (X축), `px * (7.5 / 720)` (Y축) |
| Export: px → EMU | `px * 9525` (패딩) |
| **Import: inches → px** | `inches * 96` |
| **Import: EMU → px** | `EMU / 9525` |

#### 슬라이드 크기 정규화

외부 PPTX의 슬라이드 크기가 1280×720px이 아닌 경우, 좌표를 비례 스케일링하여 캔버스에 맞춘다.

#### 요소별 추출 전략

##### 1. 배경 (Background)

| PPTX 속성 | DesignSpec 필드 |
|-----------|-----------------|
| Solid fill | `background_color: "#RRGGBB"` |
| blipFill (이미지 배경) | 전체 캔버스 크기 이미지 요소로 추가 |
| Gradient fill | Dominant color를 추출하여 단색 근사 |

##### 2. 텍스트박스 (TextBox)

위치/크기(EMU → px 변환), 문단/런 목록, line_spacing, vertical_alignment, 패딩(EMU → px 변환)을 추출한다.

##### 3. 도형 (Shape)

Non-textbox 도형에서 shape_type, fill/border 색상, 선 두께, 텍스트, 패딩, 정렬 등을 추출한다.

**지원 shape_type (22종):**

| 카테고리 | shape_type 값 |
|----------|--------------|
| Basic | `rectangle`, `rounded_rectangle`, `ellipse` |
| Arrows | `up_arrow`, `down_arrow`, `left_arrow`, `right_arrow`, `chevron` |
| Polygons | `triangle`, `diamond`, `pentagon`, `hexagon`, `trapezoid`, `parallelogram`, `cross` |
| Stars | `star_4`, `star_5`, `heart` |
| Flowchart | `flowchart_process`, `flowchart_decision`, `flowchart_terminator` |
| Line | `line` |

매핑되지 않은 도형은 `rectangle`로 폴백된다.

##### 3-1. 커스텀 Freeform 도형 (Custom SVG Path)

`FREEFORM` + `custGeom`(Custom Geometry) 도형은 OOXML path 명령을 SVG path data로 변환하여 보존한다.

**svg_path 형식**: `"{viewBox_width} {viewBox_height} {SVG_path_data}"` — viewBox 크기와 SVG path `d` 속성을 공백으로 구분.

**변환 매핑 (OOXML → SVG)**:

| OOXML 명령 | SVG 명령 |
|-----------|----------|
| `a:moveTo` | `M x y` |
| `a:lnTo` | `L x y` |
| `a:cubicBezTo` (3점) | `C x1 y1 x2 y2 x3 y3` |
| `a:close` | `Z` |

**렌더링**: HTML에서는 `<svg>` + `<path>`, PPTX export에서는 SVG path를 역변환하여 `custGeom`으로 복원.

##### 4. 커넥터/선 (Line)

시작점/끝점에서 위치/크기를 계산하고, 선 색상/두께/화살표 유무/대시 스타일을 추출한다. 화살표 감지는 OOXML `a:ln`의 `tailEnd`/`headEnd` 속성을 파싱한다.

##### 5. 이미지 (Image)

위치/크기와 이미지 바이너리를 추출한다.

**이미지 파일 경로 보존 (Import → Export 라운드트립):**

이미지 데이터를 파일로 저장하고 상대경로(`src`)를 JSON에 보존한다. JSON 직렬화 시 바이너리는 제거되지만, export 시 `src` 경로에서 바이너리를 복원하여 PPTX에 포함한다.

```
Import:  PPTX → image_bytes → save file → set src → save JSON (src 포함, bytes 제거)
Export:  load JSON (src 포함) → read file → restore image_bytes → build PPTX
```

##### 6. 텍스트 런/문단 추출 (OOXML 서식 상속 포함)

플레이스홀더(제목, 본문 등)의 run에 font_size/color/bold가 직접 지정되지 않은 경우, OOXML 상속 체인을 순회하여 resolve한다:

```
font_size: run rPr → para defRPr → layout defRPr → master style defRPr
color:     run rPr solidFill → para defRPr → layout defRPr → master style defRPr
bold:      run rPr.b → para defRPr.b → layout defRPr.b → master style defRPr.b
```

placeholder type → master txStyle 매핑:
- TITLE, CENTER_TITLE → `titleStyle`
- BODY, OBJECT, SUBTITLE → `bodyStyle`
- 기타 placeholder 및 비-placeholder → `otherStyle` (PowerPoint는 placeholder가 아닌 일반 TextBox에서도 master의 `otherStyle`에서 상속)

**테마 색상 맵**: 프레젠테이션 테마(`a:clrScheme`)에서 실제 색상을 추출·캐시. tx1→dk1, tx2→dk2, bg1→lt1, bg2→lt2 별칭 매핑 포함. 테마가 없는 경우 Office 기본 팔레트를 폴백으로 사용.

**마스터/레이아웃 스타일 캐시**: 슬라이드 레이아웃 및 마스터의 레벨별 기본 서식을 미리 추출하여 상속 조회에 사용.

불릿 레벨은 `pPr` XML의 `lvl` 속성과 `buChar`/`buAutoNum` 존재 여부로 판단한다.

##### 7. 발표자 노트

노트 슬라이드가 존재하면 텍스트를 추출하여 `speaker_notes`로 저장.

##### 8. slide_type 추론

외부 PPTX에는 `slide_type` 필드가 없으므로 휴리스틱으로 추론:

| 조건 | slide_type |
|------|------------|
| 첫 번째 슬라이드 + 텍스트 요소 ≤ 3개 + 대형 폰트(≥ 32pt) | `"title"` |
| 마지막 슬라이드 + "감사", "Thank", "Q&A" 등 키워드 포함 | `"closing"` |
| 그 외 | `"content"` |

#### 새 MCP Tool

```
import_pptx(file_path: str) -> { project_id, num_slides, slides_html_path }
```

내부 동작:
1. python-pptx로 PPTX 로드
2. 슬라이드별 PptxSlideSpec 추출
3. DesignSpec 구성 및 저장
4. 디자인 요약 추출·저장 (첫 슬라이드 기반 테마 색상)
5. ProjectMetadata 생성 (`steps_completed`에 `"import"` 포함)
6. HTML 미리보기 자동 생성

#### 지원하지 않는 요소 처리 (Graceful Degradation)

| 미지원 요소 | 처리 방식 |
|-------------|----------|
| 그룹 도형 (GroupShape) | 평탄화(flatten)하여 개별 요소로 추출. 그룹 좌표계에서 슬라이드 절대 좌표로 변환 |
| 표 (Table) | 셀별 텍스트를 포함한 격자형 Shape 배열로 변환 |
| 차트 (Chart) | 이미지로 래스터화 |
| 비디오/오디오 | 무시 (경고 로그) |
| SmartArt | 내부 shape 분해 시도, 실패 시 무시 (경고 로그) |
| 슬라이드 마스터/레이아웃 배경 | 슬라이드에 직접 적용된 것처럼 병합 |
| 애니메이션/전환 효과 | 무시 (정적 스냅샷만 추출) |

#### 폰트 매핑

- 임포트 시 원본 폰트명을 `font_family` 필드에 보존
- 내보내기/렌더링 시 시스템 폰트로 자동 대체
- 모노스페이스 폰트 감지: `Consolas`, `Courier`, `Monaco` 등 알려진 폰트명 매칭

### 2. 임포트 시 autofit 비활성화

임포트된 PPTX는 원본에서 레이아웃이 확정된 상태이므로, validator의 autofit(텍스트 오버플로우 방지) 로직을 적용하면 텍스트 크기가 원본보다 축소되는 문제가 발생한다.

**원인:** `line_spacing_pt`가 `None`이면 줄 높이를 `font_size × 2.0`으로 과대 추정 → 필요 높이가 박스 높이를 초과 → 폰트 축소.

**해결:** 임포트 경로에서 autofit을 비활성화하여 폰트 스케일링을 스킵한다.

| 파이프라인 단계 | autofit |
|---|---|
| `import_pptx` → HTML 미리보기 생성 | `False` |
| `export_pptx` (임포트된 프로젝트) | `False` |
| `export_pptx` (LLM 생성 프로젝트) | `True` (기본값) |

임포트된 프로젝트 판별은 `ProjectMetadata.steps_completed`에 `"import"` 키가 있는지로 수행한다.

#### 보정 대상이 아닌 항목

- **Inconsistent Font Size** — 컨텍스트 의존적, LLM(Visual QA)에 위임
- **Misalignment** — 정렬 기준점 판단 복잡, LLM에 위임
- **Inconsistent Spacing** — 간격 불일치 판단 컨텍스트 의존적, LLM에 위임

### Alternatives Considered

| 대안 | 설명 | 판단 |
|------|------|------|
| A. python-pptx 오브젝트 모델 직접 파싱 | 라이브러리 API로 shape/textbox/paragraph 순회 | **채택** — 안정적이고 유지보수 용이 |
| B. OOXML(ZIP) 직접 파싱 | .pptx를 unzip하여 XML 직접 파싱 | 탈락 — python-pptx가 이미 추상화 제공 |
| C. LLM 기반 변환 | 슬라이드 스크린샷을 LLM에 전달하여 디자인 스펙 생성 | 탈락 — 비용 높음, 좌표 정확도 낮음, 텍스트 내용 손실 가능 |
| D. LibreOffice headless 활용 | PPTX → 중간 포맷 → 파싱 | 탈락 — 추가 외부 의존성, 변환 과정의 정보 손실 |

### Acceptance Criteria

1. PPTX 파일을 `import_pptx`로 로드하면 DesignSpec이 생성되어 프로젝트에 저장된다
2. 임포트된 DesignSpec으로 `export_html`이 정상 동작하여 브라우저에서 미리보기할 수 있다
3. 임포트된 DesignSpec으로 `export_pptx`가 정상 동작하여 원본과 시각적으로 유사한 PPTX가 생성된다
4. 텍스트 내용(text content)이 100% 보존된다
5. 위치/크기 좌표가 ±2px 이내 오차로 변환된다
6. 색상(배경, 텍스트, 도형 fill/border)이 정확히 보존된다
7. 발표자 노트가 보존된다
8. `modify_design_spec`으로 임포트된 슬라이드를 수정할 수 있으며, 기존 images가 보존된다
9. 미지원 요소(차트, 비디오 등) 발견 시 경고 메시지가 반환된다
10. Import → Export 라운드트립 시 이미지가 PPTX에 포함된다
11. 임포트된 PPTX의 원본 텍스트 크기가 보존된다 (autofit 비활성화)

### Out of Scope

- PPT (레거시 .ppt 포맷) 지원 — python-pptx는 .pptx만 지원
- PPTX 내 매크로(VBA) 보존
- 슬라이드 마스터/레이아웃 테마 자체의 임포트 (적용 결과만 추출)
- 애니메이션/전환 효과 보존
- ODP(LibreOffice) 포맷 지원
- 임포트 후 원본 PPTX와의 pixel-perfect 일치 보장 (최대한 유사하게 변환하되, DesignSpec 스키마의 표현 한계 내에서)

## Consequences

### Positive

- **양방향 파이프라인**: 기존 PPTX를 시스템에 가져와 수정·내보내기가 가능해짐
- **기존 도구 재활용**: `modify_design_spec`, `visual_qa`, `export_html`, `export_pptx` 모두 즉시 사용 가능
- **LLM 비용 없음**: 순수 파싱 기반이므로 추가 LLM 호출 비용이 없음
- **결정론적 변환**: 같은 입력에 항상 같은 결과 — 테스트 용이
- **역변환 일관성**: Export와 Import가 서로의 역변환으로 설계되어 라운드트립 정확도 높음
- **이미지 라운드트립**: 이미지 파일 경로를 보존하여 Import → Export 시 이미지 누락 방지
- **원본 텍스트 크기 보존**: 임포트 시 autofit 비활성화로 원본 폰트 크기 유지

### Negative

- **DesignSpec 표현 한계**: 그라디언트, 텍스처, 3D 효과 등 스키마에 없는 속성은 손실됨
- **복잡한 레이아웃 손실 가능**: 그룹 도형 평탄화, 표 → 도형 변환 시 편집 편의성 저하
- **외부 PPTX 다양성**: 다양한 PPTX 생성 도구(PowerPoint, Google Slides, Keynote 등)의 비표준 요소 처리에 엣지 케이스 발생 가능
- **이미지 용량**: 차트 래스터화, 배경 이미지 등으로 프로젝트 크기 증가 가능
- **색상 대비 미검증**: validator에서 색상 대비를 보정하지 않으므로, 원본에 대비 부족이 있으면 그대로 유지됨 (Visual QA로 확인 가능)

## References

- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0014-file-based-communication-and-per-slide-crud](./0014-file-based-communication-and-per-slide-crud.md), [0023-design-spec-validator](./0023-design-spec-validator.md), [0026-visual-qa-pipeline](./0026-visual-qa-pipeline.md)
