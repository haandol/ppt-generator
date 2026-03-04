# Architecture

## 주요 기능

- **아웃라인 생성** — 주제와 슬라이드 수를 입력하면 구조화된 아웃라인 JSON을 생성
- **발표 스크립트 생성** — 아웃라인 기반으로 슬라이드별 발표 스크립트(speaker notes) 작성
- **디자인 스펙 생성** — 슬라이드별 정밀한 레이아웃을 PptxSlideSpec JSON으로 설계
- **슬라이드별 수정** — 개별 슬라이드의 디자인 스펙을 추가/수정/삭제 (전체 재생성 불필요)
- **Visual QA** — Playwright 스크린샷 + Claude Vision으로 시각적 결함 자동 감지 및 수정 (opt-in)
- **HTML 미리보기** — 디자인 스펙에서 결정론적으로 HTML 변환
- **PPTX 내보내기** — 디자인 스펙에서 편집 가능한 PPTX로 결정론적 변환
- **PPTX 임포트** — 기존 PPTX 파일을 디자인 스펙으로 역변환하여 편집·미리보기 (LLM 호출 없이 결정론적 파싱)
- **프로젝트 관리** — `project_id` 기반으로 중간 결과물 저장/로드, 중간 단계부터 재개 가능

## 생성 파이프라인

```mermaid
flowchart LR
    A["주제 입력"] --> B["아웃라인\n생성"]
    B --> C["스크립트\n생성"]
    C --> D["디자인 스펙\n생성"]
    D -.->|"개별 수정"| D
    D -.->|"opt-in"| V["Visual QA\n(분석→수정 루프)"]
    V -.-> D
    D --> E{"내보내기"}
    E --> F["HTML\n미리보기"]
    E --> G["PPTX\n다운로드"]

    H["기존 PPTX\n파일"] -->|"import_pptx"| D
```

## 사용 워크플로우

```mermaid
flowchart TD
    A["사용자 입력\n(주제 + 슬라이드 수)"] --> B["1. generate_outline\n아웃라인 JSON 생성"]
    B --> C{"⏸ 아웃라인\n검토/수정"}
    C --> D["2. generate_script\n발표 스크립트 생성"]
    D --> E["3. generate_slides_design_spec\n디자인 스펙 생성\n(전체 또는 slide_indices 선택적)"]
    E --> F{"⏸ 검토"}
    F -->|"수정 필요"| G["modify_design_spec\n개별 슬라이드 수정"]
    G --> F
    F -->|"Visual QA"| V["visual_qa\n스크린샷 분석→자동 수정\n(max_iterations 반복)"]
    V --> F
    F -->|"완료"| H["4. 내보내기"]
    H --> I["export_pptx\n편집 가능한 .pptx"]
    H --> J["export_html\nHTML 미리보기"]

    K["기존 PPTX 파일"] -->|"import_pptx"| F
```

- 모든 도구는 `project_id`를 자동 생성하여 `~/.ppt-generator/<UUID>/`에 결과물을 저장합니다
- `load_*` 도구에 `project_id`를 전달하면 중간 단계부터 재개할 수 있습니다
- 첫 슬라이드 생성 시 디자인 테마를 추출하여 후속 슬라이드의 시각적 일관성을 유지합니다

## MCP 도구

### 생성 도구

| 도구                         | 설명                                                      |
| ---------------------------- | --------------------------------------------------------- |
| `generate_outline`           | 주제와 슬라이드 수를 기반으로 아웃라인 JSON 생성          |
| `generate_script`            | 아웃라인 기반 슬라이드별 발표 스크립트 생성               |
| `generate_slides_design_spec` | 슬라이드 디자인 스펙 생성 (전체 또는 선택적, 서버 내부 병렬 처리) |
| `modify_design_spec`         | 디자인 스펙의 개별 슬라이드 추가/수정/삭제                |
| `visual_qa`                  | 스크린샷 기반 시각적 결함 감지 및 자동 수정 (opt-in, Playwright 필요) |
| `export_html`                | 디자인 스펙에서 HTML 슬라이드 내보내기 (결정론적 변환)    |
| `export_pptx`                | 디자인 스펙에서 편집 가능한 PPTX 내보내기 (결정론적 변환) |
| `import_pptx`                | 기존 PPTX 파일을 디자인 스펙으로 역변환 (결정론적 파싱, HTML 미리보기 자동 생성) |

#### PPTX 임포트

`import_pptx`는 기존 PPTX 파일을 python-pptx 오브젝트 모델 기반으로 결정론적 파싱하여 DesignSpec으로 변환합니다. LLM 호출 없이 순수 파싱 로직으로 동작하므로 추가 비용이 없습니다.

- **지원 요소**: 텍스트박스, 도형(22종), 커넥터/선, 이미지, 배경, 발표자 노트
- **도형 22종**: Basic(3) + Arrows(5) + Polygons(7) + Stars(3) + Flowchart(3) + Line(1)
- **Graceful degradation**: 그룹 도형 → 평탄화, 테이블 → 도형 격자, 차트 → 경고, 비디오/오디오 → 무시
- **슬라이드 크기 정규화**: 외부 PPTX의 크기가 1280×720px이 아닌 경우 비례 스케일링
- 임포트 후 `modify_design_spec`, `visual_qa`, `export_html`, `export_pptx` 모두 즉시 사용 가능

> 상세 설계: [ADR-0027](adr/pipeline/0027-pptx-import-to-design-spec.md)

#### 디자인 스펙 병렬 생성

`generate_slides_design_spec`은 슬라이드별 독립 LLM 호출을 `ThreadPoolExecutor`로 병렬 처리합니다.

