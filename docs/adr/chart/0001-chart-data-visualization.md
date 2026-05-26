# 차트 및 데이터 시각화 지원

Date: 2026-04-02

## Status

Proposed

## Context

현재 디자인 스펙 파이프라인은 `textboxes`, `shapes`, `images` 세 가지 요소 타입만 지원한다. LLM이 차트를 표현하려면 도형을 조합하여 수동으로 시각화를 구성해야 하는데, 이 방식에는 근본적인 한계가 있다:

1. **정확도 부족**: LLM이 데이터 값을 정확한 비율로 도형 좌표에 매핑하기 매우 어렵다. 막대 높이, 파이 각도 등의 수치적 정확성이 보장되지 않는다.
2. **PPTX 편집 불가**: 도형으로 조합된 "차트"는 PowerPoint에서 데이터를 수정하거나 차트 스타일을 변경할 수 없다.
3. **복잡도 폭발**: 축, 범례, 데이터 레이블 등을 모두 개별 도형으로 표현하면 요소 수가 급증하고 토큰 소비가 비효율적이다.
4. **임포트 손실**: PPTX 임포트 시 차트 요소는 경고만 출력하고 완전히 무시된다.

python-pptx는 네이티브 Chart API를 제공하여 편집 가능한 차트를 OOXML으로 직접 생성할 수 있다.

## Decision

`PptxSlideSpec`에 네 번째 요소 타입 `charts`를 추가하고, 데이터 기반 결정적 렌더링을 구현한다. LLM은 차트 유형과 데이터만 생성하고, 실제 렌더링은 코드에서 결정적으로 수행한다.

### Technical Details

#### 설계 원칙

- **LLM의 역할 최소화**: LLM은 차트 유형, 카테고리, 시리즈 데이터, 위치/크기만 결정. 좌표 계산과 시각적 렌더링은 코드가 결정적으로 처리.
- **Single Source of Truth 유지**: 기존 디자인 스펙 → {HTML, PPTX} 결정적 변환 아키텍처(ADR-0001 (design))를 그대로 따른다.
- **z_index 통합**: 기존 요소 타입과 동일하게 z_index 기반 렌더링 순서에 참여한다.
- **하위 호환**: `charts` 필드의 기본값은 빈 리스트이므로 기존 디자인 스펙에 영향 없음.

#### 차트 데이터 모델

`PptxChart` frozen dataclass를 신규 정의한다. 구성 요소:

- **위치/크기**: `left_px`, `top_px`, `width_px`, `height_px` (기존 요소와 동일한 좌표계)
- **차트 유형**: `chart_type` 문자열 (아래 지원 목록 참조)
- **데이터**: 카테고리 리스트 + 시리즈 리스트 (시리즈 = 이름 + 값 배열)
- **스타일링**: 색상 팔레트, 범례 표시 여부, 데이터 레이블 표시 여부
- **축 설정**: 축 라벨, 최대/최솟값 (원형/도넛에는 해당 없음)
- **렌더링 순서**: `z_index` (기존 요소와 동일)

**지원 차트 유형 (10종):**

| chart_type | 설명 |
|---|---|
| `clustered_bar` | 묶은 세로 막대형 |
| `stacked_bar` | 누적 세로 막대형 |
| `100_stacked_bar` | 100% 누적 세로 막대형 |
| `clustered_horizontal_bar` | 묶은 가로 막대형 |
| `line` | 꺾은선형 |
| `line_markers` | 표식이 있는 꺾은선형 |
| `pie` | 원형 |
| `doughnut` | 도넛형 |
| `area` | 영역형 |
| `radar` | 방사형 |

#### 변경 영향 범위

| 계층 | 변경 내용 |
|---|---|
| **스키마** | `ChartDataSeries`, `PptxChart` dataclass 추가. `PptxSlideSpec`에 `charts` 필드 추가 |
| **LLM 출력 모델** | `ChartOutput` Pydantic 모델 추가. `SlideSpecOutput`에 `charts` 필드 및 변환 로직 추가 |
| **파서/직렬화** | `charts` 배열 파싱 및 직렬화 지원. z_index 정리에 `charts` 포함 |
| **PPTX 내보내기** | `chart_builder` 모듈 신규 생성. python-pptx 네이티브 Chart API로 결정적 변환. SlideBuilder의 z_index 분기에 charts 통합 |
| **HTML 미리보기** | `chart_renderer` 모듈 신규 생성. 외부 라이브러리 없이 인라인 SVG로 근사 렌더링. PPTX와 동일할 필요 없음 — 레이아웃 확인 목적 |
| **PPTX 임포트** | 기존 차트 무시 → 차트 메타데이터(유형, 카테고리, 시리즈) 역추출로 변경 |
| **디자인 프롬프트** | 차트 유형 선택 가이드, 데이터 가이드라인, 배치 규칙 추가 |
| **Visual QA** | 차트 요소의 겹침/overflow 감지 지원. 차트 내부 스타일은 QA 범위 밖 |

