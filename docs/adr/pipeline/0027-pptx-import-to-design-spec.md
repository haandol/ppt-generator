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

**python-pptx 오브젝트 모델 기반의 결정론적 PPTX → DesignSpec 변환기**를 구현한다. LLM 호출 없이 순수 파싱 로직으로 변환하며, 새 MCP tool `import_pptx`를 통해 노출한다.

#### 변환 방향

현재 PPTX 내보내기(`SlideBuilder`)의 정확한 역변환을 구현한다:

```
PPTX Export:  PptxSlideSpec  ──→  python-pptx objects  ──→  .pptx file
PPTX Import:  .pptx file    ──→  python-pptx objects  ──→  PptxSlideSpec
```

#### 단위 변환 (EMU → px)

기존 내보내기의 역변환:

| 방향 | 변환식 |
|------|--------|
| Export: px → inches | `px * (13.333 / 1280)` (X축), `px * (7.5 / 720)` (Y축) |
| Export: px → EMU | `px * 9525` (패딩) |
| **Import: inches → px** | `inches / (13.333 / 1280)` = `inches * 96` (X축), `inches / (7.5 / 720)` = `inches * 96` (Y축) |
| **Import: EMU → px** | `EMU / 9525` |

#### 슬라이드 크기 정규화

외부 PPTX의 슬라이드 크기가 1280×720px (13.333×7.5 inches)이 아닌 경우, 좌표를 비례 스케일링하여 캔버스에 맞춘다:

```python
scale_x = 1280 / (slide_width_emu / 914400 * 96)  # 96 DPI 기준
scale_y = 720 / (slide_height_emu / 914400 * 96)
```

#### 요소별 추출 전략

##### 1. 배경 (Background)

| PPTX 속성 | DesignSpec 필드 |
|-----------|-----------------|
| `slide.background.fill.fore_color.rgb` (solid fill) | `background_color: "#RRGGBB"` |
| blipFill (이미지 배경) | `images` 리스트에 전체 캔버스 크기 PptxImage로 추가 |
| Gradient fill | 그라디언트의 dominant color를 추출하여 `background_color`로 근사 |

##### 2. 텍스트박스 (TextBox)

python-pptx에서 `shape.shape_type == MSO_SHAPE_TYPE.TEXT_BOX`인 요소:

```python
PptxTextBox(
    left_px    = shape.left / 914400 * 96,   # EMU → px
    top_px     = shape.top / 914400 * 96,
    width_px   = shape.width / 914400 * 96,
    height_px  = shape.height / 914400 * 96,
    paragraphs = [extract_paragraph(p) for p in shape.text_frame.paragraphs],
    line_spacing_pt  = extract_line_spacing(shape.text_frame),
    vertical_alignment = extract_vertical_alignment(shape.text_frame),
    padding_left_px  = shape.text_frame.margin_left / 9525 if margin else None,
    padding_right_px = shape.text_frame.margin_right / 9525 if margin else None,
    padding_top_px   = shape.text_frame.margin_top / 9525 if margin else None,
    padding_bottom_px = shape.text_frame.margin_bottom / 9525 if margin else None,
)
```

##### 3. 도형 (Shape)

`MSO_SHAPE_TYPE.AUTO_SHAPE` 등 non-textbox 도형:

| python-pptx 속성 | PptxShape 필드 |
|-------------------|----------------|
| `auto_shape_type` → shape_type 매핑 (아래 표 참조) | `shape_type` |
| `fill.fore_color.rgb` | `fill_color` |
| `line.color.rgb` | `border_color` |
| `line.width` (Pt) | `border_width_pt` |
| `text_frame.paragraphs` | `paragraphs` (텍스트가 있는 경우) |
| `text_frame.margin_*` | `padding_*_px` |
| `text_frame` bodyPr anchor | `vertical_alignment` |

**지원 shape_type (22종):**

| 카테고리 | shape_type 값 | MSO_SHAPE |
|----------|--------------|-----------|
| Basic | `rectangle`, `rounded_rectangle`, `ellipse` | RECTANGLE, ROUNDED_RECTANGLE, OVAL |
| Arrows | `up_arrow`, `down_arrow`, `left_arrow`, `right_arrow`, `chevron` | UP_ARROW, DOWN_ARROW, LEFT_ARROW, RIGHT_ARROW, CHEVRON |
| Polygons | `triangle`, `diamond`, `pentagon`, `hexagon`, `trapezoid`, `parallelogram`, `cross` | ISOSCELES_TRIANGLE, DIAMOND, PENTAGON, HEXAGON, TRAPEZOID, PARALLELOGRAM, CROSS |
| Stars | `star_4`, `star_5`, `heart` | STAR_4_POINT, STAR_5_POINT, HEART |
| Flowchart | `flowchart_process`, `flowchart_decision`, `flowchart_terminator` | FLOWCHART_PROCESS, FLOWCHART_DECISION, FLOWCHART_TERMINATOR |
| Line | `line` | (Connector) |

