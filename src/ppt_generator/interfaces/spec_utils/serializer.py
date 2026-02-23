"""PptxSlideSpec 직렬화 유틸리티.

PptxSlideSpec/DesignSpec → JSON 문자열 변환을 담당한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from ppt_generator.interfaces.schemas import DesignSpec, PptxSlideSpec


def slide_spec_to_json(slide_spec: PptxSlideSpec) -> str:
    """단일 PptxSlideSpec을 JSON 문자열로 직렬화."""
    data = asdict(slide_spec)
    for img in data.get("images", []):
        img.pop("image_bytes", None)
    return json.dumps(data, ensure_ascii=False, indent=2)


def design_spec_to_json(design_spec: DesignSpec) -> str:
    """DesignSpec을 JSON 문자열로 직렬화."""
    data = asdict(design_spec)
    for slide in data.get("slides", []):
        for img in slide.get("images", []):
            img.pop("image_bytes", None)
    return json.dumps(data, ensure_ascii=False, indent=2)
