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
- [0004: HTML 슬라이드 생성 (F3)](./pipeline/0004-html-slide-generation.md) — *Superseded by 0013*
- [0005: 슬라이드 수정 (F4)](./pipeline/0005-slide-modification.md) — *Superseded by 0013/0014*
- [0006: PPTX 내보내기 (F5)](./pipeline/0006-pptx-export.md) — *Superseded by 0013*
- [0007: 파이프라인 결과물 저장/로드](./pipeline/0007-pipeline-artifact-persistence.md)
- [0008: 템플릿 분석](./pipeline/0008-template-analysis.md)
- [0010: 워킹 디렉토리 통합 및 슬라이드 개별 생성/수정](./pipeline/0010-workspace-and-per-slide.md)
- [0011: 점진적 구체화 파이프라인 설계](./pipeline/0011-progressive-refinement-pipeline.md)
- [0012: 레이아웃 골격(Skeleton) 기반 위치 강제](./pipeline/0012-layout-skeleton-enforcement.md) — *Superseded by 0013*
- [0013: 디자인 스펙 기반 슬라이드 생성 파이프라인](./pipeline/0013-design-spec-pipeline.md)
- [0014: 파일 기반 통신 및 슬라이드 단위 CRUD](./pipeline/0014-file-based-communication-and-per-slide-crud.md)
- [0015: 디자인 스펙 슬라이드별 파일 분리](./pipeline/0015-per-slide-file-separation.md)
- [0016: 슬라이드별 HTML 파일 분리 및 iframe 컨테이너](./pipeline/0016-per-slide-html-iframe.md)
- [0017: 폰트 메트릭 기반 텍스트 오버플로우 방지](./pipeline/0017-font-metric-text-overflow-prevention.md)
- [0018: 디자인 스펙 병렬 생성 및 프롬프트 캐싱](./pipeline/0018-parallel-design-spec-and-prompt-caching.md)

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