매핑되지 않은 도형은 `rectangle`로 폴백된다. HTML 렌더링은 CSS `clip-path: polygon()`으로 구현.

##### 4. 커넥터/선 (Line)

`MSO_SHAPE_TYPE.FREEFORM` 또는 Connector (`p:cxnSp`):

```python
PptxShape(
    shape_type = "line",
    left_px    = min(begin_x, end_x),
    top_px     = min(begin_y, end_y),
    width_px   = abs(end_x - begin_x),
    height_px  = abs(end_y - begin_y),
    border_color  = connector.line.color.rgb,
    border_width_pt = connector.line.width (in Pt),
    end_arrow   = has_tail_end_arrow(connector),
    start_arrow = has_head_end_arrow(connector),
    dash_style  = extract_dash_style(connector),
)
```

화살표 머리 감지는 XML `a:ln/a:tailEnd[@type="triangle"]`, `a:ln/a:headEnd[@type="triangle"]`을 직접 파싱한다.

##### 5. 이미지 (Image)

`MSO_SHAPE_TYPE.PICTURE` 또는 `MSO_SHAPE_TYPE.PLACEHOLDER`(이미지 포함):

```python
PptxImage(
    left_px    = shape.left / 914400 * 96,
    top_px     = shape.top / 914400 * 96,
    width_px   = shape.width / 914400 * 96,
    height_px  = shape.height / 914400 * 96,
    image_bytes = shape.image.blob,
    src         = "",  # 임포트 시 파일 저장 후 설정
)
```

**이미지 파일 경로 보존 (Import → Export 라운드트립):**

`PptxImage`에 `src: str` 필드를 추가하여 이미지 파일의 상대경로를 저장한다. 이는 JSON 직렬화 시 `image_bytes`가 제거되는 문제를 해결한다.

- **임포트 시**: `save_slide_images()`로 PNG 파일 저장 → 반환된 경로를 `dataclasses.replace()`로 각 `PptxImage.src`에 설정 → design spec 재저장
- **직렬화**: `slide_spec_to_json()`이 `image_bytes`를 제거하되 `src`는 보존
- **역직렬화**: `parse_slide_spec()`이 `images` 배열의 `src`, 좌표 등을 파싱
- **내보내기 시**: `load_design_spec_with_images()`가 각 이미지의 `src`로부터 파일을 읽어 `image_bytes`를 복원

```
Import:  PPTX → image_bytes → save PNG → set src → save JSON (src 포함, bytes 제거)
Export:  load JSON (src 포함) → read PNG → restore image_bytes → build PPTX
```

##### 6. 텍스트 런/문단 추출 (OOXML 서식 상속 포함)

플레이스홀더(제목, 본문 등)의 run에 font_size/color/bold가 직접 지정되지 않은 경우, OOXML 상속 체인을 순회하여 resolve한다:

```
font_size 결정: run rPr.sz → para defRPr.sz → layout defRPr.sz → master style defRPr.sz
color 결정:     run rPr solidFill → para defRPr solidFill → layout defRPr solidFill → master style defRPr solidFill
bold 결정:      run rPr.b → para defRPr.b → layout defRPr.b → master style defRPr.b
```

placeholder type → master txStyle 매핑:
- TITLE(1), CENTER_TITLE(3) → `p:titleStyle`
- BODY(2), OBJECT(7), SUBTITLE(4) → `p:bodyStyle`
- 기타 placeholder → `p:otherStyle`
- **비-placeholder (일반 TextBox)** → `p:otherStyle` 폴백 적용. PowerPoint는 placeholder가 아닌 일반 TextBox에서도 색상이 직접 지정되지 않으면 master의 `otherStyle`에서 상속하므로, `placeholder_type`이 `None`인 경우에도 `otherStyle`을 폴백으로 사용한다.

**테마 색상 맵**: `SlideReader` 초기화 시 프레젠테이션 테마(`a:clrScheme`)에서 실제 색상을 추출·캐시하여 `schemeClr` 참조 시 사용한다. tx1→dk1, tx2→dk2, bg1→lt1, bg2→lt2 별칭 매핑을 포함한다. 테마가 없는 경우 Office 기본 팔레트를 폴백으로 사용한다.

**마스터 txStyles 캐시**: `p:txStyles`의 titleStyle/bodyStyle/otherStyle에서 레벨별(lvl1pPr~lvl9pPr) 기본 서식을 미리 추출한다.

