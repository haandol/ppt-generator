# PPTX 이미지 종횡비 보존 (contain 방식)

Date: 2026-04-02

## Status

Accepted

## Context

디자인 스펙의 이미지 영역(예: 205×296px 세로 영역)에 가로 이미지(예: 1920×1080px 16:9)를 삽입할 때, HTML과 PPTX의 렌더링 결과가 다르다.

- **HTML**: `object-fit: contain`으로 비율 유지, 영역 내에 맞춤 (여백 발생)
- **PPTX**: `add_picture(width, height)`에 width/height를 모두 지정하면 이미지가 강제로 늘어나 비율이 깨짐

이미지 원본 비율과 디자인 스펙 영역 비율이 다른 경우 PPTX에서 찌그러진 이미지가 나온다.

## Decision

`_add_image_from_spec()`에서 `add_picture()` 호출 시 contain 방식으로 비율을 보존한다.

### Technical Details

**변경 파일**: `src/ppt_generator/tools/pptx/slide_builder.py` — `_add_image_from_spec()`

**현재 동작:**
```python
slide.shapes.add_picture(image_stream, left, top, width, height)
```
width/height를 모두 지정하여 이미지가 강제로 늘어남.

**변경 후 동작 (contain 방식):**
1. 이미지 원본 크기를 `PIL.Image` 또는 python-pptx의 이미지 메타데이터로 읽음
2. 원본 비율과 디자인 스펙 영역 비율을 비교
3. 영역 내에 비율을 유지하면서 최대 크기로 맞춤 (contain)
4. 영역 내 중앙 정렬 (남는 공간을 좌우 또는 상하로 균등 분배)

```python
# contain 계산
img_ratio = original_width / original_height
box_ratio = spec_width / spec_height
if img_ratio > box_ratio:
    # 이미지가 더 넓음 → width에 맞추고 height는 비율 계산
    fit_width = spec_width
    fit_height = spec_width / img_ratio
else:
    # 이미지가 더 높음 → height에 맞추고 width는 비율 계산
    fit_height = spec_height
    fit_width = spec_height * img_ratio
# 중앙 정렬
offset_x = (spec_width - fit_width) / 2
offset_y = (spec_height - fit_height) / 2
```

### Acceptance Criteria

- PPTX 내보내기 시 이미지 원본 비율이 보존된다
- 이미지가 디자인 스펙 영역 내에서 중앙 정렬된다
- HTML과 PPTX의 이미지 렌더링 결과가 시각적으로 일치한다
- 기존 테스트 통과

### Out of Scope

- `object-fit: cover` 방식 (영역을 꽉 채우고 넘치는 부분 자름) — 필요 시 별도 구현
- corner_radius_px의 PPTX 반영 (python-pptx 제약)

## Consequences

**긍정적:**
- HTML과 PPTX 간 이미지 렌더링 일관성 확보
- 이미지 비율 왜곡 제거

**부정적:**
- 이미지 영역에 여백이 생길 수 있음 (contain 방식의 특성)

## References

- `src/ppt_generator/tools/pptx/slide_builder.py` — `_add_image_from_spec()`
- `src/ppt_generator/tools/slides/html_renderer.py` — `image_to_html()` (object-fit: contain)
- [ADR-0007 (design)](0030-image-path-and-corner-radius-support.md) — 이미지 image_path 지원
