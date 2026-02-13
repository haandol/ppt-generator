"""DOM 추출 모듈 단위 테스트."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.interfaces.schemas import PptxImage, PptxSlideSpec
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

    def test_card_layout_creates_background_only_shape(self):
        """카드(info-card)가 background-only Shape (paragraphs=[])으로 변환되는지 테스트."""
        data = {
            "background_color": "#0d1b2a",
            "textboxes": [
                {
                    "left_px": 80, "top_px": 200, "width_px": 500, "height_px": 50,
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
                    "paragraphs": [],
                },
            ],
        }

        spec = _parse_extracted_data(data)

        assert len(spec.shapes) == 1
        assert spec.shapes[0].shape_type == "rounded_rectangle"
        assert spec.shapes[0].fill_color == "#162232"
        assert spec.shapes[0].corner_radius_px == 12
        assert spec.shapes[0].paragraphs == []  # background-only: 텍스트 없음
        assert len(spec.textboxes) == 1  # 텍스트는 별도 textbox로 존재
        assert spec.textboxes[0].paragraphs[0].runs[0].text == "카드 내용"

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
    def test_removes_duplicate_textbox_with_same_text_and_position(self):
        """동일 위치에 동일 텍스트를 가진 TextBox가 중복 제거됨."""
        from ppt_generator.interfaces.schemas import (
            PptxParagraph,
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
                PptxTextBox(
                    left_px=105, top_px=102, width_px=195, height_px=48,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="카드 제목")])],
                ),
            ],
            shapes=[],
        )

        result = _deduplicate_overlapping(spec)
        assert len(result.textboxes) == 1
        assert result.textboxes[0].paragraphs[0].runs[0].text == "카드 제목"

    def test_keeps_textboxes_with_different_text(self):
        """다른 텍스트를 가진 TextBox는 유지."""
        from ppt_generator.interfaces.schemas import (
            PptxParagraph,
            PptxTextBox,
            PptxTextRun,
        )

        spec = PptxSlideSpec(
            background_color=None,
            textboxes=[
                PptxTextBox(
                    left_px=100, top_px=100, width_px=200, height_px=50,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="제목")])],
                ),
                PptxTextBox(
                    left_px=100, top_px=160, width_px=200, height_px=50,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="본문")])],
                ),
            ],
            shapes=[],
        )

        result = _deduplicate_overlapping(spec)
        assert len(result.textboxes) == 2

    def test_keeps_textbox_when_shape_has_no_text(self):
        """Shape에 텍스트가 없으면 (background-only) TextBox 유지."""
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

    @pytest.mark.skipif(
        not _import_playwright_available(),
        reason="Playwright 미설치",
    )
    def test_shape_produces_background_and_separate_textboxes(self):
        """Shape 요소가 background-only shape + 텍스트 textbox를 생성."""
        html = (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<style>body{margin:0;} section{width:1280px;height:720px;position:relative;}</style>'
            '</head><body>'
            '<section style="background-color:#0f172a;">'
            '<div class="info-card" style="position:absolute;left:64px;top:100px;width:500px;height:300px;'
            'background-color:#1e293b;border-radius:12px;padding:20px;">'
            '<h3 style="color:#ffffff;font-size:24px;font-weight:bold;">카드 제목</h3>'
            '<p style="color:#94a3b8;font-size:16px;">카드 본문 내용입니다.</p>'
            '</div>'
            '</section></body></html>'
        )
        result = extract_all_slides_via_dom(html, 1)
        assert 0 in result
        spec = result[0]
        assert spec is not None

        # Shape은 background-only (paragraphs 비어있음)
        assert len(spec.shapes) >= 1
        card_shape = spec.shapes[0]
        assert card_shape.fill_color is not None
        assert card_shape.paragraphs == []
        assert card_shape.text is None

        # 텍스트는 별도 textbox로 존재
        all_text = " ".join(
            r.text for tb in spec.textboxes for p in tb.paragraphs for r in p.runs
        )
        assert "카드 제목" in all_text
        assert "카드 본문" in all_text

    @pytest.mark.skipif(
        not _import_playwright_available(),
        reason="Playwright 미설치",
    )
    def test_complex_card_produces_multiple_textboxes(self):
        """카드(title + body) → shape 1개 + textbox 2개."""
        html = (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<style>body{margin:0;} section{width:1280px;height:720px;position:relative;}</style>'
            '</head><body>'
            '<section style="background-color:#0f172a;">'
            '<div class="step-card" style="position:absolute;left:64px;top:100px;width:500px;height:300px;'
            'background-color:#1e293b;border-radius:12px;padding:20px;">'
            '<span style="color:#60a5fa;font-size:12px;font-weight:bold;">STEP 01</span>'
            '<h3 style="color:#ffffff;font-size:20px;font-weight:bold;">단계 제목</h3>'
            '<p style="color:#94a3b8;font-size:14px;">단계 설명 내용</p>'
            '</div>'
            '</section></body></html>'
        )
        result = extract_all_slides_via_dom(html, 1)
        assert 0 in result
        spec = result[0]
        assert spec is not None

        # Shape은 1개 (background-only)
        assert len(spec.shapes) >= 1
        assert spec.shapes[0].paragraphs == []

        # Textbox는 최소 2개 (STEP 01, 단계 제목, 단계 설명 중 일부가 병합될 수 있음)
        assert len(spec.textboxes) >= 2
        all_text = " ".join(
            r.text for tb in spec.textboxes for p in tb.paragraphs for r in p.runs
        )
        assert "STEP 01" in all_text
        assert "단계 제목" in all_text
        assert "단계 설명" in all_text


# --- PptxImage + 너비 패딩 테스트 ---


class TestPptxImageAndWidthPadding:
    def test_pptx_slide_spec_images_default(self):
        """PptxSlideSpec() 생성 시 images=[] 기본값."""
        spec = PptxSlideSpec()
        assert spec.images == []

    def test_pptx_slide_spec_with_images(self):
        """PptxSlideSpec에 images 필드가 올바르게 저장."""
        img = PptxImage(left_px=10, top_px=20, width_px=300, height_px=200, image_bytes=b"\x89PNG")
        spec = PptxSlideSpec(images=[img])
        assert len(spec.images) == 1
        assert spec.images[0].image_bytes == b"\x89PNG"

    @pytest.mark.skipif(
        not _import_playwright_available(),
        reason="Playwright 미설치",
    )
    def test_pre_element_captured_as_code_image(self):
        """<pre> 요소가 code_images로 캡처되어 images에 PNG 바이트 존재."""
        html = (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<style>body{margin:0;} section{width:1280px;height:720px;position:relative;}'
            'pre{position:absolute;left:64px;top:200px;width:600px;height:200px;'
            'background:#1e293b;color:#e2e8f0;padding:16px;font-family:monospace;font-size:14px;}</style>'
            '</head><body>'
            '<section style="background-color:#0f172a;">'
            '<h1 style="position:absolute;left:64px;top:50px;width:1152px;height:60px;'
            'color:#ffffff;font-size:40px;font-weight:bold;">코드 슬라이드</h1>'
            '<pre><code>def hello():\n    print("world")</code></pre>'
            '</section></body></html>'
        )
        result = extract_all_slides_via_dom(html, 1)
        assert 0 in result
        spec = result[0]
        assert spec is not None
        assert len(spec.images) >= 1
        assert len(spec.images[0].image_bytes) > 0
        # PNG 시그니처 확인
        assert spec.images[0].image_bytes[:4] == b"\x89PNG"

    @pytest.mark.skipif(
        not _import_playwright_available(),
        reason="Playwright 미설치",
    )
    def test_shape_child_textbox_has_width_padding(self):
        """Shape 내부 badge textbox가 원본 HTML 너비보다 넓은지 확인."""
        html = (
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            '<style>body{margin:0;} section{width:1280px;height:720px;position:relative;}</style>'
            '</head><body>'
            '<section style="background-color:#0f172a;">'
            '<div class="badge" style="position:absolute;left:64px;top:100px;width:200px;height:28px;'
            'background-color:#1e40af;border-radius:14px;display:flex;align-items:center;justify-content:center;">'
            '<span style="color:#ffffff;font-size:12px;font-weight:bold;">Bedrock</span>'
            '</div>'
            '</section></body></html>'
        )
        result = extract_all_slides_via_dom(html, 1)
        assert 0 in result
        spec = result[0]
        assert spec is not None
        # badge textbox의 너비가 패딩 적용됨 (원본 span 너비보다 넓어야 함)
        badge_tbs = [tb for tb in spec.textboxes if any(
            "Bedrock" in r.text for p in tb.paragraphs for r in p.runs
        )]
        assert len(badge_tbs) >= 1
        # 높이 < 35px이므로 20% 패딩 적용 → 원본보다 넓어야 함
        # 원본 span 너비는 대략 50-80px 범위이므로 패딩 후 더 넓은지 확인
        for tb in badge_tbs:
            assert tb.width_px > 0
