# 기본 테마 색상 변경 (녹색-파랑-보라 그라데이션) 및 다이어그램 활용 강화

Date: 2026-04-18

## Status

Accepted

## Context

현재 기본 테마는 AWS 팔레트(#232F3E navy ↔ #FF9900 orange ↔ #FFC000 amber)를 사용한다. 이를 녹색-파랑-보라 그라데이션으로 변경하여 범용적인 테마로 전환한다. 또한 개념 설명 슬라이드에서 텍스트 나열보다 다이어그램을 적극 활용하도록 프롬프트를 개선한다.

## Decision

### 1. 색상 팔레트 변경

그라데이션 축: Emerald Green (#10B981) ↔ Blue (#3B82F6) ↔ Violet (#8B5CF6)

Dark mode: Slate 계열 배경(#0F172A ~ #1E293B), Blue 기반 accent, Green/Violet 보조 accent
Light mode: Slate 계열 연한 배경(#F8FAFC ~ #FFFFFF), 동일 accent 체계

### 2. 다이어그램 활용 강화

Outline 시스템 프롬프트에 다이어그램 선호 지침을 추가하여, 개념 설명 시 bullets 대신 arch_diagram, process_flow, pipeline 등의 시각적 component_hint를 우선 선택하도록 유도한다.

### Acceptance Criteria

- 디자인 시스템 프롬프트 4개 파일(base, title, closing, content)의 색상이 새 팔레트로 교체됨
- HTML 템플릿(slides.html)의 CSS 색상이 새 팔레트로 교체됨
- Outline 시스템 프롬프트에 다이어그램 선호 지침이 포함됨
- 기존 테스트 전체 통과

### Out of Scope

- 배경 이미지 변경 (별도 작업)
- Light mode 색상 검증 (현재 dark mode가 기본)

## Consequences

- 신규 생성 프레젠테이션부터 적용됨 (기존 프로젝트 미영향)
- AWS 브랜드 종속에서 벗어나 범용 테마로 전환
- 다이어그램 활용 강화로 시각적 품질 향상 기대

## References

- 0004: 슬라이드 타입별 시스템 프롬프트 분리
