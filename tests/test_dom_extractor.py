"""DOM 추출 모듈 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.tools.pptx.dom_extractor import (
    JS_EXTRACT_SCRIPT,
    _deduplicate_overlapping,
    _parse_extracted_data,
    _rects_overlap,
    extract_all_slides_via_dom,
)


def _import_playwright_available() -> bool:
    """Playwright가 설치되어 있는지 확인."""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


# --- _parse_extracted_data 단위 테스트 ---


class TestParseExtractedData:
    """JS 추출 결과 JSON → PptxSlideSpec 변환 테스트."""

    def test_simple_slide_with_title_and_body(self):
        """제목+본문 슬라이드가 올바르게 변환되는지 테스트."""
        data = {
            "background_color": "#0f172a",
            "textboxes": [
                {
                    "left_px": 64, "top_px": 50, "width_px": 1152, "height_px": 60,
                    "paragraphs": [{
                        "runs": [{"text": "제목 텍스트", "font_size_pt": 30, "color": "#ffffff", "bold": True, "italic": False}],
                        "bullet_level": -1,
                    }],
                },
                {
                    "left_px": 64, "top_px": 130, "width_px": 1152, "height_px": 400,
                    "paragraphs": [{
                        "runs": [{"text": "본문 내용", "font_size_pt": 16, "color": "#cccccc", "bold": False, "italic": False}],
                        "bullet_level": -1,
                    }],
                },
            ],
            "shapes": [],
        }

        spec = _parse_extracted_data(data)

        assert spec.background_color == "#0f172a"
        assert len(spec.textboxes) == 2
        assert len(spec.shapes) == 0

        title_tb = spec.textboxes[0]
        assert title_tb.left_px == 64
        assert title_tb.top_px == 50
        assert title_tb.paragraphs[0].runs[0].text == "제목 텍스트"
        assert title_tb.paragraphs[0].runs[0].font_size_pt == 30
        assert title_tb.paragraphs[0].runs[0].bold is True

    def test_card_layout_creates_shape(self):
        """카드(info-card)가 Shape으로 변환되는지 테스트."""
        data = {
            "background_color": "#0d1b2a",
            "textboxes": [
                {
                    "left_px": 80, "top_px": 200, "width_px": 500, "height_px": 300,
                    "paragraphs": [{
                        "runs": [{"text": "카드 내용", "font_size_pt": 16, "color": "#ffffff", "bold": False, "italic": False}],
                        "bullet_level": -1,
                    }],
                },
            ],
            "shapes": [
                {
                    "left_px": 64, "top_px": 180, "width_px": 540, "height_px": 340,
                    "shape_type": "rounded_rectangle",
                    "fill_color": "#162232",
                    "border_color": None,
                    "border_width_pt": None,
                    "corner_radius_px": 12,
                    "text": None,
                    "text_color": None,
                    "text_size_pt": None,
                    "text_bold": False,
                },
            ],
        }

        spec = _parse_extracted_data(data)

        assert len(spec.shapes) == 1
        assert spec.shapes[0].shape_type == "rounded_rectangle"
        assert spec.shapes[0].fill_color == "#162232"
        assert spec.shapes[0].corner_radius_px == 12

    def test_bullet_list_with_levels(self):
        """ul/li가 bullet_level로 변환되는지 테스트."""
        data = {
            "background_color": None,
            "textboxes": [
                {
                    "left_px": 64, "top_px": 150, "width_px": 1100, "height_px": 400,
                    "paragraphs": [
                        {
                            "runs": [{"text": "항목 1", "font_size_pt": 16, "color": "#ffffff", "bold": False, "italic": False}],
                            "bullet_level": 0,
                        },
                        {
                            "runs": [{"text": "항목 2", "font_size_pt": 16, "color": "#ffffff", "bold": False, "italic": False}],
                            "bullet_level": 0,
                        },
                        {
                            "runs": [{"text": "하위 항목", "font_size_pt": 14, "color": "#cccccc", "bold": False, "italic": False}],
                            "bullet_level": 1,
                        },
                    ],
                },
            ],
            "shapes": [],
        }

        spec = _parse_extracted_data(data)

        assert len(spec.textboxes) == 1
        paras = spec.textboxes[0].paragraphs
        assert len(paras) == 3
        assert paras[0].bullet_level == 0
        assert paras[1].bullet_level == 0
        assert paras[2].bullet_level == 1

    def test_mixed_text_runs(self):
        """bold/italic/color 혼합 텍스트의 run 분리 테스트."""
        data = {
            "background_color": None,
            "textboxes": [
                {
                    "left_px": 64, "top_px": 100, "width_px": 1100, "height_px": 50,
                    "paragraphs": [{
                        "runs": [
                            {"text": "일반 ", "font_size_pt": 16, "color": "#ffffff", "bold": False, "italic": False},
                            {"text": "굵게", "font_size_pt": 16, "color": "#ffffff", "bold": True, "italic": False},
                            {"text": " ", "font_size_pt": 16, "color": "#ffffff", "bold": False, "italic": False},
                            {"text": "기울임", "font_size_pt": 16, "color": "#ff0000", "bold": False, "italic": True},
                        ],
                        "bullet_level": -1,
                    }],
                },
            ],
            "shapes": [],
        }

        spec = _parse_extracted_data(data)

        runs = spec.textboxes[0].paragraphs[0].runs
        assert len(runs) == 3  # 공백만 있는 run은 필터링됨
        assert runs[0].text == "일반 "
        assert runs[0].bold is False
        assert runs[1].text == "굵게"
        assert runs[1].bold is True
        assert runs[2].text == "기울임"
        assert runs[2].italic is True
        assert runs[2].color == "#ff0000"

    def test_empty_textbox_filtered(self):
        """빈 텍스트만 포함된 textbox는 필터링."""
        data = {
            "background_color": None,
            "textboxes": [
                {
                    "left_px": 0, "top_px": 0, "width_px": 100, "height_px": 50,
                    "paragraphs": [{
                        "runs": [{"text": "   ", "font_size_pt": 16, "color": None, "bold": False, "italic": False}],
                        "bullet_level": -1,
                    }],
                },
            ],
            "shapes": [],
        }

        spec = _parse_extracted_data(data)
        assert len(spec.textboxes) == 0

    def test_no_background_color(self):
        """background_color가 null인 경우."""
        data = {"background_color": None, "textboxes": [], "shapes": []}
        spec = _parse_extracted_data(data)
        assert spec.background_color is None


# --- 중복 제거 테스트 ---


class TestDeduplicateOverlapping:
    def test_removes_duplicate_textbox_when_shape_has_text(self):
        """Shape에 이미 텍스트가 있으면 중복 TextBox 제거."""
        from ppt_generator.interfaces.schemas import (
            PptxParagraph,
            PptxShape,
            PptxTextBox,
            PptxTextRun,
        )

        spec = PptxSlideSpec(
            background_color=None,
            textboxes=[
                PptxTextBox(
                    left_px=100, top_px=100, width_px=200, height_px=50,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="카드 제목")])],
                ),
            ],
            shapes=[
                PptxShape(
                    left_px=90, top_px=90, width_px=220, height_px=70,
                    fill_color="#162232",
                    text="카드 제목",
                ),
            ],
        )

        result = _deduplicate_overlapping(spec)
        assert len(result.textboxes) == 0
        assert len(result.shapes) == 1

    def test_keeps_textbox_when_shape_has_no_text(self):
        """Shape에 텍스트가 없으면 TextBox 유지."""
        from ppt_generator.interfaces.schemas import (
            PptxParagraph,
            PptxShape,
            PptxTextBox,
            PptxTextRun,
        )

        spec = PptxSlideSpec(
            background_color=None,
            textboxes=[
                PptxTextBox(
                    left_px=100, top_px=100, width_px=200, height_px=50,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="카드 내용")])],
                ),
            ],
            shapes=[
                PptxShape(
                    left_px=90, top_px=90, width_px=220, height_px=70,
                    fill_color="#162232",
                    text=None,
                ),
            ],
        )

        result = _deduplicate_overlapping(spec)
        assert len(result.textboxes) == 1


# --- rect overlap 테스트 ---


class TestRectsOverlap:
    def test_full_overlap(self):
        assert _rects_overlap(0, 0, 100, 100, 0, 0, 100, 100) is True

    def test_no_overlap(self):
        assert _rects_overlap(0, 0, 50, 50, 200, 200, 50, 50) is False

    def test_partial_overlap_below_threshold(self):
        assert _rects_overlap(0, 0, 100, 100, 50, 50, 100, 100, threshold=0.8) is False

    def test_zero_area(self):
        assert _rects_overlap(0, 0, 0, 100, 0, 0, 100, 100) is False


# --- extract_all_slides_via_dom 통합 테스트 ---


class TestExtractAllSlidesViaDom:
    def test_returns_empty_when_playwright_unavailable(self):
        """Playwright 미설치 시 빈 dict 반환."""
        with patch("ppt_generator.tools.pptx.dom_extractor._PLAYWRIGHT_AVAILABLE", False):
            result = extract_all_slides_via_dom("<html><body><section><h1>Test</h1></section></body></html>", 1)
        assert result == {}

    def test_returns_empty_on_no_sections(self):
        """<section>이 없는 HTML이면 빈 dict 반환."""
        with patch("ppt_generator.tools.pptx.dom_extractor._PLAYWRIGHT_AVAILABLE", True):
            result = extract_all_slides_via_dom("<html><body>빈 페이지</body></html>", 0)
        assert result == {}

    def test_returns_empty_on_browser_error(self):
        """브라우저 실행 실패 시 빈 dict 반환."""
        with patch("ppt_generator.tools.pptx.dom_extractor._PLAYWRIGHT_AVAILABLE", True), \
             patch("ppt_generator.tools.pptx.dom_extractor.sync_playwright", side_effect=Exception("Browser error")):
            result = extract_all_slides_via_dom(
                "<html><body><section><h1>Test</h1></section></body></html>", 1,
            )
        assert result == {}

    @pytest.mark.skipif(
        not _import_playwright_available(),
        reason="Playwright 미설치",
    )
    def test_extracts_simple_slide(self):
        """단순 슬라이드(제목+본문) DOM 추출 통합 테스트."""
        html = (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<style>body{margin:0;} section{width:1280px;height:720px;position:relative;}</style>'
            '</head><body>'
            '<section style="background-color:#0f172a;">'
            '<h1 style="position:absolute;left:64px;top:50px;width:1152px;height:60px;'
            'color:#ffffff;font-size:40px;font-weight:bold;">테스트 제목</h1>'
            '<p style="position:absolute;left:64px;top:150px;width:1152px;height:400px;'
            'color:#cccccc;font-size:21px;">본문 내용입니다.</p>'
            '</section></body></html>'
        )
        result = extract_all_slides_via_dom(html, 1)
        assert 0 in result
        spec = result[0]
        assert spec is not None
        assert spec.background_color is not None
        assert len(spec.textboxes) >= 2

        # 제목 텍스트 확인
        all_text = " ".join(
            r.text for tb in spec.textboxes for p in tb.paragraphs for r in p.runs
        )
        assert "테스트 제목" in all_text
        assert "본문 내용" in all_text
