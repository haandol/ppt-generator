"""텍스트박스와 도형에서 추출한 덱 테마가 같은 규칙을 따르는지 검사한다."""

from __future__ import annotations

from dataclasses import asdict

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.design.summary import extract_design_summary


def test_summary_collects_run_fonts_and_deduplicates_colors_without_mutation() -> None:
    spec = PptxSlideSpec(
        background_color="#101010",
        textboxes=[
            PptxTextBox(
                0,
                0,
                100,
                100,
                paragraphs=[
                    PptxParagraph(
                        runs=[
                            PptxTextRun(
                                "title", font_size_pt=28, bold=True, color="#ffffff"
                            ),
                            PptxTextRun("body", font_size_pt=18, color="#abcdef"),
                        ]
                    )
                ],
            )
        ],
        shapes=[
            PptxShape(
                0,
                100,
                100,
                100,
                fill_color="#222222",
                border_color="#333333",
                text_color="#abcdef",
                text_size_pt=72,
                paragraphs=[
                    PptxParagraph(
                        runs=[
                            PptxTextRun(
                                "emphasis", font_size_pt=32, bold=True, color="#ffffff"
                            ),
                            PptxTextRun("detail", font_size_pt=22),
                            PptxTextRun("default", color="#112233"),
                        ]
                    )
                ],
            )
        ],
    )
    before = asdict(spec)
    expected = {
        "background_color": "#101010",
        "text_colors": ["#112233", "#abcdef", "#ffffff"],
        "title_font_pt": 32,
        "body_font_pt": 22,
        "card_fills": ["#222222"],
        "card_borders": ["#333333"],
    }
    assert extract_design_summary(spec) == expected
    assert DesignService.extract_design_summary(spec) == expected
    assert asdict(spec) == before


def test_summary_does_not_infer_run_fonts_from_plain_shape_text() -> None:
    spec = PptxSlideSpec(
        shapes=[
            PptxShape(
                0,
                0,
                100,
                100,
                text="caption",
                text_size_pt=32,
                text_bold=True,
            )
        ]
    )
    assert extract_design_summary(spec) == {
        "background_color": None,
        "text_colors": [],
        "title_font_pt": None,
        "body_font_pt": None,
        "card_fills": [],
        "card_borders": [],
    }