**레이아웃 defRPr 캐시**: `read_slide()` 시 해당 슬라이드 레이아웃의 placeholder별 `lstStyle > lvlNpPr > defRPr`을 조회한다.

```python
PptxParagraph(
    runs = [
        PptxTextRun(
            text         = run.text,
            font_size_pt = run.font.size.pt or inherited.font_size_pt,  # 상속 체인
            color        = run_color or inherited.color,                 # 상속 체인
            bold         = run.font.bold if run.font.bold is not None else inherited.bold,
            italic       = bool(run.font.italic),
            font_family  = "monospace" if is_monospace(run.font.name) else None,
        )
        for run in paragraph.runs
    ],
    bullet_level = extract_bullet_level(paragraph),
    alignment    = extract_alignment(paragraph),
)
```

불릿 레벨은 `pPr` XML의 `lvl` 속성과 `buChar`/`buAutoNum` 존재 여부로 판단한다.

##### 7. 발표자 노트

```python
speaker_notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
```

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

- `file_path`: 로컬 PPTX 파일 절대 경로
- 반환값: 새 프로젝트 ID, 슬라이드 수, HTML 미리보기 경로
- 내부 동작:
  1. python-pptx로 PPTX 로드
  2. 슬라이드별 PptxSlideSpec 추출
  3. DesignSpec 구성 → `DesignSpecStore.save_design_spec()` 저장
  4. `design_summary` 추출·저장 (첫 슬라이드 기반 테마 색상)
  5. ProjectMetadata 생성 (`steps_completed: { "import": "completed", "design_spec": "completed" }`)
  6. HTML 미리보기 자동 생성 (`SlidesService.generate_from_design_spec()`)

#### 모듈 구조

```
src/ppt_generator/tools/pptx_import/
├── __init__.py
├── controller.py          # MCP tool 등록 (register_pptx_import_tools)
├── service.py             # ImportService (PPTX → DesignSpec 변환 오케스트레이션)
└── slide_reader.py        # SlideReader (python-pptx 객체 → PptxSlideSpec 변환)
```

- `SlideReader`: `SlideBuilder`의 역변환. Shape/TextBox/Connector/Image 추출 로직
- `ImportService`: SlideReader + DesignSpecStore + SlidesService 조합

#### DI 통합

```python
# di/container.py
@property
def import_service(self) -> ImportService:
    return ImportService(
        project_service=self.project_service,
        slides_service=self.slides_service,
    )
```

#### 지원하지 않는 요소 처리 (Graceful Degradation)

| 미지원 요소 | 처리 방식 |
|-------------|----------|
| 그룹 도형 (GroupShape) | 그룹을 평탄화(flatten)하여 개별 Shape/TextBox로 추출 |
| 표 (Table) | 셀별 텍스트를 포함한 격자형 Shape 배열로 변환 |
| 차트 (Chart) | 이미지로 래스터화하여 PptxImage로 저장 |
| 비디오/오디오 | 무시 (경고 로그) |
| SmartArt | 내부 shape 분해 시도, 실패 시 무시 (경고 로그) |
| 슬라이드 마스터/레이아웃 배경 | 슬라이드에 직접 적용된 것처럼 병합 |
| 애니메이션/전환 효과 | 무시 (정적 스냅샷만 추출) |

#### 폰트 매핑

외부 PPTX의 폰트가 시스템에서 사용하는 `PPTX_FONT_NAME`과 다를 수 있다:

- 임포트 시 원본 폰트명을 `font_family` 필드에 보존
- 내보내기/렌더링 시 시스템 폰트로 자동 대체 (기존 동작)
- 모노스페이스 폰트 감지: `Consolas`, `Courier`, `Monaco` 등 알려진 폰트명 매칭

### 2. 임포트 시 autofit 비활성화

임포트된 PPTX는 원본에서 레이아웃이 확정된 상태이므로, `validate_slide_spec()`의 autofit(텍스트 오버플로우 방지) 로직을 적용하면 텍스트 크기가 원본보다 축소되는 문제가 발생한다.

**원인:** `calculate_required_height()`에서 `line_spacing_pt`가 `None`이면 줄 높이를 `font_size × 2.0`으로 과대 추정 → 필요 높이가 박스 높이를 초과 → 폰트 축소.

**해결:** 임포트 경로에서 `validate_slide_spec(spec, autofit=False)`를 호출하여 폰트 스케일링을 스킵한다. 자세한 내용은 [ADR-0023](./0023-design-spec-validator.md)의 "autofit 비활성화" 섹션 참조.

