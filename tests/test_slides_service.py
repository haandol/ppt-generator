import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
    SlidesResponse,
)
from ppt_generator.tools.slides.service import SlidesService


def _make_design_spec(num_slides: int = 1) -> DesignSpec:
    slides = []
    for i in range(num_slides):
        slides.append(
            PptxSlideSpec(
                background_color="#1a1a2e",
                textboxes=[
                    PptxTextBox(
                        left_px=40, top_px=40, width_px=600, height_px=60,
                        paragraphs=[PptxParagraph(runs=[PptxTextRun(text=f"슬라이드 {i}", font_size_pt=32)])],
                    ),
                ],
                speaker_notes=f"노트 {i}" if i > 0 else "",
            ),
        )
    return DesignSpec(slides=slides)


@pytest.fixture
def service():
    return SlidesService()


class TestGenerateFromDesignSpec:
    def test_returns_slides_response(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        assert isinstance(response, SlidesResponse)
        assert response.session_id
        assert response.html

    def test_produces_html_structure(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        assert "<!DOCTYPE html>" in response.html
        assert "<section" in response.html
        assert "<body>" in response.html

    def test_raises_on_empty_slides(self, service):
        spec = DesignSpec(slides=[])
        with pytest.raises(ValueError, match="디자인 스펙에 슬라이드가 없습니다"):
            service.generate_from_design_spec(spec)

    def test_stores_session(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        html = service.get_session_html(response.session_id)
        assert html == response.html

    def test_multiple_slides(self, service):
        spec = _make_design_spec(3)
        response = service.generate_from_design_spec(spec)

        assert "slide-0" in response.html
        assert "slide-1" in response.html
        assert "slide-2" in response.html

    def test_speaker_notes_in_html(self, service):
        spec = _make_design_spec(2)
        response = service.generate_from_design_spec(spec)

        assert "data-speaker-notes" in response.html
        assert "노트 1" in response.html

    def test_background_color_in_html(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        assert "#1a1a2e" in response.html


class TestGetSessionHtml:
    def test_raises_on_invalid_session(self, service):
        with pytest.raises(KeyError, match="세션을 찾을 수 없습니다"):
            service.get_session_html("nonexistent-id")
