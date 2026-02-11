from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from google import genai
from google.genai import types

from ppt_generator.interfaces.constants import (
    GEMINI_IMAGE_ASPECT_RATIO,
    GEMINI_IMAGE_MODEL_ID,
    SKIP_IMAGE_LAYOUT_TYPES,
)
from ppt_generator.interfaces.schemas import ImageRequest, ImageResponse, ImageResult

logger = logging.getLogger(__name__)


class ImageService:
    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def generate(self, request: ImageRequest, output_dir: Path | None = None) -> ImageResponse:
        if not request.slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="ppt_images_"))
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[ImageResult] = []

        for i, slide in enumerate(request.slides):
            if not slide.image_idea or not slide.image_idea.strip():
                logger.info("슬라이드 %d: image_idea 없음, 건너뜀", i)
                continue

            if slide.layout_type in SKIP_IMAGE_LAYOUT_TYPES:
                logger.info("슬라이드 %d: layout_type=%s, 이미지 생성 건너뜀", i, slide.layout_type)
                continue

            try:
                image_path = self._generate_single(slide.image_idea, output_dir / f"slide_{i}.png")
                results.append(ImageResult(slide_index=i, image_path=str(image_path)))
            except Exception:
                logger.exception("슬라이드 %d 이미지 생성 실패", i)

        return ImageResponse(images=results)

    def _generate_single(self, prompt: str, output_path: Path) -> Path:
        response = self._client.models.generate_content(
            model=GEMINI_IMAGE_MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=GEMINI_IMAGE_ASPECT_RATIO,
                ),
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image = part.as_image()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path)
                logger.info("이미지 생성 완료: %s", output_path)
                return output_path

        raise RuntimeError("이미지 생성 결과 없음: 응답에 이미지 데이터가 없습니다.")
