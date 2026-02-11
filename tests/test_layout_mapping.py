from ppt_generator.templates.layout_mapping import (
    DEFAULT_LAYOUT_INDEX,
    LAYOUT_MAP,
    LayoutInfo,
    find_blank_layout_index,
    get_layout_info,
)


class TestLayoutMapping:
    def test_all_layout_indices_defined(self):
        expected_indices = {0, 22, 28, 21, 87, 88}
        assert set(LAYOUT_MAP.keys()) == expected_indices

    def test_get_layout_info_title(self):
        info = get_layout_info(0)
        assert info.layout_index == 0
        assert info.title_ph == 0
        assert info.subtitle_ph == 1

    def test_get_layout_info_text_image(self):
        info = get_layout_info(28)
        assert info.title_ph == 0
        assert info.body_ph == 1
        assert info.picture_ph == 14

    def test_get_layout_info_text_only(self):
        info = get_layout_info(22)
        assert info.title_ph == 0
        assert info.body_ph == 1
        assert info.picture_ph is None

    def test_get_layout_info_chart(self):
        info = get_layout_info(21)
        assert info.title_ph == 0
        assert info.body_ph == 1

    def test_get_layout_info_closing(self):
        info = get_layout_info(87)
        assert isinstance(info, LayoutInfo)

    def test_unknown_layout_index_falls_back_to_text_only(self):
        info = get_layout_info(999)
        expected = LAYOUT_MAP[DEFAULT_LAYOUT_INDEX]
        assert info == expected

    def test_get_layout_info_freeform(self):
        info = get_layout_info(88)
        assert info.layout_name == "Blank"
        assert info.title_ph is None
        assert info.body_ph is None
        assert info.picture_ph is None

    def test_layout_info_is_frozen(self):
        info = get_layout_info(0)
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
