from ppt_generator.templates.layout_mapping import (
    DEFAULT_LAYOUT_TYPE,
    LAYOUT_MAP,
    LayoutInfo,
    find_blank_layout_index,
    get_layout_info,
)


class TestLayoutMapping:
    def test_all_layout_types_defined(self):
        expected_types = {"title", "text_image", "text_only", "chart", "closing", "freeform"}
        assert set(LAYOUT_MAP.keys()) == expected_types

    def test_get_layout_info_title(self):
        info = get_layout_info("title")
        assert info.layout_index == 0
        assert info.title_ph == 0
        assert info.subtitle_ph == 1

    def test_get_layout_info_text_image(self):
        info = get_layout_info("text_image")
        assert info.title_ph == 0
        assert info.body_ph == 1
        assert info.picture_ph == 14

    def test_get_layout_info_text_only(self):
        info = get_layout_info("text_only")
        assert info.title_ph == 0
        assert info.body_ph == 1
        assert info.picture_ph is None

    def test_get_layout_info_chart(self):
        info = get_layout_info("chart")
        assert info.title_ph == 0
        assert info.body_ph == 1

    def test_get_layout_info_closing(self):
        info = get_layout_info("closing")
        assert isinstance(info, LayoutInfo)

    def test_unknown_layout_type_falls_back_to_text_only(self):
        info = get_layout_info("nonexistent")
        expected = LAYOUT_MAP[DEFAULT_LAYOUT_TYPE]
        assert info == expected

    def test_empty_layout_type_falls_back(self):
        info = get_layout_info("")
        expected = LAYOUT_MAP[DEFAULT_LAYOUT_TYPE]
        assert info == expected

    def test_get_layout_info_freeform(self):
        info = get_layout_info("freeform")
        assert info.layout_name == "Blank"
        assert info.title_ph is None
        assert info.body_ph is None
        assert info.picture_ph is None

    def test_layout_info_is_frozen(self):
        info = get_layout_info("title")
        try:
            info.layout_index = 999
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestFindBlankLayoutIndex:
    def test_find_blank_returns_default_for_basic_presentation(self):
        from pptx import Presentation

        prs = Presentation()
        idx = find_blank_layout_index(prs)
        # 기본 프레젠테이션에서 blank 레이아웃을 찾거나, 기본값 반환
        assert isinstance(idx, int)
