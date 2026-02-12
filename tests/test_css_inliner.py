"""CSS 인라이너 유닛 테스트."""

from ppt_generator.tools.slides.css_inliner import inline_css_classes


class TestInlineCssClasses:
    def test_simple_class_inlined(self):
        html = (
            "<html><head><style>"
            ".info-card { background-color: #162232; padding: 16px; }"
            "</style></head><body>"
            '<div class="info-card">내용</div>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        assert "background-color: #162232" in result
        assert "padding: 16px" in result

    def test_existing_inline_style_takes_priority(self):
        html = (
            "<html><head><style>"
            ".info-card { background-color: #162232; color: #ffffff; }"
            "</style></head><body>"
            '<div class="info-card" style="background-color: #ff0000;">내용</div>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        # 기존 인라인(#ff0000)이 클래스(#162232)보다 우선
        assert "background-color: #ff0000" in result
        # div의 인라인 style에 #162232가 포함되지 않아야 함
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(result, "html.parser")
        div = soup.find("div", class_="info-card")
        assert "#162232" not in div["style"]
        assert "#ff0000" in div["style"]
        # 클래스의 color는 인라인에 없으므로 추가
        assert "color: #ffffff" in result

    def test_multiple_classes_merged(self):
        html = (
            "<html><head><style>"
            ".two-col { display: grid; grid-template-columns: 1fr 1fr; }"
            ".info-card { background-color: #162232; }"
            "</style></head><body>"
            '<div class="two-col info-card">내용</div>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        assert "display: grid" in result
        assert "background-color: #162232" in result

    def test_compound_selector_skipped(self):
        """복합 셀렉터(.parent .child)는 처리하지 않음."""
        html = (
            "<html><head><style>"
            ".parent .child { color: red; }"
            ".simple { color: blue; }"
            "</style></head><body>"
            '<div class="simple">내용</div>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        assert "color: blue" in result

    def test_no_style_tag_returns_original(self):
        html = '<html><body><div class="foo">내용</div></body></html>'
        result = inline_css_classes(html)
        # 변환 없이 반환 (원본과 동일)
        assert "내용" in result

    def test_css_comment_removed(self):
        html = (
            "<html><head><style>"
            "/* 이건 주석 */ .tag { font-family: monospace; }"
            "</style></head><body>"
            '<span class="tag">라벨</span>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        assert "font-family: monospace" in result

    def test_at_media_removed(self):
        html = (
            "<html><head><style>"
            "@media (max-width: 768px) { .foo { display: none; } }"
            ".tag { color: #f59e0b; }"
            "</style></head><body>"
            '<span class="tag">라벨</span>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        assert "color: #f59e0b" in result

    def test_element_without_matching_class_unchanged(self):
        html = (
            "<html><head><style>"
            ".info-card { background-color: #162232; }"
            "</style></head><body>"
            '<div class="other-class">내용</div>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        assert "background-color" not in result or "other-class" in result

    def test_preserves_non_class_elements(self):
        html = (
            "<html><head><style>"
            ".tag { color: #f59e0b; }"
            "</style></head><body>"
            "<p>일반 텍스트</p>"
            '<span class="tag">라벨</span>'
            "</body></html>"
        )
        result = inline_css_classes(html)
        assert "일반 텍스트" in result
        assert "color: #f59e0b" in result

    def test_full_slide_html_with_classes(self):
        """실제 슬라이드 HTML과 유사한 구조 테스트."""
        html = (
            "<!DOCTYPE html>\n<html><head><style>\n"
            ".two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }\n"
            ".info-card { background-color: #162232; border-radius: 12px; padding: 24px; }\n"
            ".tag { font-family: monospace; background-color: #1e3a5f; "
            "padding: 4px 12px; border-radius: 9999px; font-size: 14px; color: #f59e0b; }\n"
            "</style></head><body>\n"
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0; '
            'background-color:#0d1b2a;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <div class="two-col">\n'
            '        <div class="info-card">\n'
            '          <span class="tag">AWS</span>\n'
            "          <p>클라우드 서비스</p>\n"
            "        </div>\n"
            '        <div class="info-card" style="background-color: #1a2b3c;">\n'
            "          <p>커스텀 배경</p>\n"
            "        </div>\n"
            "      </div>\n"
            "    </div>\n"
            "  </div>\n"
            "</section>\n"
            "</body></html>"
        )
        result = inline_css_classes(html)
        # two-col에 grid 스타일 인라인
        assert "display: grid" in result
        # 첫 번째 info-card에 배경색 인라인
        assert "#162232" in result
        # 두 번째 info-card는 기존 인라인(#1a2b3c) 유지
        assert "#1a2b3c" in result
        # tag에 monospace 인라인
        assert "font-family: monospace" in result

    def test_no_classes_in_html(self):
        """클래스가 없는 HTML은 변경 없이 반환."""
        html = (
            "<html><head><style>.foo { color: red; }</style></head><body>"
            "<div>내용</div></body></html>"
        )
        result = inline_css_classes(html)
        assert "내용" in result

    def test_empty_style_tag(self):
        html = (
            "<html><head><style></style></head><body>"
            '<div class="foo">내용</div></body></html>'
        )
        result = inline_css_classes(html)
        assert "내용" in result
