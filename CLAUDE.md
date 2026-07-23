# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

에이전트 가이드(구조, 컨벤션, 워크플로우)는 [AGENTS.md](./AGENTS.md)를 참조하세요.

## Quick Reference

```bash
uv sync                                          # 의존성 설치
uv run ppt-generator                             # MCP 서버 실행 (stdio 모드)
uv run pytest                                    # 전체 테스트
uv run pytest tests/test_xxx.py                  # 개별 테스트 파일
uv run pytest tests/test_xxx.py::test_func -v    # 특정 테스트 함수
```

패키지 매니저: uv | 빌드 시스템: hatchling | Python 3.13+ | 진입점: `ppt_generator.server:main`

## ADR-First 워크플로우 (필수)

새 기능 추가 또는 기존 기능 변경 시 **반드시 코드 작성 전에** ADR을 먼저 작성/수정하고 사용자 확인을 받아야 합니다.

1. **ADR 먼저 작성**: 기능/변경의 Context, Decision, Technical Details를 ADR에 정리
2. **사용자 확인**: ADR 내용을 사용자에게 제시하고 승인을 받음
3. **코드 구현**: 승인된 ADR을 기반으로 코드 작성

상세 규칙은 [AGENTS.md](./AGENTS.md)의 ADR 섹션을 참조하세요.

## HTML/PPTX 렌더 패리티

HTML 또는 PPTX 렌더링을 수정할 때는 같은 `DesignSpec`을 두 출력으로 검증합니다.
공유 필드는 렌더 패리티 분류표와 교차 렌더 테스트를 함께 갱신하고, 타이포그래피·좌표·
줄바꿈·불렛·화살표·효과 변경은 실제 HTML/PPTX 렌더도 비교합니다.
