"""테스트 공통 helper — fixture 가 아닌 데이터 생성 함수.

`conftest.py` 는 pytest 가 자동 로드하지만 일반 helper 는
`from _helpers import ...` 로 명시적으로 import 한다 (`tests/` 는
pytest rootdir 에 의해 sys.path 에 들어와 있어 import 가능).
"""

from __future__ import annotations

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
    """테스트용 PptxSlideSpec 생성."""
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
    """테스트용 DesignSpec 생성."""
    return DesignSpec(
        slides=[make_slide_spec(f"슬라이드 {i + 1}") for i in range(num_slides)]
    )
