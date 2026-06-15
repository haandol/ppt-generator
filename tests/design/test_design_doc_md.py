"""DESIGN.md 파서/직렬화 및 페이지 매칭 테스트."""

from __future__ import annotations

from ppt_generator.tools.design.design_doc_md import (
    PageRequest,
    match_page_request,
    parse_design_doc_md,
    render_design_doc_md,
)

FULL_SUMMARY = {
    "color_theme": "dark",
    "background_color": "#0F172A",
    "text_colors": ["#FFFFFF", "#E0E0E0"],
    "title_font_pt": 32,
    "body_font_pt": 20,
    "card_fills": ["#1E293B"],
    "card_borders": ["#334155"],
    "header_region": {"top_px": 64, "height_px": 64},
    "content_region": {"top_px": 148, "height_px": 508},
    "footer_region": {"top_px": 664, "height_px": 24},
}


class TestRoundTrip:
    def test_summary_round_trips(self) -> None:
        md = render_design_doc_md(FULL_SUMMARY)
        doc = parse_design_doc_md(md)
        # background_image 정책은 draft 에 항상 노출되므로(기본 gradient)
        # round-trip 결과엔 그 키가 추가된다.
        assert doc.design_summary == {**FULL_SUMMARY, "background_image": "gradient"}

    def test_summary_with_explicit_bg_policy_round_trips(self) -> None:
        summary = {**FULL_SUMMARY, "background_image": "none"}
        doc = parse_design_doc_md(render_design_doc_md(summary))
        assert doc.design_summary == summary

    def test_tone_and_pages_round_trip(self) -> None:
        md = render_design_doc_md(
            FULL_SUMMARY,
            tone="차분한 기업 톤.",
            page_requests=[PageRequest(3, "아키텍처 개요", "좌우 비교 레이아웃으로.")],
        )
        doc = parse_design_doc_md(md)
        assert doc.tone == "차분한 기업 톤."
        assert len(doc.page_requests) == 1
        assert doc.page_requests[0].number == 3
        assert doc.page_requests[0].title == "아키텍처 개요"
        assert "좌우 비교" in doc.page_requests[0].text


class TestParserRobustness:
    def test_empty_returns_empty_doc(self) -> None:
        doc = parse_design_doc_md("")
        assert doc.design_summary == {}
        assert doc.tone == ""
        assert doc.page_requests == []

    def test_unknown_keys_and_sections_ignored(self) -> None:
        md = (
            "# DESIGN\n\n"
            "## 전역 디자인 시스템\n"
            "- background_color: #000000\n"
            "- bogus_key: whatever\n"
            "- title_font_pt: 30\n\n"
            "## 알수없는 섹션\n"
            "- noise: 123\n"
        )
        doc = parse_design_doc_md(md)
        assert doc.design_summary == {
            "background_color": "#000000",
            "title_font_pt": 30,
        }

    def test_korean_and_english_section_aliases(self) -> None:
        md = (
            "## Design System\n- theme: light\n\n"
            "## Tone & Direction\n자유 산문.\n\n"
            "## Per-slide Requests\n### 2. Intro\n특별 요청.\n"
        )
        doc = parse_design_doc_md(md)
        assert doc.design_summary == {"color_theme": "light"}
        assert doc.tone == "자유 산문."
        assert doc.page_requests[0].number == 2

    def test_garbage_int_value_is_skipped(self) -> None:
        md = "## 전역 디자인 시스템\n- title_font_pt: not-a-number\n"
        doc = parse_design_doc_md(md)
        # 숫자 없는 값 → 무시 (파서가 죽지 않음)
        assert "title_font_pt" not in doc.design_summary


class TestPageMatching:
    REQS = [PageRequest(3, "아키텍처 개요", "좌우 비교.")]

    def test_match_by_number(self) -> None:
        r = match_page_request(self.REQS, 3, "전혀 다른 제목")
        assert r is not None and r.number == 3

    def test_match_by_title_when_number_shifted(self) -> None:
        # 번호가 밀렸지만 제목으로 보정 매칭
        r = match_page_request(self.REQS, 5, "아키텍처 개요")
        assert r is not None and r.title == "아키텍처 개요"

    def test_title_match_ignores_whitespace_punctuation(self) -> None:
        r = match_page_request(self.REQS, 9, "  아키텍처  개요!! ")
        assert r is not None

    def test_no_match_returns_none(self) -> None:
        assert match_page_request(self.REQS, 9, "다른 슬라이드") is None


class TestDirectives:
    def test_directives_include_tone_and_request(self) -> None:
        doc = parse_design_doc_md(
            render_design_doc_md(
                FULL_SUMMARY,
                tone="기업 톤.",
                page_requests=[PageRequest(2, "본론", "다이어그램 강조.")],
            )
        )
        out = doc.directives_for(2, "본론")
        assert "기업 톤." in out
        assert "다이어그램 강조." in out

    def test_directives_tone_only_for_unmatched_slide(self) -> None:
        doc = parse_design_doc_md(
            render_design_doc_md(
                FULL_SUMMARY,
                tone="기업 톤.",
                page_requests=[PageRequest(2, "본론", "다이어그램 강조.")],
            )
        )
        out = doc.directives_for(1, "표지")
        assert "기업 톤." in out
        assert "다이어그램 강조." not in out

    def test_directives_empty_when_no_intent(self) -> None:
        doc = parse_design_doc_md(render_design_doc_md(FULL_SUMMARY))
        assert doc.directives_for(1, "표지") == ""
