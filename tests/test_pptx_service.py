import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pptx import Presentation

from ppt_generator.interfaces.constants import PPTX_FONT_MIN_SIZE_PT, PPTX_FONT_SCALE_FACTOR
from ppt_generator.interfaces.schemas import ExportPptxRequest
from ppt_generator.tools.pptx.service import ExportService


def _make_minimal_png() -> bytes:
    """1x1 흰색 PNG 바이트 생성."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat = _chunk(b"IDAT", raw)
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _make_sample_html(png_path: Path) -> str:
    return (
        '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
        '<section data-speaker-notes="발표자 노트"\n'
        '     style="background-color:#1a2b3c;">\n'
        '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;\n'
        '             font-size:36px;font-weight:bold;color:#333333;">제목</h1>\n'
        '  <p style="position:absolute;left:50px;top:130px;width:400px;height:200px;\n'
        '            font-size:18px;">본문 텍스트</p>\n'
        f'  <img src="file://{png_path}" alt="이미지 설명"\n'
        '       style="position:absolute;left:500px;top:130px;width:400px;height:300px;"/>\n'
        '</section>\n'
        '</body></html>'
    )

MULTI_SLIDE_HTML = (
    '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
    '<section>\n'
    '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;">슬라이드 1</h1>\n'
    '</section>\n'
    '<section>\n'
    '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;">슬라이드 2</h1>\n'
    '</section>\n'
    '<section>\n'
    '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;">슬라이드 3</h1>\n'
    '</section>\n'
    '</body></html>'
)


def _make_slides_service(html: str) -> MagicMock:
    mock = MagicMock()
    mock.get_session_html.return_value = html
    return mock


@pytest.fixture
def png_file(tmp_path) -> Path:
    """테스트용 PNG 파일 생성."""
    p = tmp_path / "test_image.png"
    p.write_bytes(_make_minimal_png())
    return p


@pytest.fixture
def service(tmp_path, png_file):
    html = _make_sample_html(png_file)
    mock_slides = _make_slides_service(html)
    return ExportService(slides_service=mock_slides, use_llm_convert=False)


@pytest.fixture
def service_with_html(tmp_path):
    """커스텀 HTML로 ExportService를 생성하는 팩토리 fixture."""
    def _factory(html: str):
        mock_slides = _make_slides_service(html)
        return ExportService(slides_service=mock_slides, use_llm_convert=False)
    return _factory


class TestExportService:
    def test_export_creates_pptx_file(self, service):
        request = ExportPptxRequest(session_id="test-session")
        response = service.export(request)

        path = Path(response.pptx_path)
        assert path.exists()
        assert path.suffix == ".pptx"

    def test_export_raises_on_invalid_session(self, tmp_path):
        mock_slides = MagicMock()
        mock_slides.get_session_html.side_effect = KeyError("세션을 찾을 수 없습니다: bad-id")
        svc = ExportService(slides_service=mock_slides)

        with pytest.raises(KeyError):
            svc.export(ExportPptxRequest(session_id="bad-id"))

    def test_export_extracts_text(self, service):
        request = ExportPptxRequest(session_id="test-session")
        response = service.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        all_text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
        assert "제목" in all_text
        assert "본문 텍스트" in all_text

    def test_export_preserves_speaker_notes(self, service):
        request = ExportPptxRequest(session_id="test-session")
        response = service.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        assert slide.notes_slide.notes_text_frame.text == "발표자 노트"

    def test_export_preserves_position(self, service):
        request = ExportPptxRequest(session_id="test-session")
        response = service.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        # h1 (제목) 텍스트박스의 위치 확인 (left:50px → ~0.694in)
        textboxes = [s for s in slide.shapes if s.has_text_frame and "제목" in s.text_frame.text]
        assert len(textboxes) >= 1
        tb = textboxes[0]
        left_inches = tb.left / 914400  # EMU to inches
        top_inches = tb.top / 914400
        # 50px * (13.333/1280) ≈ 0.521in
        assert abs(left_inches - 0.521) < 0.1
        # 30px * (7.5/720) ≈ 0.3125in
        assert abs(top_inches - 0.3125) < 0.1

    def test_export_handles_missing_image_file(self, service_with_html):
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section>\n'
            '  <img src="file:///nonexistent/path/image.png" alt="없는 이미지"\n'
            '       style="position:absolute;left:100px;top:100px;width:200px;height:200px;"/>\n'
            '  <p style="position:absolute;left:50px;top:50px;width:200px;height:50px;">텍스트</p>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        request = ExportPptxRequest(session_id="test-session")
        # 에러 없이 완료 (이미지는 건너뜀)
        response = svc.export(request)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 1
        # 이미지 shape은 없어야 함
        picture_shapes = [s for s in prs.slides[0].shapes if s.shape_type == 13]
        assert len(picture_shapes) == 0

    def test_export_handles_multiple_slides(self, service_with_html):
        svc = service_with_html(MULTI_SLIDE_HTML)
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 3

    def test_export_handles_background_color(self, service):
        request = ExportPptxRequest(session_id="test-session")
        response = service.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        fill = slide.background.fill
        # 배경이 설정되었는지 확인
        assert fill.fore_color.rgb is not None
        # #1a2b3c
        assert str(fill.fore_color.rgb) == "1A2B3C"

    def test_export_raises_on_no_slides(self, service_with_html):
        svc = service_with_html("<html><body>빈 페이지</body></html>")
        with pytest.raises(ValueError, match="슬라이드를 찾을 수 없습니다"):
            svc.export(ExportPptxRequest(session_id="test-session"))

    def test_export_uses_custom_output_dir(self, service_with_html, tmp_path):
        svc = service_with_html(MULTI_SLIDE_HTML)
        custom_dir = tmp_path / "custom_export"
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request, output_dir=custom_dir)

        path = Path(response.pptx_path)
        assert path.parent == custom_dir
        assert path.exists()
        assert path.name == "presentation.pptx"

    def test_export_creates_output_dir(self, service_with_html, tmp_path):
        svc = service_with_html(MULTI_SLIDE_HTML)
        nested_dir = tmp_path / "a" / "b" / "export"
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request, output_dir=nested_dir)

        assert nested_dir.exists()
        assert Path(response.pptx_path).exists()


def _make_region_html(png_path: Path | None = None) -> str:
    """region 기반 HTML 구조를 생성."""
    img_tag = ""
    if png_path:
        img_tag = (
            f'      <img src="file://{png_path}" style="width:100%; height:100%; object-fit:cover;" />'
        )
    image_region = ""
    if png_path:
        image_region = (
            '    <div data-region="image" style="position:absolute; left:702px; top:36px; '
            'width:542px; height:616px; overflow:hidden;">\n'
            f'{img_tag}\n'
            '    </div>\n'
        )
    return (
        '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
        '<section id="slide-0" data-speaker-notes="발표자 노트">\n'
        '  <div data-wrapper="true" '
        'style="position:absolute; top:0; left:0; right:0; bottom:0; background-color:#0f172a;">\n'
        '    <div data-region="title" style="position:absolute; left:57px; top:96px; '
        'width:1152px; height:56px; overflow:hidden;">\n'
        '      <h2 style="color:#fff; font-size:1.875rem; font-weight:bold;">제목 텍스트</h2>\n'
        '    </div>\n'
        '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
        'width:1152px; height:472px; overflow:hidden;">\n'
        '      <p style="color:#fff; font-size:1.125rem;">본문 텍스트</p>\n'
        '    </div>\n'
        f'{image_region}'
        '  </div>\n'
        '</section>\n'
        '</body></html>'
    )


class TestRegionBasedExport:
    """data-wrapper/data-region 기반 HTML 내보내기 테스트."""

    def test_export_region_html_creates_pptx(self, service_with_html):
        svc = service_with_html(_make_region_html())
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request)

        path = Path(response.pptx_path)
        assert path.exists()
        assert path.suffix == ".pptx"

    def test_export_region_extracts_text(self, service_with_html):
        svc = service_with_html(_make_region_html())
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        all_text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
        assert "제목 텍스트" in all_text
        assert "본문 텍스트" in all_text

    def test_export_region_preserves_speaker_notes(self, service_with_html):
        svc = service_with_html(_make_region_html())
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        assert slide.notes_slide.notes_text_frame.text == "발표자 노트"

    def test_export_region_extracts_background(self, service_with_html):
        svc = service_with_html(_make_region_html())
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        fill = slide.background.fill
        assert fill.fore_color.rgb is not None
        assert str(fill.fore_color.rgb) == "0F172A"

    def test_export_region_title_position(self, service_with_html):
        """title region 좌표가 PPTX에서도 유지되는지 확인."""
        svc = service_with_html(_make_region_html())
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        textboxes = [s for s in slide.shapes if s.has_text_frame and "제목" in s.text_frame.text]
        assert len(textboxes) >= 1
        tb = textboxes[0]
        left_inches = tb.left / 914400
        top_inches = tb.top / 914400
        # 57px * (13.333/1280) ≈ 0.594in
        assert abs(left_inches - 0.594) < 0.1
        # 96px * (7.5/720) ≈ 1.0in
        assert abs(top_inches - 1.0) < 0.1

    def test_export_region_preserves_rem_font_size(self, service_with_html):
        """rem 단위 글꼴 크기가 PPTX에 보존되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">\n'
            '    <div data-region="title" style="position:absolute; left:57px; top:96px; '
            'width:1152px; height:56px; overflow:hidden;">\n'
            '      <h2 style="color:#fff; font-size:1.875rem; font-weight:bold;">제목</h2>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        textboxes = [s for s in slide.shapes if s.has_text_frame and "제목" in s.text_frame.text]
        assert len(textboxes) >= 1
        tb = textboxes[0]
        # 1.875rem * 16 = 30px → 30 * 1.5 = 45 → Pt(45) (스케일링 적용)
        for p in tb.text_frame.paragraphs:
            for run in p.runs:
                if run.text.strip():
                    assert run.font.size is not None
                    assert run.font.size.pt == 45

    def test_export_region_preserves_child_color(self, service_with_html):
        """자식 요소의 color가 PPTX에 보존되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">\n'
            '    <div data-region="title" style="position:absolute; left:57px; top:96px; '
            'width:1152px; height:56px; overflow:hidden;">\n'
            '      <h2 style="color:#ff5500; font-size:28px; font-weight:bold;">색상 제목</h2>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        textboxes = [s for s in slide.shapes if s.has_text_frame and "색상 제목" in s.text_frame.text]
        assert len(textboxes) >= 1
        tb = textboxes[0]
        for p in tb.text_frame.paragraphs:
            for run in p.runs:
                if run.text.strip():
                    assert run.font.color.rgb is not None
                    assert str(run.font.color.rgb) == "FF5500"

    def test_export_region_bullet_points(self, service_with_html):
        """ul/li 불릿 포인트가 PPTX 불릿으로 변환되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <ul>\n'
            '        <li style="color:#fff; font-size:18px;">항목 1</li>\n'
            '        <li style="color:#fff; font-size:18px;">항목 2</li>\n'
            '        <li style="color:#fff; font-size:18px;">항목 3</li>\n'
            '      </ul>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        from lxml import etree
        from pptx.oxml.ns import qn
        textboxes = [s for s in slide.shapes if s.has_text_frame]
        bullet_count = 0
        for tb in textboxes:
            for p in tb.text_frame.paragraphs:
                pPr = p._p.find(qn("a:pPr"))
                if pPr is not None:
                    buChar = pPr.find(qn("a:buChar"))
                    if buChar is not None:
                        bullet_count += 1
        assert bullet_count == 3

    def test_export_region_flex_columns(self, service_with_html):
        """flex 멀티 컬럼 레이아웃이 개별 텍스트박스로 변환되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <div style="display:flex; gap:32px;">\n'
            '        <div style="flex:1;"><p style="color:#fff;">왼쪽 컬럼</p></div>\n'
            '        <div style="flex:1;"><p style="color:#fff;">오른쪽 컬럼</p></div>\n'
            '      </div>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        textboxes = [s for s in slide.shapes if s.has_text_frame]
        # flex 2컬럼 → 2개의 텍스트박스
        assert len(textboxes) >= 2
        all_text = " ".join(s.text_frame.text for s in textboxes)
        assert "왼쪽 컬럼" in all_text
        assert "오른쪽 컬럼" in all_text
        # 두 텍스트박스의 left 값이 다른지 확인 (분할 배치)
        lefts = sorted(set(s.left for s in textboxes))
        assert len(lefts) >= 2

    def test_export_region_bold_detection(self, service_with_html):
        """h3 및 font-weight:bold가 PPTX에서 bold로 감지되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <h3 style="color:#fff; font-weight:bold;">볼드 제목</h3>\n'
            '      <p style="color:#fff; font-weight:bold;">볼드 본문</p>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        textboxes = [s for s in slide.shapes if s.has_text_frame]
        bold_texts = []
        for tb in textboxes:
            for p in tb.text_frame.paragraphs:
                for run in p.runs:
                    if run.font.bold and run.text.strip():
                        bold_texts.append(run.text.strip())
        assert "볼드 제목" in bold_texts
        assert "볼드 본문" in bold_texts

    def test_legacy_html_still_works(self, service_with_html):
        """data-wrapper가 없는 레거시 HTML도 정상 동작."""
        legacy_html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section>\n'
            '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;">레거시 제목</h1>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(legacy_html)
        request = ExportPptxRequest(session_id="test-session")
        response = svc.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        all_text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
        assert "레거시 제목" in all_text


