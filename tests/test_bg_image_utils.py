from unittest.mock import patch

import pytest

from ppt_generator.interfaces.bg_image_utils import (
    get_bg_image_base64,
    get_bg_image_bytes,
    get_bg_image_path,
    is_dark_background,
    reset_cache,
)


class TestIsDarkBackground:
    def test_none_returns_dark(self):
        assert is_dark_background(None) is True

    def test_empty_string_returns_dark(self):
        assert is_dark_background("") is True

    def test_black_is_dark(self):
        assert is_dark_background("#000000") is True

    def test_white_is_light(self):
        assert is_dark_background("#ffffff") is False

    def test_dark_blue_is_dark(self):
        assert is_dark_background("#1a1a2e") is True

    def test_light_gray_is_light(self):
        assert is_dark_background("#cccccc") is False

    def test_short_hex(self):
        assert is_dark_background("#fff") is False
        assert is_dark_background("#000") is True

    def test_invalid_hex_returns_dark(self):
        assert is_dark_background("#xyz") is True
        assert is_dark_background("not-a-color") is True

    def test_no_hash_prefix(self):
        # 6자리 hex이지만 # 없는 경우
        assert is_dark_background("ffffff") is False

    def test_mid_brightness(self):
        # #808080 (중간 밝기) - sRGB 선형화 후 luminance ~0.22 → dark
        assert is_dark_background("#808080") is True


class TestGetBgImagePath:
    def setup_method(self):
        reset_cache()

    def test_returns_path_for_dark_theme(self):
        path = get_bg_image_path("#1a1a2e")
        assert path is not None
        assert path.exists()
        assert "dark" in str(path)

    def test_returns_path_for_light_theme(self):
        path = get_bg_image_path("#ffffff")
        assert path is not None
        assert path.exists()
        assert "light" in str(path)

    def test_cache_returns_same_path(self):
        path1 = get_bg_image_path("#1a1a2e")
        path2 = get_bg_image_path("#1a1a2e")
        assert path1 == path2

    def test_cache_consistency_across_colors_same_theme(self):
        """같은 테마(dark)의 다른 색상에서도 동일 이미지 반환."""
        path1 = get_bg_image_path("#000000")
        path2 = get_bg_image_path("#1a1a2e")
        assert path1 == path2

    def test_reset_cache_allows_new_selection(self):
        path1 = get_bg_image_path("#1a1a2e")
        reset_cache()
        # 랜덤이므로 다를 수도 같을 수도 있지만, 에러 없이 동작해야 함
        path2 = get_bg_image_path("#1a1a2e")
        assert path2 is not None


class TestGetBgImageBytes:
    def setup_method(self):
        reset_cache()

    def test_returns_bytes(self):
        data = get_bg_image_bytes("#1a1a2e")
        assert data is not None
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_png_header(self):
        data = get_bg_image_bytes("#1a1a2e")
        assert data is not None
        # PNG 매직 바이트 확인
        assert data[:4] == b"\x89PNG"


class TestGetBgImageBase64:
    def setup_method(self):
        reset_cache()

    def test_returns_base64_string(self):
        b64 = get_bg_image_base64("#1a1a2e")
        assert b64 is not None
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_returns_none_for_missing_dir(self):
        with patch(
            "ppt_generator.interfaces.bg_image_utils.TEMPLATE_BG_IMAGES_DIR",
            get_bg_image_path.__module__,
        ):
            reset_cache()
            from pathlib import Path
            with patch(
                "ppt_generator.interfaces.bg_image_utils.TEMPLATE_BG_IMAGES_DIR",
                Path("/nonexistent/path"),
            ):
                reset_cache()
                result = get_bg_image_base64("#1a1a2e")
                assert result is None
