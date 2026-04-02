# Environment & Configuration

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- LLM 인증 (아래 중 하나 선택):
  - **Anthropic API** (권장): `ANTHROPIC_API_KEY` 환경변수 설정
  - **AWS Bedrock (기본)**: 별도 설정 없이 기본 AWS credential chain 사용 (`~/.aws/credentials`, 환경변수, IAM role 등)
    - Amazon Bedrock 모델 접근 권한 필요 (Claude Sonnet 4.6)
    - 리전: `us-east-1` (기본값)
  - **AWS Bedrock (API key)**: `AWS_BEARER_TOKEN_BEDROCK` 환경변수로 bearer token 설정 시 SigV4 대신 bearer token 인증 사용
    - 리전: `us-east-1` (기본값)

## 환경변수

| 환경변수                   | 값                      | 설명                                                                                                     |
| -------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| `LLM_PROVIDER`             | `anthropic` / `bedrock` | 명시적 provider 선택 (미설정시 auto-detect)                                                              |
| `ANTHROPIC_API_KEY`        | API Key 문자열          | Anthropic 직접 API 인증 (auto-detect 트리거)                                                             |
| `AWS_ACCESS_KEY_ID`        | AWS Access Key          | Bedrock IAM 인증                                                                                         |
| `AWS_SECRET_ACCESS_KEY`    | AWS Secret Key          | Bedrock IAM 인증                                                                                         |
| `AWS_REGION`               | AWS 리전                | Bedrock 리전 (기본: us-east-1)                                                                           |
| `AWS_BEARER_TOKEN_BEDROCK` | Bearer Token 문자열     | Bedrock API key (bearer token) 인증. 설정 시 bearer token 우선, 미설정 시 기본 AWS credential chain 사용 |
| `BEDROCK_DESIGN_MODEL_ID`  | 모델 ID 문자열          | 디자인 스펙 생성 Bedrock 모델 (기본: `global.anthropic.claude-sonnet-4-6`)                                |
| `ANTHROPIC_DESIGN_MODEL_ID`| 모델 ID 문자열          | 디자인 스펙 생성 Anthropic 모델 (기본: `claude-sonnet-4-6`)                                              |
| `BEDROCK_DESIGN_MAX_TOKENS`| 정수 (기본: 64000)      | 디자인 스펙 생성 max tokens                                                                              |
| `BEDROCK_OUTLINE_MODEL_ID` | 모델 ID 문자열          | 아웃라인/스크립트 Bedrock 모델 (기본: `global.anthropic.claude-sonnet-4-6`)                               |
| `ANTHROPIC_OUTLINE_MODEL_ID`| 모델 ID 문자열         | 아웃라인/스크립트 Anthropic 모델 (기본: `claude-sonnet-4-6`)                                             |
| `DESIGN_SPEC_PARALLEL`     | 정수 (기본: 8)          | 디자인 스펙 생성 시 슬라이드별 병렬 워커 수. API rate limit에 맞게 조절                                  |
| `VISUAL_QA_PARALLEL`       | 정수 (기본: 8)          | Visual QA 병렬 워커 수 (스크린샷 캡처 + LLM 분석)                                                       |
| `VISUAL_QA_MAX_ITERATIONS` | 정수 (기본: 2)          | Visual QA 최대 수정 반복 횟수                                                                            |
| `PPT_LOG_DIR`              | 디렉토리 경로 문자열    | 세션별 UUID 로그 파일 디렉토리 (권장, 예: `/tmp/ppt-generator`). 10MB 회전, 백업 2개                     |
| `PPT_LOG_FILE`             | 파일 경로 문자열        | 단일 로그 파일 경로 (레거시, `PPT_LOG_DIR` 우선). 10MB 회전, 백업 2개                                    |

> **Auto-detect 로직**: `LLM_PROVIDER` 미설정 시, `ANTHROPIC_API_KEY`가 있으면 `anthropic`, 없으면 `bedrock`으로 자동 선택됩니다.

## 사용 모델

| 용도              | Bedrock 모델 ID                          | Anthropic 모델 ID   | Max Tokens | Thinking Effort                          |
| ----------------- | ---------------------------------------- | -------------------- | ---------- | ---------------------------------------- |
| 디자인 스펙 생성  | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 64,000     | adaptive (슬라이드 복잡도 기반 high/medium/low) |
| 아웃라인          | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 32,000     | medium                                           |
| 스크립트          | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 32,000     | off                                              |
| Visual QA 분석   | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 64,000     | adaptive (medium)                                |
| Visual QA 수정   | `global.anthropic.claude-sonnet-4-6`     | `claude-sonnet-4-6` | 64,000     | adaptive (high)                                  |

## MCP Client Configuration

### Anthropic API 사용 시

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "PPT_LOG_DIR": "/tmp/ppt-generator"
      }
    }
  }
}
```

### AWS Bedrock 사용 시 (`~/.aws/credentials` 설정 완료 가정)

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "PPT_LOG_DIR": "/tmp/ppt-generator"
      }
    }
  }
}
```

### AWS 환경변수를 직접 지정하는 경우

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "LLM_PROVIDER": "bedrock",
        "AWS_ACCESS_KEY_ID": "AKIA...",
        "AWS_SECRET_ACCESS_KEY": "...",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

### Bedrock API key (bearer token) 사용 시

```json
{
  "mcpServers": {
    "ppt-generator": {
      "command": "uv",
      "args": ["--directory", "/path/to/ppt-generator", "run", "ppt-generator"],
      "env": {
        "LLM_PROVIDER": "bedrock",
        "AWS_BEARER_TOKEN_BEDROCK": "your-api-key",
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```