class TestFontSizeScaling:
    """PPTX 폰트 크기 스케일링 테스트."""

    def test_scale_font_size_applies_factor(self):
        """스케일 팩터가 올바르게 적용되는지 확인."""
        result = ExportService._scale_font_size(18)
        assert result == int(18 * PPTX_FONT_SCALE_FACTOR)  # 21

    def test_scale_font_size_enforces_minimum(self):
        """최소 폰트 크기가 보장되는지 확인."""
        result = ExportService._scale_font_size(11)
        # 11 * 1.2 = 13.2 → int(13) < 14 → 14
        assert result == PPTX_FONT_MIN_SIZE_PT

    def test_scale_font_size_none_passthrough(self):
        """None 입력은 None을 반환."""
        assert ExportService._scale_font_size(None) is None

    def test_scale_font_size_large_value(self):
        """큰 폰트 크기는 스케일만 적용되고 최소값에 영향 없음."""
        result = ExportService._scale_font_size(36)
        assert result == int(36 * PPTX_FONT_SCALE_FACTOR)  # 43

    def test_region_font_size_scaled_in_pptx(self, service_with_html):
        """룰 기반 폴백에서 폰트 크기가 스케일링되어 PPTX에 반영되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <p style="color:#fff; font-size:11px;">작은 텍스트</p>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        for shape in slide.shapes:
            if shape.has_text_frame and "작은 텍스트" in shape.text_frame.text:
                for p in shape.text_frame.paragraphs:
                    for run in p.runs:
                        if run.text.strip():
                            # 11px → 11*1.2=13.2 → min 14pt
                            assert run.font.size is not None
                            assert run.font.size.pt == PPTX_FONT_MIN_SIZE_PT
                            return
        pytest.fail("작은 텍스트가 포함된 shape을 찾지 못했습니다")

    def test_region_font_size_scaled_above_minimum(self, service_with_html):
        """최소값보다 큰 폰트는 스케일만 적용되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <p style="color:#fff; font-size:18px;">본문 텍스트</p>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        for shape in slide.shapes:
            if shape.has_text_frame and "본문 텍스트" in shape.text_frame.text:
                for p in shape.text_frame.paragraphs:
                    for run in p.runs:
                        if run.text.strip():
                            # 18px → 18*1.2=21.6 → int(21) → 21pt
                            assert run.font.size is not None
                            assert run.font.size.pt == int(18 * PPTX_FONT_SCALE_FACTOR)
                            return
        pytest.fail("본문 텍스트가 포함된 shape을 찾지 못했습니다")


