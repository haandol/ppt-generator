# 13. 이미지 생성을 HTML 슬라이드 생성에 통합

Date: 2026-02-12

## Status

Accepted

## Context

기존 파이프라인에서 이미지 생성(F3)은 HTML 슬라이드 생성(F4) 이전에 독립된 단계로 존재했다:

```
F1(아웃라인) → F2(스크립트) → F3(이미지) → F4(HTML 슬라이드) → F5(수정) → F6(PPTX) → F7(저장/로드)
```

이 구조의 문제점:

1. **불필요한 단계 분리**: 이미지 생성은 슬라이드 생성 과정에서 필요한 경우에만 수행되면 되지만, 독립 단계로 존재하여 파이프라인이 불필요하게 복잡해짐
2. **text_only 슬라이드 비효율**: 이미지가 필요 없는 슬라이드(text_only, chart, closing 등)도 이미지 생성 단계를 거쳐야 함
3. **MCP 클라이언트 호출 횟수 증가**: 클라이언트가 generate_images를 별도로 호출하고 결과를 generate_slides에 전달해야 하는 추가 작업 필요
4. **이미지 모델 변경**: Amazon Titan Image Generator v2에서 Google Gemini 2.5 Flash로 이미지 생성 모델이 변경됨

## Decision

이미지 생성을 독립 파이프라인 단계에서 제거하고, HTML 슬라이드 생성(F3) 내부에서 필요한 경우에만 이미지를 생성하도록 통합한다.

변경 후 파이프라인:

```
F1(아웃라인) → F2(스크립트) → F3(HTML 슬라이드 + 내부 이미지 생성) → F4(수정) → F5(PPTX) → F6(저장/로드)
```

### Technical Details

- `generate_slides`가 슬라이드 생성 과정에서 `layout_index`를 확인하여 이미지가 필요한 슬라이드에 대해서만 내부적으로 이미지를 생성
- `SKIP_IMAGE_LAYOUT_INDICES`에 해당하는 레이아웃(text_only, chart, title, closing 등)은 이미지 생성을 건너뜀
- MCP 클라이언트는 `generate_slides`만 호출하면 되며, 이미지 경로를 별도로 전달할 필요 없음
- 이미지 생성 모델: Google Gemini 2.5 Flash (`gemini-2.5-flash-image`)
- `ImageRequest`, `ImageResult`, `ImageResponse` 스키마는 내부 스키마로 유지

### MCP Tool Interface 변경

기존:
```
generate_images(outline_json) → 이미지 경로 목록
generate_slides(outline_json, images_json) → HTML 슬라이드
```

변경 후:
```
generate_slides(outline_json) → HTML 슬라이드 (이미지 내부 생성)
```

### Acceptance Criteria

1. `generate_slides` 호출 시 이미지가 필요한 슬라이드에 대해 자동으로 이미지가 생성된다
2. `SKIP_IMAGE_LAYOUT_INDICES`에 해당하는 슬라이드는 이미지 생성을 건너뛴다
3. MCP 클라이언트가 `generate_images`를 별도로 호출할 필요가 없다
4. 기존 이미지 생성 품질이 유지된다

### Out of Scope

- `generate_images` MCP 도구의 코드 제거 (하위 호환을 위해 당분간 유지 가능)

## Consequences

### 긍정적

- 파이프라인 단계가 7단계에서 6단계로 단순화됨 (F1~F6)
- MCP 클라이언트의 호출 횟수 감소 (generate_images + generate_slides → generate_slides만)
- text_only 등 이미지 불필요 슬라이드의 처리 효율 향상
- 이미지 생성과 슬라이드 생성의 결합도가 높아져 이미지 배치 최적화 가능

### 부정적

- 이미지만 독립적으로 재생성하려면 generate_slides를 다시 호출해야 함
- generate_slides의 책임이 증가함

## References

- Supersedes: [0003-image-generation](./0003-image-generation.md)
- 관련 ADR: [0004-html-slide-generation](./0004-html-slide-generation.md)
- 구현: `src/ppt_generator/tools/slides/service.py`, `src/ppt_generator/tools/images/service.py`
- ALPS: Section 7.3
