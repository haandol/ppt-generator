"""text_measurement 모듈 단위 테스트."""

from __future__ import annotations

import pytest

from ppt_generator.interfaces.schemas import PptxParagraph, PptxTextRun
from ppt_generator.interfaces.text_measurement import (
    _is_wide_char,
    calculate_autofit_font_scale,
    calculate_required_height,
    calculate_required_height_simple_text,
    estimate_paragraph_wrapped_lines,
    estimate_text_width_px,
)


# ---------------------------------------------------------------------------
# _is_wide_char
# ---------------------------------------------------------------------------


class TestIsWideChar:
    def test_korean(self) -> None:
        assert _is_wide_char("가") is True
        assert _is_wide_char("한") is True

    def test_cjk(self) -> None:
        assert _is_wide_char("漢") is True
        assert _is_wide_char("あ") is True

    def test_latin(self) -> None:
        assert _is_wide_char("A") is False
        assert _is_wide_char("z") is False

    def test_digit(self) -> None:
        assert _is_wide_char("0") is False
        assert _is_wide_char("9") is False

    def test_space(self) -> None:
        assert _is_wide_char(" ") is False


# ---------------------------------------------------------------------------
# estimate_text_width_px
# ---------------------------------------------------------------------------


class TestEstimateTextWidthPx:
    def test_pure_korean(self) -> None:
        # 한글 5자, 18pt
        width = estimate_text_width_px("안녕하세요", 18)
        # 5 × 18 × 1.333 × 0.9 = 107.946
        assert width == pytest.approx(5 * 18 * 1.333 * 0.9, rel=1e-3)

    def test_pure_latin(self) -> None:
        # Latin 5자, 18pt
        width = estimate_text_width_px("Hello", 18)
        # 5 × 18 × 1.333 × 0.55 = 65.967
        assert width == pytest.approx(5 * 18 * 1.333 * 0.55, rel=1e-3)

    def test_mixed(self) -> None:
        # "AB가나" = Latin 2 + Korean 2
        width = estimate_text_width_px("AB가나", 20)
        latin_w = 2 * 20 * 1.333 * 0.55
        cjk_w = 2 * 20 * 1.333 * 0.9
        assert width == pytest.approx(latin_w + cjk_w, rel=1e-3)

    def test_monospace(self) -> None:
        # monospace에서는 모든 글자 동일 비율
        width = estimate_text_width_px("AB가나", 20, is_monospace=True)
        expected = 4 * 20 * 1.333 * 0.6
        assert width == pytest.approx(expected, rel=1e-3)

    def test_empty_string(self) -> None:
        assert estimate_text_width_px("", 18) == 0.0


# ---------------------------------------------------------------------------
# estimate_paragraph_wrapped_lines
# ---------------------------------------------------------------------------


