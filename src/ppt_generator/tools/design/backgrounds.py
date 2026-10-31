"""프로젝트 배경 정책을 슬라이드 생성·편집에 공통 적용한다."""

from __future__ import annotations

import logging
from dataclasses import replace

from ppt_generator.interfaces.schemas import PptxSlideSpec

logger = logging.getLogger(__name__)


def _enforce_background_color(
    spec: PptxSlideSpec,
    design_summary: dict | None,
    bg_image_policy: str,
    idx: int,
) -> PptxSlideSpec:
    """본문의 덱 배경을 유지하고 이미지 없는 표지의 누락된 색상만 보완한다.

    표지·클로징에 명시된 단색은 자동 배경 보완으로 덮어쓰지 않는다.
    """
    _enforce_bg = spec.slide_type == "content" or (
        bg_image_policy == "none" and not spec.background_color
    )
    if (
        design_summary
        and _enforce_bg
        and design_summary.get("background_color")
        and spec.background_color != design_summary["background_color"]
    ):
        logger.info(
            "slide[%d] 배경색 보정: %s → %s",
            idx,
            spec.background_color,
            design_summary["background_color"],
        )
        spec = replace(spec, background_color=design_summary["background_color"])
    return spec
