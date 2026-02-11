from ppt_generator.templates.layout_mapping import (
    DEFAULT_LAYOUT_INDEX,
    LAYOUT_MAP,
    LayoutInfo,
    get_layout_info,
)


class TestLayoutMapping:
    def test_all_layout_indices_defined(self):
        # 템플릿 97종 중 Do Not Use(95) 제외한 96종 등록
        assert len(LAYOUT_MAP) == 96
        assert 95 not in LAYOUT_MAP  # Do Not Use 레이아웃 제외

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
        assert info.layout_name == "1_Thank You Option 1 Alt"
        assert info.body_ph == 10
        assert info.picture_ph == 14

    def test_get_layout_info_blank(self):
        info = get_layout_info(20)
        assert info.layout_name == "Blank"
        assert info.title_ph is None
        assert info.body_ph is None

    def test_layout_info_has_theme(self):
        assert get_layout_info(0).theme == "light"
        assert get_layout_info(28).theme == "dark"
        assert get_layout_info(96).theme == "dark"
        assert get_layout_info(22).theme == "light"

    def test_layout_info_is_frozen(self):
        info = get_layout_info(0)
        try:
            info.layout_index = 999
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass
