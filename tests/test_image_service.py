import base64
import io
import json
from unittest.mock import MagicMock

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


def _mock_invoke_response(image_bytes: bytes = b"FAKEPNG") -> dict:
    body = io.BytesIO(json.dumps({"images": [base64.b64encode(image_bytes).decode()]}).encode())
    return {"body": body}


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.invoke_model.side_effect = lambda **kwargs: _mock_invoke_response()
    return client


@pytest.fixture
def service(mock_client):
    return ImageService(bedrock_runtime=mock_client)


class TestImageService:
    def test_generate_creates_images(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(), _make_slide()])
        response = service.generate(request)

        assert len(response.images) == 2
        assert mock_client.invoke_model.call_count == 2
        for img in response.images:
            assert img.image_path.endswith(".png")

    def test_generate_writes_image_file(self, service):
        request = ImageRequest(slides=[_make_slide()])
        response = service.generate(request)

        from pathlib import Path

        path = Path(response.images[0].image_path)
        assert path.exists()
        assert path.read_bytes() == b"FAKEPNG"

    def test_generate_skips_empty_image_idea(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(image_idea="")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.invoke_model.assert_not_called()

    def test_generate_skips_whitespace_image_idea(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(image_idea="   ")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.invoke_model.assert_not_called()

    def test_generate_skips_text_only_layout(self, service, mock_client):
        request = ImageRequest(slides=[_make_slide(layout_type="text_only")])
        response = service.generate(request)

        assert len(response.images) == 0
        mock_client.invoke_model.assert_not_called()

    def test_generate_continues_on_api_failure(self, mock_client):
        mock_client.invoke_model.side_effect = [
            RuntimeError("API error"),
            _mock_invoke_response(),
        ]
        service = ImageService(bedrock_runtime=mock_client)
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

        call_kwargs = mock_client.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == "amazon.titan-image-generator-v2:0"
        assert call_kwargs["accept"] == "application/json"

        body = json.loads(call_kwargs["body"])
        assert body["taskType"] == "TEXT_IMAGE"
        assert body["textToImageParams"]["text"] == "a futuristic city"
        assert body["imageGenerationConfig"]["width"] == 1280
        assert body["imageGenerationConfig"]["height"] == 768
