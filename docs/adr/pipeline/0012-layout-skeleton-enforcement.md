# 12. 레이아웃 골격(Skeleton) 기반 위치 강제

Date: 2026-02-11

## Status

Accepted

## Context

F3(HTML 슬라이드 생성)에서 LLM이 TailwindCSS로 자유롭게 슬라이드를 배치하면, `LAYOUT_REGIONS`에 정의된 제목/본문/이미지의 정확한 좌표를 따르지 않는 문제가 있었다. 프롬프트에 px 좌표를 가이드라인으로 제시해도, LLM이 flex/grid 레이아웃으로 "자연스럽게" 구현하면서 실제 위치가 AWS PPTX 템플릿의 placeholder 좌표와 크게 벗어났다.

이로 인해 발생하는 문제:
- **PPTX 변환 부정확**: HTML에서 인라인 style 없이 Tailwind 클래스만 사용하면, PPTX 변환 시 정확한 좌표를 추출할 수 없음
- **슬라이드 간 레이아웃 불일치**: 동일 layout_type이라도 LLM이 매번 다른 위치에 요소를 배치
- **템플릿 좌표와의 괴리**: AWS PPTX 템플릿에서 추출한 정밀한 좌표가 활용되지 않음

## Decision

`LAYOUT_REGIONS` 좌표를 사용하여 `position:absolute` div 골격(skeleton)을 **코드로** 생성하고, LLM은 각 영역 **내부** 컨텐츠만 채우도록 한다. 후처리에서 좌표를 검증/복원하여 이중 안전장치를 구성한다.

### Technical Details

#### 1. 골격 생성 — `build_layout_skeleton()`

`constants.py`에 순수 함수로 구현. `LAYOUT_REGIONS` 딕셔너리에서 좌표를 읽어 `<section>` 골격 HTML을 생성한다.

```python
def build_layout_skeleton(
    layout_type: str,
    slide_index: int,
    speaker_notes: str = "",
    image_placeholder: str | None = None,
) -> str:
```

생성되는 HTML 구조:
```html
<section id="slide-0" data-speaker-notes="...">
  <div data-wrapper="true" class="absolute inset-0">
    <div data-region="title" style="position:absolute; left:57px; top:96px; width:1152px; height:56px; overflow:hidden;">
      <!-- CONTENT:title -->
    </div>
    <div data-region="body" style="position:absolute; left:64px; top:180px; width:1152px; height:472px; overflow:hidden;">
      <!-- CONTENT:body -->
    </div>
  </div>
</section>
```

주요 속성:
- `data-wrapper="true"`: 래퍼 div 마커. 배경색 적용 대상 (Tailwind 클래스 + 인라인 `background-color` 병기)
- `data-region="xxx"`: 영역 마커. PPTX 변환 시 좌표 추출에 사용
- `style="position:absolute; ..."`: LAYOUT_REGIONS 좌표로 고정
- image region에 `image_placeholder`가 있으면 `<img>` 태그 미리 삽입

#### 2. LLM 프롬프트 — `SLIDES_REGION_SYSTEM_PROMPT`

기존 `SLIDES_SYSTEM_PROMPT`(전체 section 자유 생성)를 대체하는 새 시스템 프롬프트:
- 골격의 `<!-- CONTENT:xxx -->` 마커를 실제 HTML로 교체하도록 지시
- `data-region` div의 style 속성은 **절대 변경 금지**
- `data-wrapper` div에 배경색 Tailwind 클래스 + 인라인 `style="background-color:#hex"` 병기
- 영역 내부에서는 TailwindCSS 유틸리티로 자유 디자인

#### 3. 좌표 검증 — `_validate_region_styles()`

LLM이 region div의 좌표를 변경했을 경우 `LAYOUT_REGIONS`에서 원래 값을 복원하는 안전장치:
- BeautifulSoup으로 파싱
- `data-region` div를 찾아 LAYOUT_REGIONS 좌표로 style 속성 강제 복원
- 콘텐츠와 Tailwind 클래스는 보존

#### 4. PPTX 변환 — `_extract_region_elements()`

`data-wrapper` div가 있으면 region 기반 로직으로 처리:
- `data-region` div의 `position:absolute` style에서 좌표 추출
- 좌표를 px → inches → EMU 변환하여 PPTX 요소 배치
- `data-wrapper` div에서 `background-color` 추출하여 슬라이드 배경 설정
- 레거시 HTML (data-wrapper 없음)은 기존 인라인 style 기반 로직으로 폴백

#### 5. 수정 시 좌표 보존

`_modify_single_slide()` 수정 후에도 `_validate_region_styles()`로 좌표 보존:
- `_detect_layout_type_from_html()`로 region 이름 집합에서 layout_type 자동 감지
- 수정 프롬프트에도 "data-region div의 style 변경 금지" 규칙 포함

### Alternatives Considered

- **프롬프트만으로 좌표 가이드 (기존 방식)**: px 좌표를 프롬프트에 명시하되 flex/grid로 구현하도록 지시. LLM이 좌표를 정확히 따르지 않아 탈락
- **후처리 좌표 주입만**: LLM이 자유 생성 후 좌표를 강제 주입. LLM이 영역 구조를 모르므로 콘텐츠가 영역에 맞지 않을 수 있음
- **골격 + 후처리 검증 (채택)**: 골격으로 구조 강제 + 후처리로 이중 안전. LLM이 영역 크기를 인지하고 콘텐츠 양을 조절할 수 있으며, 좌표 변경 시에도 복원 보장

## Consequences

**긍정적:**
- 모든 layout_type에서 제목/본문/이미지의 위치가 LAYOUT_REGIONS 좌표로 구조적으로 보장됨
- PPTX 변환 시 정확한 좌표로 요소가 배치되어 HTML↔PPTX 간 레이아웃 일치도 향상
- LLM은 영역 크기를 인지하므로 콘텐츠 양을 적절히 조절 가능
- 슬라이드 간 레이아웃 일관성 보장
- 레거시 HTML과의 하위 호환 유지 (data-wrapper 없으면 기존 로직)

**부정적:**
- LLM의 레이아웃 자유도가 영역 내부로 제한됨 (의도된 제약)
- 골격 HTML이 프롬프트에 포함되므로 입력 토큰이 약간 증가
- 새로운 layout_type 추가 시 `LAYOUT_REGIONS`와 `build_layout_skeleton()` 업데이트 필요

## References

- 골격 생성: `src/ppt_generator/interfaces/constants.py` — `build_layout_skeleton()`, `LAYOUT_REGIONS`
- 프롬프트: `src/ppt_generator/interfaces/constants.py` — `SLIDES_REGION_SYSTEM_PROMPT`, `SLIDES_REGION_USER_PROMPT_TEMPLATE`
- 좌표 검증: `src/ppt_generator/tools/slides/service.py` — `_validate_region_styles()`, `_detect_layout_type_from_html()`
- PPTX 변환: `src/ppt_generator/tools/pptx/service.py` — `_extract_region_elements()`, `_add_textbox_at()`
- 테스트: `tests/test_slides_service.py` — `TestBuildLayoutSkeleton`, `TestValidateRegionStyles`, `TestDetectLayoutType`
- 테스트: `tests/test_pptx_service.py` — `TestRegionBasedExport`
- 관련 ADR: [0004-html-slide-generation](./0004-html-slide-generation.md), [0006-pptx-export](./0006-pptx-export.md), [0005-slide-modification](./0005-slide-modification.md)
- ALPS: Section 7.3, Section 7.5
