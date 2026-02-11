import base64
import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pptx import Presentation

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


VALID_PNG_B64 = base64.b64encode(_make_minimal_png()).decode("ascii")

SAMPLE_HTML = (
    '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
    '<div class="slide" data-speaker-notes="발표자 노트"\n'
    '     style="width:960px;height:540px;position:relative;background-color:#1a2b3c;">\n'
    '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;\n'
    '             font-size:36px;font-weight:bold;color:#333333;">제목</h1>\n'
    '  <p style="position:absolute;left:50px;top:130px;width:400px;height:200px;\n'
    '            font-size:18px;">본문 텍스트</p>\n'
    '  <img src="data:image/png;base64,' + VALID_PNG_B64 + '" alt="이미지 설명"\n'
    '       style="position:absolute;left:500px;top:130px;width:400px;height:300px;"/>\n'
    '</div>\n</body></html>'
)

MULTI_SLIDE_HTML = (
    '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
    '<div class="slide" style="width:960px;height:540px;position:relative;">\n'
    '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;">슬라이드 1</h1>\n'
    '</div>\n'
    '<div class="slide" style="width:960px;height:540px;position:relative;">\n'
    '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;">슬라이드 2</h1>\n'
    '</div>\n'
    '<div class="slide" style="width:960px;height:540px;position:relative;">\n'
    '  <h1 style="position:absolute;left:50px;top:30px;width:860px;height:80px;">슬라이드 3</h1>\n'
    '</div>\n'
    '</body></html>'
)


def _make_slides_service(html: str = SAMPLE_HTML) -> MagicMock:
    mock = MagicMock()
    mock.get_session_html.return_value = html
    return mock


@pytest.fixture
def service(tmp_path):
    mock_slides = _make_slides_service()
    return ExportService(slides_service=mock_slides, template_path=tmp_path / "nonexistent.pptx")


@pytest.fixture
def service_with_html(tmp_path):
    """커스텀 HTML로 ExportService를 생성하는 팩토리 fixture."""
    def _factory(html: str):
        mock_slides = _make_slides_service(html)
        return ExportService(slides_service=mock_slides, template_path=tmp_path / "nonexistent.pptx")
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
        svc = ExportService(slides_service=mock_slides, template_path=tmp_path / "nonexistent.pptx")

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

    def test_export_extracts_images(self, service):
        request = ExportPptxRequest(session_id="test-session")
        response = service.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        picture_shapes = [s for s in slide.shapes if s.shape_type == 13]  # MSO_SHAPE_TYPE.PICTURE
        assert len(picture_shapes) >= 1

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
        # 50px * (13.333/960) ≈ 0.694in
        assert abs(left_inches - 0.694) < 0.1
        # 30px * (7.5/540) ≈ 0.417in
        assert abs(top_inches - 0.417) < 0.1

    def test_export_sets_image_alt_text(self, service):
        request = ExportPptxRequest(session_id="test-session")
        response = service.export(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        picture_shapes = [s for s in slide.shapes if s.shape_type == 13]
        assert len(picture_shapes) >= 1
        from pptx.oxml.ns import qn
        nvPicPr = picture_shapes[0]._element.find(qn("p:nvPicPr"))
        assert nvPicPr is not None
        cNvPr = nvPicPr.find(qn("p:cNvPr"))
        assert cNvPr is not None
        assert cNvPr.get("descr") == "이미지 설명"

    def test_export_handles_base64_decode_failure(self, service_with_html):
        html = (
            '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"></head>\n<body>\n'
            '<div class="slide" style="width:960px;height:540px;position:relative;">\n'
            '  <img src="data:image/png;base64,INVALID_BASE64!!!" alt="깨진 이미지"\n'
            '       style="position:absolute;left:100px;top:100px;width:200px;height:200px;"/>\n'
            '  <p style="position:absolute;left:50px;top:50px;width:200px;height:50px;">텍스트</p>\n'
            '</div>\n</body></html>'
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
