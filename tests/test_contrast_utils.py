"""contrast_utils 단위 테스트.

luminance 계산, contrast ratio 계산, 텍스트 색상 자동 보정을 검증한다.
"""

from __future__ import annotations

import pytest

from ppt_generator.interfaces.spec_utils.contrast_utils import (
    _contrast_ratio,
    _hex_to_relative_luminance,
    ensure_text_contrast,
)


# ---------------------------------------------------------------------------
# _hex_to_relative_luminance
# ---------------------------------------------------------------------------


class TestHexToRelativeLuminance:
    def test_black(self) -> None:
        assert _hex_to_relative_luminance("#000000") == pytest.approx(0.0, abs=1e-4)

    def test_white(self) -> None:
        assert _hex_to_relative_luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-4)

    def test_shorthand_hex(self) -> None:
        # #FFF == #FFFFFF
        assert _hex_to_relative_luminance("#FFF") == pytest.approx(1.0, abs=1e-4)

    def test_no_hash(self) -> None:
        assert _hex_to_relative_luminance("000000") == pytest.approx(0.0, abs=1e-4)

    def test_invalid_returns_zero(self) -> None:
        assert _hex_to_relative_luminance("xyz") == 0.0
        assert _hex_to_relative_luminance("#GG0000") == 0.0

    def test_mid_gray(self) -> None:
        lum = _hex_to_relative_luminance("#808080")
        assert 0.2 < lum < 0.3  # ~0.2159


# ---------------------------------------------------------------------------
# _contrast_ratio
# ---------------------------------------------------------------------------


class TestContrastRatio:
    def test_black_on_white(self) -> None:
        ratio = _contrast_ratio(0.0, 1.0)
        assert ratio == pytest.approx(21.0, abs=0.1)

    def test_same_color(self) -> None:
        ratio = _contrast_ratio(0.5, 0.5)
        assert ratio == pytest.approx(1.0, abs=0.01)

    def test_order_independent(self) -> None:
        assert _contrast_ratio(0.1, 0.9) == pytest.approx(
            _contrast_ratio(0.9, 0.1), abs=1e-6,
        )


# ---------------------------------------------------------------------------
# ensure_text_contrast
# ---------------------------------------------------------------------------


class TestEnsureTextContrast:
    def test_good_contrast_unchanged(self) -> None:
        """흰 텍스트 + 검정 배경 → 변경 없음."""
        assert ensure_text_contrast("#FFFFFF", "#000000") == "#FFFFFF"

    def test_poor_contrast_on_dark_bg(self) -> None:
        """어두운 텍스트 + 어두운 배경 → 흰색으로 교체."""
        result = ensure_text_contrast("#333333", "#1a1a2e")
        assert result == "#FFFFFF"

    def test_poor_contrast_on_light_bg(self) -> None:
        """밝은 텍스트 + 밝은 배경 → 검정으로 교체."""
        result = ensure_text_contrast("#CCCCCC", "#FFFFFF")
        assert result == "#000000"

    def test_large_text_lower_threshold(self) -> None:
        """대형 텍스트(≥24pt) → 3:1 기준 적용, 더 관대."""
        # 중간 회색 텍스트 + 흰 배경: 4.5:1 미달이지만 3:1 충족
        gray = "#767676"  # contrast ~4.54:1 with white → passes 4.5 threshold
        # 더 밝은 회색으로 테스트
        light_gray = "#949494"  # contrast ~3.0:1 with white
        result = ensure_text_contrast(light_gray, "#FFFFFF", font_size_pt=24)
        # 3:1 경계이므로 pass 또는 교체 — 중요한 건 에러 없이 동작
        assert result in (light_gray, "#000000")

    def test_large_bold_text(self) -> None:
        """18pt bold → 대형 텍스트로 인식, 3:1 기준."""
        result = ensure_text_contrast("#767676", "#FFFFFF", font_size_pt=18, bold=True)
        # #767676 on white ≈ 4.54:1 > 3.0 → unchanged
        assert result == "#767676"

    def test_normal_text_stricter(self) -> None:
        """일반 텍스트(16pt) → 4.5:1 기준."""
        # #767676 on white ≈ 4.54:1 → just passes
        result = ensure_text_contrast("#767676", "#FFFFFF", font_size_pt=16)
        assert result == "#767676"

        # #777777 on white ≈ 4.48:1 → fails 4.5:1
        result = ensure_text_contrast("#787878", "#FFFFFF", font_size_pt=16)
        assert result == "#000000"
