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

### Pipeline — Active

- [0001: 슬라이드 아웃라인 생성 (F1)](./pipeline/0001-outline-generation.md)
- [0002: 발표 스크립트 생성 (F2)](./pipeline/0002-script-generation.md)
- [0007: 파이프라인 결과물 저장/로드 및 프로젝트 디렉토리 통합](./pipeline/0007-pipeline-artifact-persistence.md)
- [0008: 템플릿 분석](./pipeline/0008-template-analysis.md) — _Proposed_
- [0011: 점진적 구체화 파이프라인 설계](./pipeline/0011-progressive-refinement-pipeline.md)
- [0013: 디자인 스펙 기반 슬라이드 생성 파이프라인](./pipeline/0013-design-spec-pipeline.md)
- [0014: 파일 기반 통신, 슬라이드 단위 CRUD 및 파일 분리](./pipeline/0014-file-based-communication-and-per-slide-crud.md)
- [0016: 슬라이드별 HTML 파일 분리 및 iframe 컨테이너](./pipeline/0016-per-slide-html-iframe.md)
- [0017: 폰트 메트릭 기반 텍스트 오버플로우 방지](./pipeline/0017-font-metric-text-overflow-prevention.md)
- [0018: 디자인 스펙 병렬 생성, 프롬프트 캐싱 및 Adaptive Effort](./pipeline/0018-parallel-design-spec-and-prompt-caching.md)
- [0020: 토큰 사용량 추적 및 비용 추정](./pipeline/0020-token-usage-tracking-and-cost-estimation.md)
- [0021: 슬라이드 타입별 시스템 프롬프트 분리](./pipeline/0021-slide-type-specific-system-prompts.md)
- [0022: 타이틀 슬라이드 긴 제목 텍스트 잘림 수정](./pipeline/0022-title-slide-long-title-overflow-fix.md)
- [0023: 디자인 스펙 Validator](./pipeline/0023-design-spec-validator.md)
- [0024: Agenda Slide Optional Numbering](./pipeline/0024-agenda-optional-numbering.md)
- [0025: Enable Medium Thinking for Outline Generation](./pipeline/0025-outline-thinking-medium.md)
- [0026: Visual QA Pipeline](./pipeline/0026-visual-qa-pipeline.md)
- [0027: PPTX 임포트 → 디자인 스펙 변환](./pipeline/0027-pptx-import-to-design-spec.md)
- [0028: 개별 파일 기반 outline/script 저장 및 save_outline_slide 도구](./pipeline/0028-modify-design-spec-inline-outline.md)
- [0029: 텍스트 런 하이퍼링크 지원](./pipeline/0029-text-run-hyperlink-support.md)

## ADR 작성 가이드

새로운 ADR을 작성할 때는 다음 템플릿을 사용하세요:

```markdown
# N. [제목]

Date: YYYY-MM-DD

## Status

[Proposed | Accepted | Deprecated | Superseded | Merged into XXXX]

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

- [Architecture](../architecture.md)
- [ALPS 설계 문서](../ppt-generator.alps.md)
- [ADR GitHub](https://adr.github.io/)
