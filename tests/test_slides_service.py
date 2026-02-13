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
        assert len(response.slide_htmls) == 1
        assert response.container_html

    def test_slide_html_is_complete_document(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        slide_html = response.slide_htmls[0]
        assert "<!DOCTYPE html>" in slide_html
        assert "<section" in slide_html
        assert "<body" in slide_html
        assert "</html>" in slide_html

    def test_container_html_has_iframes(self, service):
        spec = _make_design_spec(3)
        response = service.generate_from_design_spec(spec)

        assert "iframe" in response.container_html
        assert 'src="slides/slide_01.html"' in response.container_html
        assert 'src="slides/slide_02.html"' in response.container_html
        assert 'src="slides/slide_03.html"' in response.container_html

    def test_container_html_has_slide_numbers(self, service):
        spec = _make_design_spec(3)
        response = service.generate_from_design_spec(spec)

        assert "1 / 3" in response.container_html
        assert "2 / 3" in response.container_html
        assert "3 / 3" in response.container_html

    def test_raises_on_empty_slides(self, service):
        spec = DesignSpec(slides=[])
        with pytest.raises(ValueError, match="디자인 스펙에 슬라이드가 없습니다"):
            service.generate_from_design_spec(spec)

    def test_stores_session(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        html = service.get_session_html(response.session_id)
        assert html == response.container_html

    def test_multiple_slides(self, service):
        spec = _make_design_spec(3)
        response = service.generate_from_design_spec(spec)

        assert len(response.slide_htmls) == 3
        assert "slide-0" in response.slide_htmls[0]
        assert "slide-1" in response.slide_htmls[1]
        assert "slide-2" in response.slide_htmls[2]

    def test_speaker_notes_in_slide_html(self, service):
        spec = _make_design_spec(2)
        response = service.generate_from_design_spec(spec)

        assert "data-speaker-notes" in response.slide_htmls[1]
        assert "노트 1" in response.slide_htmls[1]

    def test_background_color_in_slide_html(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        assert "#1a1a2e" in response.slide_htmls[0]


class TestGetSessionHtml:
    def test_raises_on_invalid_session(self, service):
        with pytest.raises(KeyError, match="세션을 찾을 수 없습니다"):
            service.get_session_html("nonexistent-id")
