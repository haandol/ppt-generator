# PPT Generator

주제를 입력하면 AI가 자동으로 HTML/CSS 기반 프레젠테이션을 생성하고, 사용자의 수정 요청을 반영한 뒤 편집 가능한 PPTX로 내보내는 MCP 서버입니다.

Amazon Bedrock Claude로 콘텐츠를 생성하고, HTML/CSS 기반 슬라이드로 자유로운 디자인을 구현합니다. 생성된 HTML은 브라우저에서 수직 스크롤로 디자인을 확인할 수 있으며, 최종 확정 후 python-pptx로 편집 가능한 PPTX 파일로 내보냅니다. Claude Desktop, Kiro 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

## 처리 파이프라인

### 설계 철학: 점진적 구체화 (Progressive Refinement)

파이프라인은 **추상에서 구체로** 단계적으로 변환하면서, 각 단계에서 디자인 자유도를 최대한 보존하도록 설계되었습니다.

```
텍스트 (가장 추상적)       — 사용자가 주제만 입력
  → 아웃라인 (구조화)      — 슬라이드 구성·요점·레이아웃을 JSON으로 정리
    → 스크립트 (구체적)     — 발표 내용(speaker_notes)을 채움
      → HTML 슬라이드       — LLM이 <section> 생성 → 템플릿에 삽입
        → PPTX              — 자유도를 최대한 유지하면서 편집 가능한 포맷으로 변환
```

HTML을 중간 표현으로 사용하는 이유는, python-pptx 직접 생성 대비 LLM이 HTML/CSS 코드로 자유 배치·스타일링을 할 수 있어 디자인 자유도가 훨씬 높기 때문입니다. LLM은 `<section>` 요소만 생성하고, 서비스가 템플릿(`slides.html`)에 삽입하여 일관된 슬라이드 구조를 보장합니다. 생성된 HTML은 브라우저에서 수직 스크롤로 디자인을 확인할 수 있으며, 최종 PPTX 변환 시에는 `<section>` 내 HTML 요소를 개별 편집 가능한 PPTX 객체(텍스트박스, 이미지, 도형)로 매핑하여 실무 편집성을 확보합니다.

### 파이프라인 흐름

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: generate_outline   → 슬라이드 아웃라인 JSON 생성 (freeform 좌표 기반)
    ↓
F2: generate_script    → 아웃라인 기반 발표 스크립트 생성 (speaker_notes 채움)
    ↓
F3: generate_slides    → 아웃라인 → HTML 슬라이드 생성 (1장씩 개별)
    ↓ (선택)
F4: modify_slides      → 사용자 수정 요청 반영 (슬라이드 단위 또는 전체, 반복 가능)
    ↓
F5: export_pptx        → 편집 가능한 PPTX 파일 내보내기
    ↓
출력: .pptx 파일 경로
```

모든 도구는 `project_id`를 자동 생성하여 `~/.ppt-generator/<UUID>/`에 결과물을 저장합니다. `load_*` 도구에 `project_id`를 전달하면 저장된 결과물을 불러와 중간 단계부터 재개할 수 있습니다.

### 프로젝트 디렉토리 구조

```
~/.ppt-generator/<UUID>/
  project.json         # 메타데이터 (주제, 슬라이드 수, 단계 완료 상태)
  outline.json         # F1 출력
  script.json          # F2 출력
  slides.html          # F3/F4 출력
  slides_meta.json     # 세션 메타 (session_id)
  presentation.pptx    # F5 출력
```

## 요구사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- AWS 자격 증명 (`~/.aws/credentials` 또는 환경 변수)
  - Amazon Bedrock 모델 접근 권한 (Claude Opus 4.6, Claude Sonnet 4.5)

## 시작하기

```bash
# 의존성 설치
uv sync

# 서버 실행 (stdio 모드)
uv run ppt-generator

# 테스트 실행
uv run pytest
```

## MCP 클라이언트 설정

`claude_desktop_config.json` 또는 MCP 클라이언트 설정에 추가:

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ppt-generator",
        "run",
        "ppt-generator"
      ]
    }
  }
}
```

## MCP 도구

### 생성 도구

