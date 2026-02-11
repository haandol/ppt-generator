import tempfile
from pathlib import Path

import pytest
from pptx import Presentation

from ppt_generator.interfaces.schemas import PptxRequest, SlideElement, SlideOutline
from ppt_generator.tools.pptx.service import PptxService

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "2026 Confidential AWS Powerpoint Template Light & Dark Themes.pptx"


def _make_slide(
    title: str = "테스트 슬라이드",
    bullets: list[str] | None = None,
    image_idea: str = "",
    layout_type: str = "text_only",
    speaker_notes: str = "발표자 노트입니다.",
    elements: list[SlideElement] | None = None,
) -> SlideOutline:
    return SlideOutline(
        title=title,
        bullets=bullets or ["요점 1", "요점 2"],
        image_idea=image_idea,
        layout_type=layout_type,
        speaker_notes=speaker_notes,
        elements=elements or [],
    )


def _create_test_image(directory: Path) -> Path:
    """1x1 흰색 PNG 파일 생성."""
    # 최소 유효 PNG
    import struct
    import zlib

    def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = zlib.compress(b"\x00\xff\xff\xff")
    idat = _png_chunk(b"IDAT", raw)
    iend = _png_chunk(b"IEND", b"")

    path = directory / "test_image.png"
    path.write_bytes(sig + ihdr + idat + iend)
    return path


@pytest.fixture
def service():
    return PptxService(template_path=TEMPLATE_PATH)


@pytest.fixture
def service_no_template(tmp_path):
    return PptxService(template_path=tmp_path / "nonexistent.pptx")


