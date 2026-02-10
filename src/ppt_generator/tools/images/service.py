from __future__ import annotations

import base64
import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ppt_generator.interfaces.constants import (
    SKIP_IMAGE_LAYOUT_TYPES,
    TITAN_IMAGE_CFG_SCALE,
    TITAN_IMAGE_HEIGHT,
    TITAN_IMAGE_MODEL_ID,
    TITAN_IMAGE_WIDTH,
)
from ppt_generator.interfaces.schemas import ImageRequest, ImageResponse, ImageResult

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

logger = logging.getLogger(__name__)


class ImageService:
    def __init__(self, bedrock_runtime: BedrockRuntimeClient) -> None:
        self._client = bedrock_runtime

    def generate(self, request: ImageRequest) -> ImageResponse:
        if not request.slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        output_dir = Path(tempfile.mkdtemp(prefix="ppt_images_"))
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
        body = json.dumps(
            {
                "taskType": "TEXT_IMAGE",
                "textToImageParams": {"text": prompt},
                "imageGenerationConfig": {
                    "numberOfImages": 1,
                    "width": TITAN_IMAGE_WIDTH,
                    "height": TITAN_IMAGE_HEIGHT,
                    "cfgScale": TITAN_IMAGE_CFG_SCALE,
                },
            }
        )

        response = self._client.invoke_model(
            modelId=TITAN_IMAGE_MODEL_ID,
            accept="application/json",
            contentType="application/json",
            body=body,
        )

        result = json.loads(response["body"].read())

        if not result.get("images"):
            raise RuntimeError(f"이미지 생성 결과 없음: {result.get('error', 'unknown')}")

        image_data = base64.b64decode(result["images"][0])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)

        logger.info("이미지 생성 완료: %s", output_path)
        return output_path