| 도구 | 설명 | 입력 | 출력 |
|------|------|------|------|
| `generate_outline` | 슬라이드 아웃라인 생성 | 주제, 슬라이드 수, [project_id] | 아웃라인 JSON + project_id |
| `generate_script` | 발표 스크립트 생성 | 아웃라인 JSON, [project_id] | speaker_notes 포함 아웃라인 JSON + project_id |
| `generate_slides` | HTML 슬라이드 생성 | 아웃라인 JSON, [project_id] | session_id + HTML + project_id |
| `modify_slides` | 슬라이드 수정 | 세션 ID, 수정 요청, [slide_index], [project_id] | session_id + 수정된 HTML + project_id |
| `export_pptx` | PPTX 내보내기 | 세션 ID, [project_id] | project_id + .pptx 파일 경로 |

### 로드 도구

| 도구 | 설명 | 입력 | 출력 |
|------|------|------|------|
| `load_project_status` | 프로젝트 상태 로드 | project_id | 메타데이터 JSON |
| `load_outline` | 저장된 아웃라인 로드 | project_id | 아웃라인 JSON |
| `load_script` | 저장된 스크립트 로드 | project_id | speaker_notes 포함 아웃라인 JSON |
| `load_slides_html` | 저장된 슬라이드 로드 + 세션 복원 | project_id | session_id + HTML |

## 프로젝트 구조

```
ppt-generator/
├── src/ppt_generator/
│   ├── server.py                  # MCP 서버 진입점
│   ├── di/
│   │   └── container.py           # 의존성 주입 컨테이너
│   ├── interfaces/
│   │   ├── constants.py           # 모델 설정, 프롬프트, 상수
│   │   └── schemas.py             # 데이터클래스 (Request/Response)
│   ├── templates/
│   │   ├── slides.html            # HTML 슬라이드 템플릿 (TailwindCSS, 수직 스크롤)
│   │   └── layout_mapping.py      # layout_type → 슬라이드 레이아웃 매핑
│   └── tools/
│       ├── outline/               # F1: 아웃라인 생성
│       ├── script/                # F2: 발표 스크립트 생성
│       ├── slides/                # F3/F4: HTML 슬라이드 생성 + 수정
│       ├── pptx/                  # F5: PPTX 내보내기
│       └── project/               # F6: 프로젝트 저장/로드
├── docs/
│   ├── adr/                       # Architecture Decision Records
│   ├── ppt-generator.alps.xml     # ALPS 설계 문서
│   └── ppt-generator.alps.md      # ALPS 마크다운 내보내기
├── tests/
└── pyproject.toml
```

## 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| 프로토콜 | Model Context Protocol (MCP) |
| 에이전트 프레임워크 | AWS Strands SDK |
| LLM | Amazon Bedrock - Claude Opus 4.6, Sonnet 4.5 (아웃라인) |
| 슬라이드 프레임워크 | 순수 HTML/CSS (인라인 스타일, JavaScript 없음, 수직 스크롤) |
| PPTX 내보내기 | python-pptx (HTML → PPTX 변환) |
| HTML 파싱 | BeautifulSoup (`<section>` 기반 슬라이드 파싱) |
| 패키지 관리 | uv + hatchling |

## 아키텍처

Controller-Service 패턴 + 의존성 주입(DI):

- **Controller** (`controller.py`): MCP 도구 인터페이스, 입력 검증
- **Service** (`service.py`): 비즈니스 로직 (API 호출, HTML 생성/수정, PPTX 변환)
- **DIContainer** (`container.py`): Bedrock 모델, Agent, Service 생성 및 연결

## 레이아웃 타입

| layout_type | 설명 | 비고 |
|-------------|------|------|
| `title` | 제목 슬라이드 | 첫 번째 슬라이드 |
| `text_only` | 텍스트 전용 | 기본 폴백 레이아웃 |
| `chart` | 차트/콘텐츠 중심 | 데이터 시각화 |
| `closing` | 마무리 슬라이드 | 마지막 슬라이드 |
| `freeform` | 자유 배치 (좌표 기반) | **기본 모드**, elements 배열 사용 |
