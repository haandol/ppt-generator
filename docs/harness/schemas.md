# Key Data Schemas

내부 도메인 모델은 `interfaces/schemas.py`의 `@dataclass`로 정의합니다. 클라이언트의
LLM 출력은 `interfaces/output_models/`의 도메인별 Pydantic `BaseModel`로 검증합니다.
`interfaces/llm_output_models.py`는 기존 모델 이름과 import 경로를 그대로 재노출합니다.

## 내부 도메인 모델 (`schemas.py`)

| Schema                                          | 용도                                                                           |
| ----------------------------------------------- | ------------------------------------------------------------------------------ |
| `OutlineRequest` / `OutlineResponse`            | 아웃라인 생성 입출력 (topic, num_slides → slides)                              |
| `SlideOutline`                                  | 개별 슬라이드 아웃라인 (title, content_summary, component_hint, slide_type, layout_plan, speaker_notes, slide_index) |
| `SlidesResponse`                                | HTML 슬라이드 생성 출력 (session_id, html)                                     |
| `ExportPptxResponse`                            | PPTX 내보내기 출력 (pptx_path)                                                 |
| `PptxTextRun` / `PptxParagraph` / `PptxTextBox` | PPTX 텍스트 요소                                                               |
| `PptxShape` / `PptxSlideSpec`                   | PPTX 도형/슬라이드 스펙 (speaker_notes 포함). PptxShape는 rectangle/rounded_rectangle/ellipse는 `add_shape()`, line은 `add_connector()`로 렌더링. line shape는 `end_arrow`, `start_arrow`, `dash_style` 속성 지원 |
| `DesignSpec`                                    | 프레젠테이션 전체 디자인 스펙 (PptxSlideSpec 리스트)                           |
| `ProjectMetadata`                               | 프로젝트 메타데이터 (topic, num_slides, steps_completed)                       |

## LLM 출력 모델 (`llm_output_models.py`)

| Schema                              | 용도                                                                                           |
| ----------------------------------- | ---------------------------------------------------------------------------------------------- |
| `OutlineOutput` / `SlideOutlineOutput` | 아웃라인 prepare 응답 스키마와 ingest 검증에 함께 사용하는 엄격한 모델                      |
| `DesignDocDraftOutput`              | DESIGN.md 초안 prepare 응답 스키마와 ingest 검증에 함께 사용하는 엄격한 모델                  |
| `SpeakerScriptOutput` / `SpeakerScriptSlideOutput` | 슬라이드 번호와 발표자 노트를 검증하는 대본 응답 |
| `ContentSlideSpecOutput` / `TitleSlideSpecOutput` / `ClosingSlideSpecOutput` | `slide_spec_output_model()`이 선택하는 슬라이드별 응답 모델. prepare와 ingest가 공유하고 `to_dataclass()`로 `PptxSlideSpec`으로 변환 |
| `TextRunOutput` / `ParagraphOutput` | LLM 출력용 텍스트 런/단락                                                                      |
| `TextBoxOutput` / `ShapeOutput`     | LLM 출력용 텍스트박스/도형                                                                     |
| `VisualQAIssue` / `VisualQAOutput`  | Visual QA 분석 결과 (이슈 타입, 심각도, 수정 제안)                                             |

텍스트·도형 변환은 `output_models/elements.py`, 그리드 변환은 `output_models/layout.py`에
모은다. 전체 슬라이드 생성, 단일 요소 수정과 임포트 의미 트리 보완이 같은 변환을
사용해 렌더 필드와 계층 연결을 보존한다. 문자열·객체 응답의 검증은 `handoff.py`에서
입력 형식에 맞는 Pydantic 검증 함수를 호출한다.

## 슬라이드 아웃라인 저장

아웃라인은 개별 JSON 파일로 저장됩니다. `outline/slide_01.json` 형식이며, `slide_index`가 명시적으로 포함됩니다. Legacy fallback으로 JSONL(`outline.jsonl`) → JSON(`outline.json`) 순서로 지원합니다.

```json
// outline/slide_01.json
{"slide_index": 0, "title": "슬라이드 제목", "content_summary": "슬라이드에 담길 핵심 내용 요약", "component_hint": "bullets", "slide_type": "title", "layout_plan": "제목을 중앙에 배치하고 핵심 메시지를 한 줄로 강조", "speaker_notes": "발표를 시작하며 주제와 목적을 소개합니다."}
```

개별 슬라이드 저장·수정은 `save_outline_slide(project_id, slide_index, ...)`를 사용하고, 전체 내용 조회는 `load_outline(project_id, include_content=true)`를 사용합니다.

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
| `custom`        | layout_plan으로 설명하는 사용자 정의 구조 |
