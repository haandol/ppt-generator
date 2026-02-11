"""ImageService 통합 테스트 - 실제 Gemini API를 호출하여 이미지를 생성합니다.

실행 전 GEMINI_API_KEY 환경변수가 설정되어 있어야 합니다.
    export GEMINI_API_KEY="your-key"
    uv run pytest tests/test_image_service_integration.py -v -s
"""

import os

import pytest
from google import genai

from ppt_generator.interfaces.schemas import ImageRequest, SlideOutline
from ppt_generator.tools.images.service import ImageService


pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY 환경변수가 설정되지 않았습니다.",
)


def _make_slide(
    title: str = "테스트 슬라이드",
    content_summary: str = "a simple blue circle on white background",
    layout_index: int = 28,
) -> SlideOutline:
    return SlideOutline(
        title=title,
        content_summary=content_summary,
        layout_index=layout_index,
    )


@pytest.fixture(scope="module")
def image_service():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return ImageService(client=client)


class TestImageServiceIntegration:
    def test_generate_single_image(self, image_service, tmp_path):
        """간단한 프롬프트로 이미지 1장을 생성합니다."""
        request = ImageRequest(slides=[_make_slide()])
        response = image_service.generate(request, output_dir=tmp_path)

        assert len(response.images) == 1
        result = response.images[0]
        assert result.slide_index == 0

        image_file = tmp_path / "slide_0.png"
        assert image_file.exists()
        assert image_file.stat().st_size > 0
        print(f"\n  생성된 이미지: {image_file} ({image_file.stat().st_size:,} bytes)")

    def test_generate_multiple_images(self, image_service, tmp_path):
        """여러 슬라이드에 대해 이미지를 생성합니다."""
        slides = [
            _make_slide(title="첫 번째", content_summary="a red triangle on white background"),
            _make_slide(title="두 번째", content_summary="a green square on white background"),
        ]
        request = ImageRequest(slides=slides)
        response = image_service.generate(request, output_dir=tmp_path)

        assert len(response.images) == 2
        for img in response.images:
            path = tmp_path / f"slide_{img.slide_index}.png"
            assert path.exists()
            assert path.stat().st_size > 0
            print(f"\n  슬라이드 {img.slide_index}: {path} ({path.stat().st_size:,} bytes)")

    def test_skip_and_generate_mixed(self, image_service, tmp_path):
        """스킵 대상과 생성 대상이 섞인 경우를 테스트합니다."""
        slides = [
            _make_slide(layout_index=0, content_summary="should be skipped"),
            _make_slide(content_summary="a yellow star on dark background"),
            _make_slide(content_summary=""),
            _make_slide(content_summary="a purple diamond on light gray background"),
        ]
        request = ImageRequest(slides=slides)
        response = image_service.generate(request, output_dir=tmp_path)

        assert len(response.images) == 2
        assert response.images[0].slide_index == 1
        assert response.images[1].slide_index == 3

        for img in response.images:
            path = tmp_path / f"slide_{img.slide_index}.png"
            assert path.exists()
            print(f"\n  슬라이드 {img.slide_index}: {path} ({path.stat().st_size:,} bytes)")
