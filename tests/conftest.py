"""공통 테스트 fixture 및 헬퍼."""

from __future__ import annotations

import pytest
from pptx import Presentation

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxImage,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)


def make_slide_spec(
    title: str = "테스트",
    *,
    images: list[PptxImage] | None = None,
) -> PptxSlideSpec:
    """테스트용 PptxSlideSpec 생성 헬퍼."""
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=[
            PptxTextBox(
                left_px=40,
                top_px=40,
                width_px=600,
                height_px=60,
                paragraphs=[
                    PptxParagraph(
                        runs=[PptxTextRun(text=title, font_size_pt=32, bold=True)]
                    ),
                ],
            ),
        ],
        shapes=[],
        images=images or [],
        speaker_notes="",
    )


def make_design_spec(num_slides: int = 3) -> DesignSpec:
    """테스트용 DesignSpec 생성 헬퍼."""
    return DesignSpec(
        slides=[make_slide_spec(f"슬라이드 {i + 1}") for i in range(num_slides)]
    )


@pytest.fixture
def blank_slide():
    """python-pptx 빈 슬라이드 생성."""
    prs = Presentation()
    return prs.slides.add_slide(prs.slide_layouts[6])