- **병렬 워커 수**: `DESIGN_SPEC_PARALLEL` 환경변수로 제어 (기본 `8`). API rate limit에 맞게 조절 가능
- **Longest-job-first 스케줄링**: 슬라이드 복잡도 점수(1~13)를 산출하여 복잡한 슬라이드부터 먼저 처리 → wall-clock time 단축
- **Adaptive thinking effort**: 복잡도에 따라 `high`(7~13) / `medium`(4~6) / `low`(1~3) effort를 동적 적용 → 단순 슬라이드 토큰 절약, 복잡한 슬라이드 품질 유지

#### Visual QA 파이프라인

`visual_qa`는 디자인 스펙 생성 후 실제 렌더링 결과의 시각적 결함을 자동 감지·수정합니다. Playwright + Claude Vision 기반이며 opt-in 방식으로 사용자 동의 후에만 실행됩니다.

```
for iteration in range(max_iterations):    # 기본 2회
    1. Playwright 스크린샷 캡처 (1280×720, ThreadPoolExecutor 병렬)
    2. Claude Vision 분석 (asyncio.gather 병렬, thinking_effort=medium)
       → has_issues=false → "pass" / "fixed"
       → has_issues=true  → 수정 대상 분류
    3. LLM 디자인 스펙 수정 (asyncio.gather 병렬, thinking_effort=high)
       → 스펙 저장 + HTML 재렌더링 → 다음 iteration에서 재검사
    종료: 이슈 없음 / 모든 수정 실패 / max_iterations 도달
```

**감지 이슈 타입 (10가지)**: `word_break` · `text_truncation` · `overlap` · `overflow` · `contrast` · `misalignment` · `wrong_vertical_alignment` · `inconsistent_font_size` · `inconsistent_spacing` · `arrow_disconnected`

**Scope 제약**: 시각적 속성(위치, 크기, 폰트, 색상, 정렬)만 수정하며 텍스트 콘텐츠는 변경하지 않습니다.

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `VISUAL_QA_PARALLEL` | `8` | 스크린샷 캡처 병렬 워커 수 |
| `VISUAL_QA_MAX_ITERATIONS` | `2` | 분석→수정 최대 반복 횟수 |

> Playwright 미설치 시 기존 기능에 영향 없습니다. 설치: `uv sync --group visual-qa && playwright install chromium`

### 프로젝트 관리 도구

| 도구                  | 설명                             |
| --------------------- | -------------------------------- |
| `list_projects`       | 기존 프로젝트 목록 조회          |
| `load_project_status` | 프로젝트 상태 및 메타데이터 로드 |
| `load_outline`        | 저장된 아웃라인 JSON 로드        |
| `load_script`         | 저장된 스크립트 JSON 로드        |
| `load_design_spec`    | 저장된 디자인 스펙 로드          |

## 사용 모델

디자인 스펙과 아웃라인 생성에는 Claude Extended Thinking을 사용합니다. 모든 LLM 호출은 Sonnet 4.6을 사용합니다.

| 용도              | Bedrock 모델 ID                          | Anthropic 모델 ID   | Max Tokens | Thinking Effort                          |
| ----------------- | ---------------------------------------- | -------------------- | ---------- | ---------------------------------------- |
| 디자인 스펙 생성  | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 64,000     | adaptive (슬라이드 복잡도 기반 high/medium/low) |
| 아웃라인          | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 32,000     | medium                                           |
| 스크립트          | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 32,000     | off                                              |
| Visual QA 분석   | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 64,000     | adaptive (medium)                                |
| Visual QA 수정   | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 64,000     | adaptive (high)                                  |

## 프로젝트 구조

```
ppt-generator/
├── src/ppt_generator/
│   ├── server.py                  # MCP 서버 진입점
│   ├── di/
│   │   └── container.py           # 의존성 주입 컨테이너
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 수치 상수
│   │   ├── schemas.py             # 내부 도메인 모델 (dataclass)
│   │   ├── llm_output_models.py   # LLM structured_output용 Pydantic 모델
│   │   └── prompts/               # 프롬프트 템플릿 (.prompt.md)
│   ├── templates/
│   │   ├── slide.html             # 개별 슬라이드 HTML 템플릿
│   │   ├── slides_container.html  # iframe 컨테이너 템플릿
│   │   └── layout_mapping.py      # layout_index → 슬라이드 레이아웃 매핑
│   └── tools/
│       ├── outline/               # 아웃라인 생성
│       ├── script/                # 발표 스크립트 생성
│       ├── design/                # 디자인 스펙 생성/수정
│       ├── slides/                # HTML 슬라이드 생성
│       ├── visual_qa/             # Visual QA (스크린샷 분석 + 자동 수정)
│       ├── pptx/                  # PPTX 내보내기
│       ├── pptx_import/           # PPTX 임포트 (외부 PPTX → 디자인 스펙)
│       └── project/               # 프로젝트 관리
├── env/
│   └── local.env                  # 샘플 환경변수 파일
├── docs/
│   ├── adr/                       # Architecture Decision Records
│   └── ppt-generator.alps.md     # ALPS 설계 문서
├── tests/
└── pyproject.toml
```

## 기술 스택

| 구성 요소               | 기술                               |
| ----------------------- | ---------------------------------- |
| 프로토콜                | Model Context Protocol (MCP)       |
| 언어                    | Python 3.13+                       |
| 패키지 관리             | uv + hatchling                     |
| 에이전트 프레임워크     | AWS Strands SDK (`strands-agents`) |
| LLM                     | Claude Sonnet 4.6 Extended Thinking |
| 슬라이드 프레임워크     | 순수 HTML/CSS (인라인 스타일)      |
| Visual QA               | Playwright headless Chromium (opt-in) |
| PPTX 내보내기           | python-pptx                        |