| 파이프라인 단계 | autofit |
|---|---|
| `import_pptx` → HTML 미리보기 생성 | `False` (`SlidesService.generate_from_design_spec(skip_autofit=True)`) |
| `export_pptx` (임포트된 프로젝트) | `False` (`ExportService.export_from_design_spec(skip_autofit=True)`) |
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
| B. OOXML(ZIP) 직접 파싱 | .pptx를 unzip하여 XML 직접 파싱 | 탈락 — python-pptx가 이미 추상화 제공, XML 직접 파싱은 복잡도 대비 이점 없음 |
| C. LLM 기반 변환 | 슬라이드 스크린샷을 LLM에 전달하여 디자인 스펙 생성 | 탈락 — 비용 높음, 좌표 정확도 낮음, 텍스트 내용 손실 가능 |
| D. LibreOffice headless 활용 | PPTX → 중간 포맷 → 파싱 | 탈락 — 추가 외부 의존성, 변환 과정의 정보 손실 |

### Acceptance Criteria

1. PPTX 파일을 `import_pptx(file_path)`로 로드하면 DesignSpec이 생성되어 프로젝트 디렉토리에 저장된다
2. 임포트된 DesignSpec으로 `export_html`이 정상 동작하여 브라우저에서 미리보기할 수 있다
3. 임포트된 DesignSpec으로 `export_pptx`가 정상 동작하여 원본과 시각적으로 유사한 PPTX가 생성된다
4. 텍스트 내용(text content)이 100% 보존된다
5. 위치/크기 좌표가 ±2px 이내 오차로 변환된다
6. 색상(배경, 텍스트, 도형 fill/border)이 정확히 보존된다
7. 발표자 노트가 보존된다
8. `modify_design_spec`으로 임포트된 슬라이드를 수정할 수 있으며, 기존 images가 보존된다
9. 미지원 요소(차트, 비디오 등) 발견 시 경고 메시지가 반환된다
10. Import → Export 라운드트립 시 이미지가 PPTX에 포함된다 (`PptxImage.src` 기반 복원)
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
- **역변환 일관성**: `SlideBuilder`와 `SlideReader`가 서로의 역변환으로 설계되어 라운드트립 정확도 높음
- **이미지 라운드트립**: `PptxImage.src` 필드로 이미지 파일 경로를 보존하여 Import → Export 시 이미지 누락 방지
- **원본 텍스트 크기 보존**: 임포트 시 autofit 비활성화로 원본 폰트 크기 유지

### Negative

- **DesignSpec 표현 한계**: 그라디언트, 텍스처, 3D 효과 등 `PptxSlideSpec` 스키마에 없는 속성은 손실됨
- **복잡한 레이아웃 손실 가능**: 그룹 도형 평탄화, 표 → 도형 변환 시 편집 편의성 저하
- **외부 PPTX 다양성**: 다양한 PPTX 생성 도구(PowerPoint, Google Slides, Keynote 등)의 비표준 요소 처리에 엣지 케이스 발생 가능
- **이미지 용량**: 차트 래스터화, 배경 이미지 등으로 프로젝트 디렉토리 크기 증가 가능
- **색상 대비 미검증**: validator에서 색상 대비를 보정하지 않으므로, 원본 PPTX에 대비 부족이 있으면 그대로 유지됨 (Visual QA로 확인 가능)

## References

- 도메인 스키마: `src/ppt_generator/interfaces/schemas.py` — `PptxSlideSpec`, `PptxTextBox`, `PptxShape`, `PptxImage`
- PPTX 내보내기 (역방향 참조): `src/ppt_generator/tools/pptx/slide_builder.py` — `SlideBuilder`
- 텍스트 포매터: `src/ppt_generator/tools/pptx/text_formatter.py` — `parse_color`, `format_paragraphs`
- 디자인 스펙 저장소: `src/ppt_generator/tools/project/design_spec_store.py` — `DesignSpecStore`
- Spec 유틸리티: `src/ppt_generator/interfaces/spec_utils/` — parser, serializer, validator
- 대비 유틸리티: `src/ppt_generator/interfaces/spec_utils/contrast_utils.py`
- 배경 이미지 유틸리티: `src/ppt_generator/interfaces/bg_image_utils.py`
- 상수: `src/ppt_generator/interfaces/constants.py` — `PX_TO_EMU`, `EXPORT_PX_TO_INCHES_*`
- 슬라이드 서비스: `src/ppt_generator/tools/slides/service.py` — `generate_from_design_spec()`
- 테스트: `tests/test_pptx_import.py`, `tests/test_contrast_utils.py`, `tests/test_spec_utils_validation.py`
- 관련 ADR: [0013-design-spec-pipeline](./0013-design-spec-pipeline.md), [0014-file-based-communication-and-per-slide-crud](./0014-file-based-communication-and-per-slide-crud.md), [0023-design-spec-validator](./0023-design-spec-validator.md), [0026-visual-qa-pipeline](./0026-visual-qa-pipeline.md)