class TestEstimateParagraphWrappedLines:
    def test_single_line(self) -> None:
        para = PptxParagraph(
            runs=[PptxTextRun(text="Hello", font_size_pt=18)],
        )
        # 매우 넓은 박스 → 1줄
        assert estimate_paragraph_wrapped_lines(para, 1000) == 1

    def test_multiple_lines(self) -> None:
        # 한글 20자, 18pt, box 200px → 여러 줄
        text = "가" * 20
        para = PptxParagraph(
            runs=[PptxTextRun(text=text, font_size_pt=18)],
        )
        total_w = estimate_text_width_px(text, 18)
        expected_lines = -(-int(total_w) // 200)  # ceil division
        result = estimate_paragraph_wrapped_lines(para, 200)
        assert result >= 2
        assert result == expected_lines

    def test_narrow_box(self) -> None:
        para = PptxParagraph(
            runs=[PptxTextRun(text="한글테스트", font_size_pt=20)],
        )
        # 아주 좁은 박스 → 많은 줄
        result = estimate_paragraph_wrapped_lines(para, 30)
        assert result >= 3

    def test_empty_runs(self) -> None:
        para = PptxParagraph(runs=[PptxTextRun(text="")])
        assert estimate_paragraph_wrapped_lines(para, 500) == 1


# ---------------------------------------------------------------------------
# calculate_required_height
# ---------------------------------------------------------------------------


class TestCalculateRequiredHeight:
    def test_single_paragraph(self) -> None:
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text="짧은 텍스트", font_size_pt=18)],
            ),
        ]
        h = calculate_required_height(paras, 500)
        assert h > 0
        # 한 줄 × 18 × 2.0 = 36
        assert h == pytest.approx(1 * 18 * 2.0, rel=0.1)

    def test_multiple_paragraphs(self) -> None:
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text="첫 번째", font_size_pt=18)],
            ),
            PptxParagraph(
                runs=[PptxTextRun(text="두 번째", font_size_pt=18)],
            ),
        ]
        h = calculate_required_height(paras, 500)
        # 2줄 × 18 × 2.0 = 72
        assert h == pytest.approx(2 * 18 * 2.0, rel=0.1)

    def test_bullet_indent(self) -> None:
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text="가" * 30, font_size_pt=18)],
                bullet_level=1,  # L1 indent = 48px
            ),
        ]
        # indent가 있으면 available_width가 줄어 줄수가 늘어남
        h_with_indent = calculate_required_height(paras, 300)
        paras_no_indent = [
            PptxParagraph(
                runs=[PptxTextRun(text="가" * 30, font_size_pt=18)],
                bullet_level=-1,
            ),
        ]
        h_no_indent = calculate_required_height(paras_no_indent, 300)
        assert h_with_indent >= h_no_indent

    def test_with_padding(self) -> None:
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text="가" * 20, font_size_pt=18)],
            ),
        ]
        h_no_pad = calculate_required_height(paras, 500)
        h_with_pad = calculate_required_height(
            paras, 500,
            padding_top_px=10, padding_bottom_px=10,
            padding_left_px=50, padding_right_px=50,
        )
        assert h_with_pad > h_no_pad

    def test_with_line_spacing(self) -> None:
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text="짧은", font_size_pt=18)],
            ),
            PptxParagraph(
                runs=[PptxTextRun(text="텍스트", font_size_pt=18)],
            ),
        ]
        h_default = calculate_required_height(paras, 500)
        h_custom = calculate_required_height(paras, 500, line_spacing_pt=28)
        # line_spacing_pt=28 → 28 * 1.333 ≈ 37.3px per line
        # default: 18 * 2.0 = 36px per line
        assert h_custom > h_default

    def test_empty_paragraphs(self) -> None:
        assert calculate_required_height([], 500) == 0.0


# ---------------------------------------------------------------------------
# calculate_required_height_simple_text
# ---------------------------------------------------------------------------


class TestCalculateRequiredHeightSimpleText:
    def test_single_line(self) -> None:
        h = calculate_required_height_simple_text("Hello", 18, 500)
        assert h > 0

    def test_multiline(self) -> None:
        h = calculate_required_height_simple_text("Line1\nLine2\nLine3", 18, 500)
        # 3줄 기대
        assert h > calculate_required_height_simple_text("Line1", 18, 500)

    def test_wrapping(self) -> None:
        # 매우 좁은 박스에서 긴 텍스트
        h = calculate_required_height_simple_text("가" * 30, 18, 100)
        h_wide = calculate_required_height_simple_text("가" * 30, 18, 1000)
        assert h > h_wide


# ---------------------------------------------------------------------------
# calculate_autofit_font_scale
# ---------------------------------------------------------------------------


class TestCalculateAutofitFontScale:
    def test_no_shrink_needed(self) -> None:
        scale = calculate_autofit_font_scale(100, 200)
        assert scale == 1.0

    def test_moderate_shrink(self) -> None:
        scale = calculate_autofit_font_scale(200, 100, min_font_pt=10, max_font_pt=20)
        assert scale == pytest.approx(0.5, rel=1e-3)

    def test_min_font_limit(self) -> None:
        # 필요 축소: 1000→100 = 0.1, 하지만 min_font/max_font = 10/20 = 0.5가 하한
        scale = calculate_autofit_font_scale(1000, 100, min_font_pt=10, max_font_pt=20)
        assert scale == pytest.approx(0.5, rel=1e-3)

    def test_exact_fit(self) -> None:
        scale = calculate_autofit_font_scale(100, 100)
        assert scale == 1.0

    def test_zero_values(self) -> None:
        assert calculate_autofit_font_scale(0, 100) == 1.0
        assert calculate_autofit_font_scale(100, 0) == 1.0