#### PPTX 내보내기 전략

python-pptx의 `CategoryChartData` + `add_chart()` API를 사용하여 네이티브 OOXML 차트를 생성한다. 이로써:
- PowerPoint에서 차트를 더블클릭하여 데이터를 편집할 수 있다
- 차트 스타일, 색상, 레이아웃을 PowerPoint UI에서 변경할 수 있다
- 도형 조합 방식의 좌표 부정확 문제가 근본적으로 해결된다

#### HTML 미리보기 전략

외부 JS 라이브러리(Chart.js 등)를 사용하지 않고, 순수 SVG 문자열을 생성하여 인라인한다. 정적 HTML iframe 환경과 호환되며, 데이터에서 좌표를 수학적으로 계산하여 정확한 비율을 보장한다.

### Alternatives Considered

1. **도형 조합 유지 (현행)**: 정확도 낮고 PPTX 편집 불가. 요소 수 20-30개로 폭증하여 토큰 비효율.
2. **이미지 기반 차트 (matplotlib/plotly → PNG)**: PPTX에서 편집 불가. 무거운 외부 의존성 필요.
3. **HTML 차트 라이브러리 → 스크린샷**: Playwright 의존 + 복잡한 파이프라인. PPTX에서 편집 불가.
4. **python-pptx 네이티브 Chart API (채택)**: PPTX 편집 가능, 정확한 수치, 추가 의존성 없음.

### Acceptance Criteria

- [ ] 디자인 스펙에서 `clustered_bar`, `line`, `pie` 차트를 정의할 수 있음
- [ ] PPTX 내보내기에서 네이티브 차트가 표시되고, PowerPoint에서 데이터 편집이 가능함
- [ ] HTML 내보내기에서 SVG 기반 차트 미리보기가 표시됨
- [ ] 디자인 스펙 생성 시 데이터 시각화가 필요한 슬라이드에 차트 요소를 생성함
- [ ] 슬라이드 수정(add/update)으로 차트가 포함된 슬라이드를 다룰 수 있음
- [ ] PPTX 임포트 시 기존 차트를 역추출할 수 있음 (지원 차트 유형 한정)
- [ ] 기존 차트 없는 디자인 스펙과 하위 호환
- [ ] 10개 차트 유형에 대한 단위 테스트

### Out of Scope

- 3D 차트 (python-pptx 3D 지원 제한)
- 콤보 차트 (막대+꺾은선 혼합) — 후속 ADR에서 별도 처리
- 외부 데이터 소스 연결 (정적 데이터만)
- 차트 애니메이션
- XY 산점도 / 버블 차트 (별도 데이터 모델 필요)
- HTML 미리보기와 PPTX 차트의 픽셀 단위 동일성

## Consequences

**긍정적:**
- PowerPoint 네이티브 차트로 인식되어 데이터 수정 및 스타일 변경 가능
- 데이터 → 시각화 매핑을 코드가 수학적으로 처리하여 LLM 좌표 부정확 문제 해소
- 도형 조합 대비 요소 수 대폭 감소 → 토큰 절약
- python-pptx 내장 기능으로 추가 외부 의존성 없음
- PPTX 임포트 시 차트 데이터 보존 (기존에는 완전 손실)

**부정적:**
- HTML SVG 미리보기와 PPTX 네이티브 차트의 외관 차이 가능
- LLM 시스템 프롬프트에 차트 스키마 설명 추가로 토큰 증가
- SVG 렌더러 구현/유지보수 비용 (10개 차트 유형)
- PPTX 임포트 시 모든 차트 유형의 완전한 역추출이 어려울 수 있음 (graceful degradation 필요)

## References

- [ADR-0001 (design): Design Spec Pipeline](0013-design-spec-pipeline.md) — 디자인 스펙 아키텍처
- [ADR-0007 (design): Image Path Support](0030-image-path-and-corner-radius-support.md) — 새 요소 타입 추가 선례
