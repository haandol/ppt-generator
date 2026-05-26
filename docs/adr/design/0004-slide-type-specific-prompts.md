# 슬라이드 타입별 시스템 프롬프트 분리

Date: 2026-02-25

## Status

Accepted

## Context

디자인 스펙 생성 시 LLM이 title/closing 슬라이드의 메인 텍스트를 `top=72`(content 슬라이드의 제목 위치)에 배치하는 문제가 반복 발생했다. 프롬프트 강화(⚠️ 경고문, bold 표기, 부정 지시 등)와 validator 보정을 시도했으나 근본적으로 해결되지 않았다.

### 근본 원인 분석

1. **`top=72` 빈도 우세**: 단일 시스템 프롬프트에서 `top=72`가 ~10회 등장 (3개 content 예제 + layout 규칙 + agenda 규칙) vs `top=260`/`top=240`은 각 ~5회
2. **부정 지시의 역효과**: "top=72를 사용하지 마세요"라는 지시가 오히려 `top=72` 값을 강화
3. **예제의 압도적 영향력**: 구조화된 출력에서 LLM은 텍스트 규칙보다 예제를 더 강하게 모방
4. **slide_type 미구분**: 출력 스키마에 slide_type 필드가 없어 LLM이 현재 생성 중인 타입을 자기참조 불가

### validator 보정의 한계

validator가 title/closing의 첫 텍스트박스를 강제로 아래로 이동시키면, 하위 요소(부제목, 연락처 등)도 같은 offset만큼 밀려나 캔버스 하단을 넘어 잘리는 문제 발생. validator의 현재 보정 규칙 상세는 [ADR-0001 (lint)](../lint/0001-design-spec-validator.md) 참조.

## Decision

### 시스템 프롬프트를 공통 베이스 + slide_type별 파일로 분리

| 파일 | 역할 | 포함 내용 |
|------|------|----------|
| `design_system_base.prompt.md` | **공통 베이스** | role, language_policy, coordinate_system, output_schema, design_principles, output_rules |
| `design_system_content.prompt.md` | content 전용 | layout_grid, diagram_grid, shapes 가이드, agenda/content 규칙, 3개 content 예제, content 전용 constraints |
| `design_system_title.prompt.md` | title 전용 | title 규칙, 1개 title 예제, title 전용 typography/constraints |
| `design_system_closing.prompt.md` | closing 전용 | closing 규칙, 1개 closing 예제, closing 전용 typography/constraints |

로딩 시 `base + "\n\n" + type별 파일`을 합쳐 최종 시스템 프롬프트를 구성한다.

**핵심 원칙**: title/closing 프롬프트에는 `top=72`가 **한 번도 등장하지 않음**.

### 코드 변경

1. **프롬프트 로딩**: `DESIGN_SPEC_SYSTEM_PROMPTS: dict[str, str]` — slide_type을 key로 프롬프트 매핑
2. **팩토리 시그니처**: `Callable[[str], DesignService]` → `Callable[[str, str], DesignService]` (effort, slide_type)
3. **Agent 생성**: `DIContainer._create_design_agent(effort, slide_type)` — slide_type에 해당하는 시스템 프롬프트로 Agent 생성
4. **병렬 러너**: `outline.slides[idx].slide_type`을 읽어 팩토리에 전달
5. **validator**: `_fix_title_closing_center()` 제거 — 프롬프트 분리로 불필요

### 프롬프트 캐싱 영향

- **content 슬라이드** (N-2장): 동일 시스템 프롬프트 → 기존과 동일한 캐시 적중률
- **title/closing** (각 1장): 캐시 miss 1회씩 발생하나, 프롬프트가 content 대비 ~60% 짧아 입력 토큰 자체가 절감

## Consequences

### Positive

- **근본 원인 해결**: title/closing 프롬프트에 `top=72`가 없으므로 LLM이 해당 값을 학습/모방할 수 없음
- **validator 불필요**: 강제 보정 로직 제거로 하위 요소 잘림 문제 원천 차단
- **토큰 절감**: title/closing 프롬프트에서 layout_grid, diagram_grid, content 예제 등 불필요한 섹션 제거 (~200줄 감소)
- **유지보수 용이**: slide_type별 독립 수정 가능, 한 타입의 규칙 변경이 다른 타입에 영향 없음

### Negative

- **파일 수 증가**: 1개 → 4개 프롬프트 파일 (base + 3개 타입별). 공통 베이스 분리로 중복은 해소됨
- **Agent 인스턴스 다양화**: slide_type별 다른 시스템 프롬프트로 Agent를 생성하므로, 병렬 처리 시 Agent 풀이 다양해짐

## References

- 프롬프트 파일: `src/ppt_generator/interfaces/prompts/design_system_{base,content,title,closing}.prompt.md`
- 프롬프트 로딩: `src/ppt_generator/interfaces/prompts/__init__.py` — `DESIGN_SPEC_SYSTEM_PROMPTS`
- 팩토리: `src/ppt_generator/di/container.py` — `create_design_service(effort, slide_type)`
- 병렬 러너: `src/ppt_generator/tools/design/parallel_runner.py` — `_generate_slide()`
- 관련 ADR: [0018-parallel-design-spec-and-prompt-caching](./0003-parallel-design-spec.md), [0023-design-spec-validator](../lint/0001-design-spec-validator.md)
