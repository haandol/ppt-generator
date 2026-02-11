# PPT Generator

주제를 입력하면 AI가 자동으로 HTML 기반 프레젠테이션을 생성하고, 사용자의 수정 요청을 반영한 뒤 편집 가능한 PPTX로 내보내는 MCP 서버입니다.

Amazon Bedrock Claude로 콘텐츠를 생성하고, Titan Image Generator v2로 시각 자료를 만들어, HTML/CSS 기반 슬라이드로 자유로운 디자인을 구현합니다. 최종 확정 후 python-pptx로 편집 가능한 PPTX 파일로 내보냅니다. Claude Desktop, Kiro 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

## 처리 파이프라인

```
사용자 입력 (주제 + 슬라이드 수)
    ↓
F1: generate_outline   → 슬라이드 아웃라인 JSON 생성 (freeform 좌표 기반)
    ↓
F2: generate_script    → 아웃라인 기반 발표 스크립트 생성 (speaker_notes 채움)
    ↓
F3: generate_images    → 슬라이드별 이미지 생성 (Titan Image v2)
    ↓
F4: generate_slides    → 아웃라인 + 이미지 → HTML/CSS 슬라이드 생성 (세션 기반)
    ↓ (선택)
F5: modify_slides      → 사용자 수정 요청 반영 (반복 가능)
    ↓
F6: export_pptx        → 편집 가능한 PPTX 파일 내보내기
    ↓
출력: .pptx 파일 경로
```

모든 generate 도구에 `project_dir` 파라미터를 지정하면 각 단계의 결과물이 자동 저장됩니다. `load_*` 도구로 저장된 결과물을 불러와 중간 단계부터 재개할 수 있습니다.

## 요구사항

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- AWS 자격 증명 (`~/.aws/credentials` 또는 환경 변수)
  - Amazon Bedrock 모델 접근 권한 (Claude Opus 4, Titan Image Generator v2)

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
| `generate_outline` | 슬라이드 아웃라인 생성 | 주제, 슬라이드 수, [project_dir] | 아웃라인 JSON |
| `generate_script` | 발표 스크립트 생성 | 아웃라인 JSON, [project_dir] | speaker_notes 포함 아웃라인 JSON |
| `generate_images` | 슬라이드별 이미지 생성 | 아웃라인 JSON, [project_dir] | 이미지 경로 목록 JSON |
| `generate_slides` | HTML/CSS 슬라이드 생성 | 아웃라인 JSON, 이미지 경로 JSON, [project_dir] | session_id + HTML |
| `modify_slides` | 슬라이드 수정 | 세션 ID, 수정 요청 (자연어), [project_dir] | session_id + 수정된 HTML |
| `export_pptx` | PPTX 내보내기 | 세션 ID, [project_dir] | .pptx 파일 경로 |

### 로드 도구

| 도구 | 설명 | 입력 | 출력 |
|------|------|------|------|
| `load_project_status` | 프로젝트 상태 로드 | project_dir | 메타데이터 JSON |
| `load_outline` | 저장된 아웃라인 로드 | project_dir | 아웃라인 JSON |
| `load_script` | 저장된 스크립트 로드 | project_dir | speaker_notes 포함 아웃라인 JSON |
| `load_images` | 저장된 이미지 메타 로드 | project_dir | 이미지 경로 목록 JSON |
| `load_slides_html` | 저장된 슬라이드 로드 + 세션 복원 | project_dir | session_id + HTML |

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
│   │   └── layout_mapping.py      # layout_type → 슬라이드 레이아웃 매핑
│   └── tools/
│       ├── outline/               # F1: 아웃라인 생성
│       ├── script/                # F2: 발표 스크립트 생성
│       ├── images/                # F3: 이미지 생성
│       ├── slides/                # F4/F5: HTML 슬라이드 생성 + 수정
│       ├── pptx/                  # F6: PPTX 내보내기
│       └── project/               # F7: 프로젝트 저장/로드
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
| LLM | Amazon Bedrock - Claude Opus 4 |
| 이미지 생성 | Amazon Bedrock - Titan Image Generator v2 |
| 슬라이드 렌더링 | HTML/CSS (freeform 좌표 기반 자유 레이아웃) |
| PPTX 내보내기 | python-pptx (HTML → PPTX 변환) |
| HTML 파싱 | BeautifulSoup / lxml |
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
| `text_image` | 텍스트 + 이미지 | 이미지가 있는 본문 |
| `text_only` | 텍스트 전용 | 기본 폴백 레이아웃 |
| `chart` | 차트/콘텐츠 중심 | 데이터 시각화 |
| `closing` | 마무리 슬라이드 | 마지막 슬라이드 |
| `freeform` | 자유 배치 (좌표 기반) | **기본 모드**, elements 배열 사용 |
