# Key Data Schemas

내부 도메인 모델은 `interfaces/schemas.py`에 `@dataclass`로, LLM 출력 모델은 `interfaces/llm_output_models.py`에 Pydantic `BaseModel`로 정의되어 있습니다.

## 내부 도메인 모델 (`schemas.py`)

| Schema                                          | 용도                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| `OutlineRequest` / `OutlineResponse`            | 아웃라인 생성 입출력 (topic, num_slides → slides)                              |
| `ScriptRequest` / `ScriptResponse`              | 스크립트 생성 입출력 (outline → slides)                                        |
| `SlideOutline`                                  | 개별 슬라이드 아웃라인 (title, content_summary, component_hint, speaker_notes, slide_index) |
| `SlidesResponse`                                | HTML 슬라이드 생성 출력 (session_id, html)                                     |
| `ExportPptxResponse`                            | PPTX 내보내기 출력 (pptx_path)                                                 |
| `PptxTextRun` / `PptxParagraph` / `PptxTextBox` | PPTX 텍스트 요소                                                               |
| `PptxShape` / `PptxSlideSpec`                   | PPTX 도형/슬라이드 스펙 (speaker_notes 포함). PptxShape는 rectangle/rounded_rectangle/ellipse는 `add_shape()`, line은 `add_connector()`로 렌더링. line shape는 `end_arrow`, `start_arrow`, `dash_style` 속성 지원 |
| `DesignSpec`                                    | 프레젠테이션 전체 디자인 스펙 (PptxSlideSpec 리스트)                           |
| `ProjectMetadata`                               | 프로젝트 메타데이터 (topic, num_slides, steps_completed)                       |

## LLM 출력 모델 (`llm_output_models.py`)

| Schema                              | 용도                                                                                           |
| ----------------------------------- | ---------------------------------------------------------------------------------------------- |
| `SlideSpecOutput`                   | strands `structured_output_model`용 Pydantic 모델. `to_dataclass()`로 `PptxSlideSpec`으로 변환 |
| `TextRunOutput` / `ParagraphOutput` | LLM 출력용 텍스트 런/단락                                                                      |
| `TextBoxOutput` / `ShapeOutput`     | LLM 출력용 텍스트박스/도형                                                                     |
| `VisualQAIssue` / `VisualQAOutput`  | Visual QA 분석 결과 (이슈 타입, 심각도, 수정 제안)                                             |

## 슬라이드 아웃라인/스크립트 저장

아웃라인과 스크립트는 개별 JSON 파일로 저장됩니다. `outline/slide_01.json`, `script/slide_01.json` 형식이며, `slide_index`가 명시적으로 포함됩니다. Legacy fallback으로 JSONL(`outline.jsonl`) → JSON(`outline.json`) 순서로 지원합니다.

```json
// outline/slide_01.json
{"slide_index": 0, "title": "슬라이드 제목", "content_summary": "슬라이드에 담길 핵심 내용 요약", "component_hint": "bullets", "speaker_notes": "", "slide_type": "title"}
```

개별 슬라이드 접근: `load_outline_slide(project_id, slide_index)`, `load_script_slide(project_id, slide_index)`

## component_hint

슬라이드 본문 영역의 시각적 구조를 결정하는 힌트:

| component_hint  | 설명                         |
| --------------- | ---------------------------- |
| `bullets`       | 기본 불릿 포인트 (기본값)    |
| `two_column`    | 2칼럼 레이아웃               |
| `vs_comparison` | VS 비교 패널 (A vs B)        |
| `step_cards`    | 단계별 카드                  |
| `code_block`    | 코드 블록 포함               |
| `arch_diagram`  | 아키텍처 다이어그램 (흐름도) |
| `pipeline`      | 파이프라인 흐름              |
| `quote`         | 인용문 강조                  |
| `summary_grid`  | 요약 그리드 (2x2)            |
| `agenda`        | 목차 섹션                    |
| `info_cards`    | 정보 카드 그리드             |
| `feature_list`  | 기능/특징 리스트             |
| `cta`           | Call-to-Action 강조          |
| `process_flow`  | 프로세스 워크스루            |
| `quote_code`    | 인용문 + 코드 블록 조합      |
| `concept_list`  | 개념 설명 리스트             |
