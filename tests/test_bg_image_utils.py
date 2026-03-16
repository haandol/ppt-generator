from unittest.mock import patch

import pytest

from ppt_generator.interfaces.bg_image_utils import (
    get_bg_image_base64,
    get_bg_image_bytes,
    get_bg_image_path,
    reset_cache,
)


class TestGetBgImagePath:
    def setup_method(self):
        reset_cache()

    def test_returns_path_for_dark_theme(self):
        path = get_bg_image_path("dark")
        assert path is not None
        assert path.exists()
        assert "dark" in str(path)

    def test_returns_path_for_light_theme(self):
        path = get_bg_image_path("light")
        assert path is not None
        assert path.exists()
        assert "light" in str(path)

    def test_default_is_dark(self):
        path = get_bg_image_path()
        assert path is not None
        assert "dark" in str(path)

    def test_invalid_theme_falls_back_to_dark(self):
        path = get_bg_image_path("invalid")
        assert path is not None
        assert "dark" in str(path)

    def test_cache_returns_same_path(self):
        path1 = get_bg_image_path("dark")
        path2 = get_bg_image_path("dark")
        assert path1 == path2

    def test_reset_cache_allows_new_selection(self):
        path1 = get_bg_image_path("dark")
        reset_cache()
        # 랜덤이므로 다를 수도 같을 수도 있지만, 에러 없이 동작해야 함
        path2 = get_bg_image_path("dark")
        assert path2 is not None


class TestGetBgImageBytes:
    def setup_method(self):
        reset_cache()

    def test_returns_bytes(self):
        data = get_bg_image_bytes("dark")
        assert data is not None
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_png_header(self):
        data = get_bg_image_bytes("dark")
        assert data is not None
        # PNG 매직 바이트 확인
        assert data[:4] == b"\x89PNG"


class TestGetBgImageBase64:
    def setup_method(self):
        reset_cache()

    def test_returns_base64_string(self):
        b64 = get_bg_image_base64("dark")
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
                result = get_bg_image_base64("dark")
                assert result is None
