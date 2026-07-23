"""text_measurement 모듈 단위 테스트."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ppt_generator.interfaces.constants import TEXT_MEASURE_PX_PER_PT
from ppt_generator.interfaces.schemas import PptxParagraph, PptxTextRun
from ppt_generator.interfaces.text_measurement import (
    _is_wide_char,
    calculate_autofit_font_scale,
    calculate_required_height,
    calculate_required_height_simple_text,
    calculate_shrink_font_scale,
    estimate_paragraph_wrapped_lines,
    estimate_text_width_px,
    scaled_line_spacing_pt,
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
            paras,
            500,
            padding_top_px=10,
            padding_bottom_px=10,
            padding_left_px=50,
            padding_right_px=50,
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

    def test_paragraph_spacing_uses_max_at_adjacent_boundaries(self) -> None:
        paragraphs = [
            PptxParagraph(
                runs=[PptxTextRun(text=f"line {index}", font_size_pt=12)],
                space_before_pt=3,
                space_after_pt=3,
            )
            for index in range(3)
        ]

        result = calculate_required_height(
            paragraphs,
            1000,
            line_spacing_pt=12,
        )

        expected = (3 * 12 + 4 * 3) * TEXT_MEASURE_PX_PER_PT
        assert result == pytest.approx(expected)

    def test_explicit_bullet_margin_controls_available_width(self) -> None:
        paragraph = PptxParagraph(
            runs=[PptxTextRun(text="abcdefgh", font_size_pt=10)],
            bullet_level=0,
            margin_left_px=10,
            indent_px=-10,
        )
        default_indent = replace(
            paragraph,
            margin_left_px=None,
            indent_px=None,
        )

        explicit_height = calculate_required_height([paragraph], 70)
        default_height = calculate_required_height([default_indent], 70)

        assert explicit_height < default_height


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


class TestScaledLineSpacing:
    def test_none_passthrough(self) -> None:
        assert scaled_line_spacing_pt(None, 0.5) is None

    def test_zero_passthrough(self) -> None:
        assert scaled_line_spacing_pt(0, 0.5) == 0

    def test_no_scale_when_full(self) -> None:
        # scale == 1.0 이면 축소하지 않는다
        assert scaled_line_spacing_pt(22.0, 1.0) == 22.0

    def test_no_scale_when_gt_one(self) -> None:
        # 비정상적으로 1 초과여도 원본 유지
        assert scaled_line_spacing_pt(22.0, 1.5) == 22.0

    def test_scales_down(self) -> None:
        assert scaled_line_spacing_pt(22.0, 0.8) == pytest.approx(17.6, rel=1e-3)


class TestShrinkConvergesWithLineSpacing:
    """다행 텍스트 + 명시적 line_spacing 에서 shrink 가 실제로 오버플로를 해소하는지.

    line_spacing 을 상수로 두면 폰트만 줄고 줄 높이는 그대로라 축소 후에도
    소비 높이가 박스를 넘던 회귀(design/0014, 2026-07-21)에 대한 가드.
    """

    def _many_lines(self, n: int, font_pt: int = 15) -> list[PptxParagraph]:
        return [
            PptxParagraph(
                runs=[PptxTextRun(text="x = foo(bar)", font_size_pt=font_pt)],
                bullet_level=-1,
            )
            for _ in range(n)
        ]

    def test_shrink_then_scaled_spacing_fits_box(self) -> None:
        paras = self._many_lines(19)
        w, h, ls = 960.0, 428.0, 22.0
        pad_lr, pad_tb = 32.0, 26.0

        scale = calculate_shrink_font_scale(
            paras,
            w,
            h,
            line_spacing_pt=ls,
            padding_left_px=pad_lr,
            padding_right_px=pad_lr,
            padding_top_px=pad_tb,
            padding_bottom_px=pad_tb,
        )
        assert scale < 1.0  # 축소가 필요한 케이스

        eff_ls = scaled_line_spacing_pt(ls, scale)
        consumed = calculate_required_height(
            paras,
            w,
            line_spacing_pt=eff_ls,
            padding_left_px=pad_lr,
            padding_right_px=pad_lr,
            padding_top_px=pad_tb,
            padding_bottom_px=pad_tb,
        )
        # 축소된 line_spacing 으로 다시 재면 박스 높이(+15% 여유) 안에 든다.
        assert consumed <= h * 1.15 + 0.5

    def test_padding_excluded_from_scale_ratio(self) -> None:
        # 상하 padding 이 큰 케이스에서도 텍스트분만 축소해 수렴하는지
        # (폰트 하한 10pt 에 걸리지 않는 범위). padding 을 비율에 포함하면
        # 축소 후에도 미세하게 넘치므로, 텍스트분만 축소하는지를 검증한다.
        paras = self._many_lines(9, font_pt=16)
        w, h, ls = 600.0, 260.0, 24.0
        pad_tb = 40.0

        scale = calculate_shrink_font_scale(
            paras,
            w,
            h,
            line_spacing_pt=ls,
            padding_top_px=pad_tb,
            padding_bottom_px=pad_tb,
        )
        assert scale < 1.0
        assert scale > 10.0 / 16.0  # 폰트 하한에 걸리지 않는 케이스
        eff_ls = scaled_line_spacing_pt(ls, scale)
        consumed = calculate_required_height(
            paras,
            w,
            line_spacing_pt=eff_ls,
            padding_top_px=pad_tb,
            padding_bottom_px=pad_tb,
        )
        assert consumed <= h * 1.15 + 0.5
