---
name: ppt-import-verify
description: Verify PPTX import fidelity by comparing the original .pptx against the imported ppt-generator project — both visually (side-by-side rendered PNGs) and numerically (shape coordinate/size/font diff). Produces a per-slide match report and tags mismatches by root-cause category so the import code/lint can be improved. Use after importing a PPTX and the user wants to check how close it is, debug missing/misplaced elements, or iterate to near-parity. Keywords - "임포트 검증 / 원본 비교 / 일치율 / import verify / fidelity check / 원본이랑 안맞아".
---

# ppt-import-verify

임포트된 프로젝트가 원본 PPTX와 얼마나 일치하는지 **시각(육안) + 좌표(수치)** 이중으로
검증하고, 불일치를 **근본 원인 카테고리**로 태깅해 코드/린트 개선의 근거를 만든다.
작업별로 고유한 출력 디렉토리를 사용해 이전 캡처와 섞이지 않게 한다.

이 스킬은 코드를 수정하지 않는다 — **진단·측정·리포트**만 한다. 발견한 근본 원인은
승인된 코드 작업으로 이어갈 수 있다. 이미 수정까지 요청받았다면 같은 범위의 승인을
다시 묻지 않는다. 진단만 요청받았다면 이 스킬은 읽기 전용으로 끝낸다.

## 전제

- 대상 PPTX 원본 경로와, 이미 임포트된 프로젝트 ID(또는 `~/.ppt-generator/<id>/`)가 있어야 한다.
  아직 임포트하지 않았다면 먼저 `import_pptx` (또는 ppt-modify 스킬)로 임포트한다.
- 렌더 도구: LibreOffice(`soffice`) + `pdftoppm`. 없으면 원본 렌더 단계는 건너뛰고
  좌표 비교만 수행한다(스크립트가 자동 폴백).

## 절차

### 1. 원본 PPTX → 슬라이드 PNG
```bash
uv --directory "${CLAUDE_PLUGIN_ROOT}" run python \
  "${CLAUDE_PLUGIN_ROOT}/skills/ppt-import-verify/scripts/render_original.py" \
  "<원본.pptx>" "<작업별 출력 디렉토리>" --dpi 110 --slides 1,2,3,4
```
`soffice --headless --convert-to pdf` 로 PDF 를 만들고 `pdftoppm -png` 로 슬라이드별 PNG 를
`"<작업별 출력 디렉토리>"/ref-NN.png` 로 저장한다.

### 2. 임포트 프로젝트 → 슬라이드 PNG
```bash
uv --directory "${CLAUDE_PLUGIN_ROOT}" run --group visual-qa python \
  "${CLAUDE_PLUGIN_ROOT}/skills/ppt-import-verify/scripts/capture_import.py" \
  <project_id> --slides 1,2,3,4
```
프로젝트의 `VisualQAService.capture_screenshots` 를 재사용해
`~/.ppt-generator/<id>/screenshots/slide_NN_v<iter>.png` 를 생성한다(경로를 출력).
MCP `capture_slides` 를 써도 되지만, **코드를 방금 고쳤다면 MCP 서버가 옛 코드일 수 있으니**
이 스크립트로 직접 캡처하는 편이 안전하다. 재임포트가 필요하면 같은 방식으로
`${CLAUDE_PLUGIN_ROOT}/skills/ppt-import-verify/scripts/reimport.py` 를 실행한다.

### 3. 시각 비교 (육안)
각 슬라이드에 대해 원본 PNG 와 임포트 PNG 를 **둘 다 Read** 로 열어 나란히 비교한다.
아래를 슬라이드별로 점검한다:
- 요소 **누락**(차트/아이콘/도형/텍스트가 통째로 사라졌는가)
- **위치·크기** 차이(좌우/상하 밀림, 박스 크기)
- **폰트 크기·행간**(원본보다 크거나 작음, 줄바꿈/세로 넘침)
- **색상·정렬**

### 4. 좌표 비교 (수치)
```bash
uv --directory "${CLAUDE_PLUGIN_ROOT}" run python \
  "${CLAUDE_PLUGIN_ROOT}/skills/ppt-import-verify/scripts/coord_diff.py" \
  "<원본.pptx>" <project_id> --slides 1,2,3,4
```
원본 slide XML 을 프로젝트의 `SlideReader` 로 파싱한 유효 좌표(placeholder 상속 해석 포함)와
저장된 `design_spec/slide_NN.json` 값을 대조해, 요소 개수·좌표(px)·폰트(pt)·autofit·줄간격의
차이를 표로 출력한다. 임계값(기본 위치 ±4px, 폰트 ±1pt)을 넘는 항목만 강조한다.

### 5. 일치율 리포트 + 근본 원인 태깅
시각·좌표 결과에서 관찰한 누락 수와 좌표·폰트 차이, 실제 비교 범위를 제시한다.
일치율을 계산한다면 비교 단위·분모·허용 오차를 함께 밝히고, 근거 없는 종합 백분율을
만들지 않는다. 좌표 비교는 임포터와 같은 파서를 사용하므로 양쪽에서 누락된 요소는
잡지 못할 수 있다. 원본 PNG 비교가 이 한계를 보완한다. 불일치는 다음처럼 분류한다:

| 카테고리 | 증상 | 근본 원인 위치 |
|---|---|---|
| `autofit` | 텍스트가 원본보다 축소/확대 | `pptx_import/text_extractor.py` autofit 해석 |
| `stroke` | 라인아트 아이콘 선이 사라짐 | `slides/shape_renderer.py` custom SVG stroke |
| `chart` | 차트 누락/왜곡 | `pptx_import/chart_extractors.py` |
| `linespacing` | 행간 과다/과소로 세로 넘침 | `pptx_import/text_extractor.py` lnSpc 상속 |
| `inherit` | 폰트 크기/색 상속 실패 | `pptx_import/text_extractor.py` `_resolve_inherited_props` |
| `position` | 좌표/크기 밀림 | 그룹 좌표 변환(`compound_extractors.py`) / EMU 스케일 |
| `missing` | 그 외 요소 누락 | `shape_extractors.py` 분기 |

### 6. 확인 후 개선 루프
진단만 요청받았으면 근거와 수정 제안을 전달한다. 수정도 승인된 작업이면 원인에 맞는
코드 변경과 재임포트·재검증으로 이어간다. 기존 동작 복구와 구조 정리는 해당 작업 지침을
따르고, 새로운 계약이나 범위 변경만 별도 결정을 받는다. 공통 임포트 결함과 사용자가
원하는 개별 슬라이드 편집을 구분한다.

## 참고
- 로컬 clone/Kiro/Codex 환경에서는 `${CLAUDE_PLUGIN_ROOT}` 를 clone의 절대 경로로
  바꿔 실행한다.
- 폰트 렌더 차이(예: Amazon Ember 미설치)로 줄바꿈이 달라질 수 있으니, 폰트 설치 여부도 함께 본다.