class TestCssClassInlining:
    """CSS 클래스가 PPTX export 시 인라이닝되어 정상 변환되는지 테스트."""

    def test_css_class_inlined_in_export(self, service_with_html):
        """CSS 클래스로 지정된 배경색이 PPTX 도형/텍스트에 반영되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8">\n'
            '<style>\n'
            '.info-card { background-color: #162232; border-radius: 12px; padding: 24px; }\n'
            '</style></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0; '
            'background-color:#0d1b2a;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <div class="info-card">\n'
            '        <p style="color:#ffffff; font-size:20px;">카드 내용</p>\n'
            '      </div>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        all_text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
        assert "카드 내용" in all_text

    def test_css_class_two_col_layout(self, service_with_html):
        """two-col CSS 클래스가 인라이닝되어 grid 레이아웃이 적용되는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8">\n'
            '<style>\n'
            '.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }\n'
            '.info-card { background-color: #162232; padding: 24px; }\n'
            '</style></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0; '
            'background-color:#0d1b2a;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <div class="two-col">\n'
            '        <div class="info-card"><p style="color:#fff; font-size:20px;">왼쪽</p></div>\n'
            '        <div class="info-card"><p style="color:#fff; font-size:20px;">오른쪽</p></div>\n'
            '      </div>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        all_text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
        assert "왼쪽" in all_text
        assert "오른쪽" in all_text

    def test_inline_style_overrides_css_class(self, service_with_html):
        """인라인 style이 CSS 클래스보다 우선하는지 확인."""
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8">\n'
            '<style>\n'
            '.info-card { background-color: #162232; padding: 24px; }\n'
            '</style></head>\n<body>\n'
            '<section id="slide-0">\n'
            '  <div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0; '
            'background-color:#0d1b2a;">\n'
            '    <div data-region="body" style="position:absolute; left:64px; top:180px; '
            'width:1152px; height:472px; overflow:hidden;">\n'
            '      <div class="info-card" style="background-color: #ff0000;">\n'
            '        <p style="color:#ffffff; font-size:20px;">커스텀 배경</p>\n'
            '      </div>\n'
            '    </div>\n'
            '  </div>\n'
            '</section>\n'
            '</body></html>'
        )
        svc = service_with_html(html)
        response = svc.export(ExportPptxRequest(session_id="test-session"))

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        all_text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
        assert "커스텀 배경" in all_text
