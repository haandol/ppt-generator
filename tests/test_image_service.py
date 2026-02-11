from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.interfaces.schemas import ImageRequest, SlideOutline
from ppt_generator.tools.images.service import ImageService


def _make_slide(image_idea: str = "a cloud diagram", layout_type: str = "text_image") -> SlideOutline:
    return SlideOutline(
        title="테스트",
        bullets=[],
        image_idea=image_idea,
        layout_type=layout_type,
        speaker_notes="",
    )


def _mock_gemini_response(image_bytes: bytes = b"FAKEPNG"):
    """Gemini generate_content 응답을 모킹합니다."""
    mock_image = MagicMock()

    mock_part = MagicMock()
    mock_part.inline_data = MagicMock()
    mock_part.as_image.return_value = mock_image

    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    mock_candidate = MagicMock()
    mock_candidate.content = mock_content

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]

    return mock_response, mock_image


@pytest.fixture
def mock_client():
    client = MagicMock()
    response, mock_image = _mock_gemini_response()
    client.models.generate_content.return_value = response
    client._mock_image = mock_image
    return client


@pytest.fixture
def service(mock_client):
    return ImageService(client=mock_client)


class TestImageService:
    def test_generate_creates_images(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(), _make_slide()])
        response = service.generate(request)

        assert len(response.images) == 2
        assert mock_client.models.generate_content.call_count == 2
        for img in response.images:
            assert img.image_path.endswith(".png")

    def test_generate_saves_image_file(self, service, mock_client, tmp_path):
        request = ImageRequest(slides=[_make_slide()])
        response = service.generate(request, output_dir=tmp_path)

        assert len(response.images) == 1
        mock_client._mock_image.save.assert_called_once()

    def test_generate_skips_empty_image_idea(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(image_idea="")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.models.generate_content.assert_not_called()

    def test_generate_skips_whitespace_image_idea(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(image_idea="   ")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.models.generate_content.assert_not_called()

    def test_generate_skips_text_only_layout(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(layout_type="text_only")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.models.generate_content.assert_not_called()

    def test_generate_skips_title_layout(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(layout_type="title")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.models.generate_content.assert_not_called()

    def test_generate_skips_closing_layout(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(layout_type="closing")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.models.generate_content.assert_not_called()

    def test_generate_continues_on_api_failure(self, mock_client):
        response_ok, _ = _mock_gemini_response()
        mock_client.models.generate_content.side_effect = [
            RuntimeError("API error"),
            response_ok,
        ]
        service = ImageService(client=mock_client)
        request = ImageRequest(slides=[_make_slide(), _make_slide()])
        response = service.generate(request)

        assert len(response.images) == 1
        assert response.images[0].slide_index == 1

    def test_generate_raises_on_empty_slides(self, service):
        request = ImageRequest(slides=[])
        with pytest.raises(ValueError, match="슬라이드 목록이 비어있습니다"):
            service.generate(request)

    def test_generate_tracks_slide_index(self, service):
        slides = [
            _make_slide(image_idea=""),
            _make_slide(),
            _make_slide(layout_type="text_only"),
            _make_slide(),
        ]
        request = ImageRequest(slides=slides)
        response = service.generate(request)

        assert len(response.images) == 2
        assert response.images[0].slide_index == 1
        assert response.images[1].slide_index == 3

    def test_generate_sends_correct_model_params(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(image_idea="a futuristic city")])
        service.generate(request)

        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert call_kwargs["model"] == "gemini-2.5-flash-image"
        assert call_kwargs["contents"] == "a futuristic city"
        config = call_kwargs["config"]
        assert config.response_modalities == ["IMAGE"]
        assert config.image_config.aspect_ratio == "16:9"

    def test_generate_uses_custom_output_dir(self, service, mock_client, tmp_path):
        custom_dir = tmp_path / "custom_images"
        request = ImageRequest(slides=[_make_slide()])
        response = service.generate(request, output_dir=custom_dir)

        assert len(response.images) == 1
        assert "custom_images" in response.images[0].image_path

    def test_generate_creates_output_dir(self, service, tmp_path):
        nested_dir = tmp_path / "a" / "b" / "images"
        request = ImageRequest(slides=[_make_slide()])
        response = service.generate(request, output_dir=nested_dir)

        assert nested_dir.exists()
        assert len(response.images) == 1

    def test_generate_skips_all_text_heavy_layouts(self, service, mock_client):
        """title, text_only, closing 모두 스킵되는지 통합 테스트."""
        slides = [
            _make_slide(layout_type="title"),
            _make_slide(layout_type="text_only"),
            _make_slide(layout_type="closing"),
            _make_slide(layout_type="text_image"),
        ]
        request = ImageRequest(slides=slides)
        response = service.generate(request)

        assert len(response.images) == 1
        assert response.images[0].slide_index == 3
        assert mock_client.models.generate_content.call_count == 1
