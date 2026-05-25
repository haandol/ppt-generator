"""렌더러의 paragraph 단위 nowrap 보정 회귀 테스트.

ADR-0017 §4 (렌더링 단계 nowrap 보정) 회귀 방지.

PPT는 시스템 폰트(맑은 고딕/Consolas) 메트릭으로 폭을 측정하지만 브라우저는
웹 폰트(Noto Sans KR/Source Code Pro) 메트릭으로 렌더링하기 때문에, 박스 폭에
거의 들어맞는 텍스트가 두 줄로 wrap 되어 height가 늘어나고 옆/아래 화살표
좌표가 어긋나는 회귀가 발생한다. 렌더러는 paragraph 단위로
``should_apply_nowrap_to_paragraph``를 호출해 ``white-space:nowrap``을 적용한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.slides.html_renderer import textbox_to_html
from ppt_generator.tools.slides.shape_renderer import shape_to_html


def _para(*runs: PptxTextRun, alignment: str = "left") -> PptxParagraph:
    return PptxParagraph(runs=list(runs), bullet_level=-1, alignment=alignment)


class TestShapeMultiParagraphNowrap:
    """shape에 paragraph가 여러 개라도 각 paragraph가 tolerance 안이면 nowrap 적용."""

    def test_first_paragraph_borderline_gets_nowrap_when_second_para_exists(self):
        # "도구 호출 요청 (JSON)" — 14pt, usable width ≈ 256px,
        # 추정 폭 ≈ 189px → 1.15× tolerance 안쪽이므로 nowrap.
        shape = PptxShape(
            left_px=516,
            top_px=397.8,
            width_px=280,
            height_px=82,
            shape_type="rounded_rectangle",
            padding_left_px=12,
            padding_right_px=12,
            padding_top_px=8,
            padding_bottom_px=8,
            paragraphs=[
                _para(
                    PptxTextRun(
                        text="도구 호출 요청 (JSON)", font_size_pt=14, bold=True
                    )
                ),
                _para(
                    PptxTextRun(
                        text='{"tool": "web_search", ...}',
                        font_size_pt=12,
                        font_family="monospace",
                    )
                ),
            ],
        )
        html = shape_to_html(shape)

        # 두 paragraph 각각이 nowrap을 받아야 한다.
        assert html.count("white-space:nowrap") >= 1, html

    def test_long_paragraph_does_not_get_nowrap(self):
        # 좁은 박스에 긴 한글 텍스트 → tolerance 초과 → nowrap 미적용.
        shape = PptxShape(
            left_px=0,
            top_px=0,
            width_px=200,
            height_px=80,
            shape_type="rounded_rectangle",
            padding_left_px=12,
            padding_right_px=12,
            paragraphs=[
                _para(
                    PptxTextRun(
                        text="제목",
                        font_size_pt=14,
                        bold=True,
                    )
                ),
                _para(
                    PptxTextRun(
                        text="이 문장은 의도적으로 길게 작성된 본문이라 절대 한 줄에 들어갈 수 없다 한 줄에 들어갈 수 없다",
                        font_size_pt=14,
                    )
                ),
            ],
        )
        html = shape_to_html(shape)

        # 긴 paragraph는 nowrap이 안 붙어야 wrap이 동작한다.
        # 첫 짧은 paragraph는 nowrap을 받아도 무방하므로 횟수만 검사.
        assert html.count("white-space:nowrap") <= 1, html


class TestTextboxMultiParagraphNowrap:
    """textbox에 paragraph가 여러 개라도 paragraph 단위로 nowrap 판정."""

    def test_textbox_short_paragraphs_each_get_nowrap(self):
        tb = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=400,
            height_px=120,
            padding_left_px=8,
            padding_right_px=8,
            paragraphs=[
                _para(PptxTextRun(text="짧은 제목", font_size_pt=18, bold=True)),
                _para(PptxTextRun(text="짧은 부제", font_size_pt=14)),
            ],
        )
        html = textbox_to_html(tb)
        # multi-paragraph여도 각 paragraph가 nowrap을 받음.
        assert html.count("white-space:nowrap") == 2, html

    def test_textbox_with_bullets_skips_nowrap(self):
        tb = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=400,
            height_px=200,
            padding_left_px=8,
            padding_right_px=8,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="항목 1", font_size_pt=14)],
                    bullet_level=0,
                    alignment="left",
                ),
                PptxParagraph(
                    runs=[PptxTextRun(text="항목 2", font_size_pt=14)],
                    bullet_level=0,
                    alignment="left",
                ),
            ],
        )
        html = textbox_to_html(tb)
        # bullet 본문에는 nowrap을 적용하지 않는다.
        assert "white-space:nowrap" not in html, html