class TestPptxService:
    def test_generate_creates_pptx_file(self, service):
        request = PptxRequest(slides=[_make_slide()], image_paths={})
        response = service.generate(request)

        path = Path(response.pptx_path)
        assert path.exists()
        assert path.suffix == ".pptx"

    def test_generate_pptx_is_valid(self, service):
        request = PptxRequest(slides=[_make_slide()], image_paths={})
        response = service.generate(request)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 1

    def test_generate_multiple_slides(self, service):
        slides = [
            _make_slide(title="제목 슬라이드", layout_type="title"),
            _make_slide(title="본문 슬라이드", layout_type="text_only"),
            _make_slide(title="감사합니다", layout_type="closing"),
        ]
        request = PptxRequest(slides=slides, image_paths={})
        response = service.generate(request)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 3

    def test_generate_sets_title(self, service):
        request = PptxRequest(
            slides=[_make_slide(title="테스트 제목", layout_type="text_only")],
            image_paths={},
        )
        response = service.generate(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        # text_only 레이아웃의 title placeholder는 idx 0
        assert slide.placeholders[0].text == "테스트 제목"

    def test_generate_sets_bullets(self, service):
        request = PptxRequest(
            slides=[_make_slide(bullets=["첫 번째", "두 번째", "세 번째"], layout_type="text_only")],
            image_paths={},
        )
        response = service.generate(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        # text_only의 body placeholder idx=1
        tf = slide.placeholders[1].text_frame
        texts = [p.text for p in tf.paragraphs]
        assert texts == ["첫 번째", "두 번째", "세 번째"]

    def test_generate_sets_speaker_notes(self, service):
        request = PptxRequest(
            slides=[_make_slide(speaker_notes="이것은 발표자 노트입니다.")],
            image_paths={},
        )
        response = service.generate(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        assert slide.notes_slide.notes_text_frame.text == "이것은 발표자 노트입니다."

    def test_generate_with_image(self, service):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = _create_test_image(Path(tmpdir))
            request = PptxRequest(
                slides=[_make_slide(layout_type="text_image", image_idea="테스트 이미지")],
                image_paths={0: str(img_path)},
            )
            response = service.generate(request)

            prs = Presentation(response.pptx_path)
            assert len(prs.slides) == 1

    def test_generate_handles_missing_image(self, service):
        request = PptxRequest(
            slides=[_make_slide(layout_type="text_image")],
            image_paths={0: "/nonexistent/image.png"},
        )
        response = service.generate(request)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 1

    def test_generate_falls_back_without_template(self, service_no_template):
        request = PptxRequest(
            slides=[_make_slide(layout_type="text_only")],
            image_paths={},
        )
        response = service_no_template.generate(request)

        path = Path(response.pptx_path)
        assert path.exists()
        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 1

    def test_generate_raises_on_empty_slides(self, service):
        request = PptxRequest(slides=[], image_paths={})
        with pytest.raises(ValueError, match="슬라이드 목록이 비어있습니다"):
            service.generate(request)

    def test_generate_title_layout_uses_subtitle_for_bullets(self, service):
        request = PptxRequest(
            slides=[_make_slide(title="발표 제목", bullets=["부제목 내용"], layout_type="title")],
            image_paths={},
        )
        response = service.generate(request)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        assert slide.placeholders[0].text == "발표 제목"
        assert slide.placeholders[1].text == "부제목 내용"


class TestPptxServiceFreeform:
    def test_freeform_textbox_creates_slide(self, service_no_template):
        elements = [
            SlideElement(type="textbox", left=0.5, top=0.5, width=12.0, height=1.5, content="제목입니다", font_size_pt=28, bold=True),
            SlideElement(type="textbox", left=0.5, top=2.5, width=12.0, height=4.0, content="본문 내용", font_size_pt=16, bold=False),
        ]
        slide = _make_slide(layout_type="freeform", elements=elements)
        request = PptxRequest(slides=[slide], image_paths={})
        response = service_no_template.generate(request)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 1
        # freeform 슬라이드에는 textbox가 shape으로 추가됨
        shapes = list(prs.slides[0].shapes)
        assert len(shapes) >= 2

    def test_freeform_textbox_content(self, service_no_template):
        elements = [
            SlideElement(type="textbox", left=1.0, top=1.0, width=5.0, height=2.0, content="Hello World", font_size_pt=20, bold=False),
        ]
        slide = _make_slide(layout_type="freeform", elements=elements)
        request = PptxRequest(slides=[slide], image_paths={})
        response = service_no_template.generate(request)

        prs = Presentation(response.pptx_path)
        shapes = list(prs.slides[0].shapes)
        assert any(s.has_text_frame and "Hello World" in s.text_frame.text for s in shapes)

    def test_freeform_image(self, service_no_template):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = _create_test_image(Path(tmpdir))
            elements = [
                SlideElement(type="image", left=2.0, top=2.0, width=4.0, height=3.0, content=""),
            ]
            slide = _make_slide(layout_type="freeform", elements=elements)
            request = PptxRequest(slides=[slide], image_paths={0: str(img_path)})
            response = service_no_template.generate(request)

            prs = Presentation(response.pptx_path)
            assert len(prs.slides) == 1

    def test_freeform_shape(self, service_no_template):
        elements = [
            SlideElement(type="shape", left=1.0, top=1.0, width=3.0, height=2.0, content="도형 내 텍스트"),
        ]
        slide = _make_slide(layout_type="freeform", elements=elements)
        request = PptxRequest(slides=[slide], image_paths={})
        response = service_no_template.generate(request)

        prs = Presentation(response.pptx_path)
        shapes = list(prs.slides[0].shapes)
        assert any(s.has_text_frame and "도형 내 텍스트" in s.text_frame.text for s in shapes)

    def test_freeform_speaker_notes(self, service_no_template):
        elements = [
            SlideElement(type="textbox", left=0.5, top=0.5, width=5.0, height=2.0, content="텍스트"),
        ]
        slide = _make_slide(layout_type="freeform", elements=elements, speaker_notes="Freeform 노트")
        request = PptxRequest(slides=[slide], image_paths={})
        response = service_no_template.generate(request)

        prs = Presentation(response.pptx_path)
        assert prs.slides[0].notes_slide.notes_text_frame.text == "Freeform 노트"

    def test_mixed_mode_placeholder_and_freeform(self, service_no_template):
        placeholder_slide = _make_slide(title="일반 슬라이드", layout_type="text_only")
        freeform_slide = _make_slide(
            layout_type="freeform",
            elements=[SlideElement(type="textbox", left=1.0, top=1.0, width=5.0, height=2.0, content="자유 배치")],
        )
        request = PptxRequest(slides=[placeholder_slide, freeform_slide], image_paths={})
        response = service_no_template.generate(request)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 2
