# Architecture Decision Records (ADR)

이 디렉토리는 PPT Generator 프로젝트의 주요 아키텍처 결정을 문서화합니다.

## ADR이란?

Architecture Decision Record (ADR)는 소프트웨어 개발 과정에서 내린 중요한 아키텍처 결정을 기록하는 문서입니다. 각 ADR은 다음을 포함합니다:

- **Context**: 결정이 필요했던 배경과 문제
- **Decision**: 내린 결정과 그 이유
- **Consequences**: 결정의 긍정적/부정적 영향

## 디렉토리 구조

```
adr/
└── pipeline/         # 파이프라인 피쳐별 결정
```

## 카테고리별 ADR 목록

### Pipeline

- [0001: 슬라이드 아웃라인 생성 (F1)](./pipeline/0001-outline-generation.md)
- [0002: 발표 스크립트 생성 (F2)](./pipeline/0002-script-generation.md)
- [0003: 이미지 생성 (F3)](./pipeline/0003-image-generation.md)
- [0004: HTML 슬라이드 생성 (F4)](./pipeline/0004-html-slide-generation.md)
- [0005: 슬라이드 수정 (F5)](./pipeline/0005-slide-modification.md)
- [0006: PPTX 내보내기 (F6)](./pipeline/0006-pptx-export.md)
- [0007: 파이프라인 결과물 저장/로드](./pipeline/0007-pipeline-artifact-persistence.md)
- [0009: 이미지 파일 참조 방식 전환](./pipeline/0009-image-file-reference.md)
- [0010: 워킹 디렉토리 통합 및 슬라이드 개별 생성/수정](./pipeline/0010-workspace-and-per-slide.md)
- [0011: 점진적 구체화 파이프라인 설계](./pipeline/0011-progressive-refinement-pipeline.md)
- [0012: 레이아웃 골격(Skeleton) 기반 위치 강제](./pipeline/0012-layout-skeleton-enforcement.md)

## ADR 작성 가이드

새로운 ADR을 작성할 때는 다음 템플릿을 사용하세요:

```markdown
# N. [제목]

Date: YYYY-MM-DD

## Status

[Proposed | Accepted | Deprecated | Superseded]

## Context

[결정이 필요한 배경과 문제 설명]

## Decision

[내린 결정과 그 이유]

### Technical Details
### Alternatives Considered
### Acceptance Criteria
### Out of Scope

## Consequences

[긍정적/부정적 영향, 리스크]

## References

[관련 파일, ADR 링크]
```

## 명명 규칙

- 파일명: `XXXX-kebab-case-title.md`
- 번호는 카테고리 내에서 순차적으로 증가
- 제목은 명확하고 간결하게

## 참고

- [ALPS 설계 문서](../ppt-generator.alps.md)
- [ADR GitHub](https://adr.github.io/)
