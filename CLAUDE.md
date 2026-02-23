# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

프로젝트 구조, 아키텍처, 코딩 규칙, 환경변수 등 모든 상세 가이드는 [AGENTS.md](./AGENTS.md)를 참조하세요.
설계 문서: [`docs/ppt-generator.alps.md`](docs/ppt-generator.alps.md)

## Quick Reference

```bash
uv sync                                          # 의존성 설치
uv run ppt-generator                             # MCP 서버 실행 (stdio 모드)
uv run pytest                                    # 전체 테스트
uv run pytest tests/test_xxx.py                  # 개별 테스트 파일
uv run pytest tests/test_xxx.py::test_func -v    # 특정 테스트 함수
```

패키지 매니저: uv | 빌드 시스템: hatchling | Python 3.13+ | 진입점: `ppt_generator.server:main`
