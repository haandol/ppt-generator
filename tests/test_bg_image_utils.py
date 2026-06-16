from unittest.mock import patch

from ppt_generator.interfaces.bg_image_utils import (
    get_bg_image_base64,
    get_bg_image_bytes,
    get_bg_image_path,
    reset_cache,
    set_project_seed,
)


class TestGetBgImagePath:
    def setup_method(self):
        set_project_seed(None)
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
        get_bg_image_path("dark")
        reset_cache()
        # 랜덤이므로 다를 수도 같을 수도 있지만, 에러 없이 동작해야 함
        path2 = get_bg_image_path("dark")
        assert path2 is not None


class TestGetBgImageBytes:
    def setup_method(self):
        set_project_seed(None)
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
        set_project_seed(None)
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


class TestProjectSeedDeterminism:
    """프로젝트 단위 결정론 선택 — 같은 시드는 같은 배경, 시드 다르면 다양성."""

    def setup_method(self):
        set_project_seed(None)
        reset_cache()

    def teardown_method(self):
        set_project_seed(None)
        reset_cache()

    def test_same_seed_same_image_across_resets(self):
        # 시드 고정 시, export 사이 reset_cache 가 끼어도 같은 이미지를 골라야 한다.
        set_project_seed("project-A")
        first = get_bg_image_path("dark")
        reset_cache()  # 재export 모사
        second = get_bg_image_path("dark")
        assert first == second

    def test_title_and_closing_share_image_within_project(self):
        # 같은 프로젝트(시드) 안에서 여러 번 호출 → 동일 (타이틀/클로징 일관성).
        set_project_seed("project-A")
        a = get_bg_image_path("dark")
        b = get_bg_image_path("dark")
        assert a == b

    def test_seed_is_deterministic_not_random(self):
        # 시드를 바꿔 끼웠다 되돌려도 같은 시드는 항상 같은 결과.
        set_project_seed("project-A")
        a1 = get_bg_image_path("dark")
        set_project_seed("project-B")
        get_bg_image_path("dark")
        set_project_seed("project-A")
        a2 = get_bg_image_path("dark")
        assert a1 == a2

    def test_different_seeds_can_differ(self):
        # 여러 시드를 돌려보면 적어도 두 종류 이상의 이미지가 나와야 다양성 보장.
        seen = set()
        for i in range(20):
            set_project_seed(f"project-{i}")
            reset_cache()
            seen.add(get_bg_image_path("dark"))
        assert len(seen) >= 2

    def test_none_seed_restores_random_mode(self):
        # 시드 해제 후엔 무작위 모드(에러 없이 동작).
        set_project_seed("project-A")
        get_bg_image_path("dark")
        set_project_seed(None)
        reset_cache()
        assert get_bg_image_path("dark") is not None
