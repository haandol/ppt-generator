"""PptxSlideSpec 직렬화 유틸리티.

PptxSlideSpec/DesignSpec → JSON 문자열 변환을 담당한다.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from ppt_generator.interfaces.schemas import DesignSpec, PptxSlideSpec


def _strip_none_z_index(data: dict) -> None:
    """z_index=None인 항목을 제거하여 JSON 크기를 줄인다."""
    for key in ("textboxes", "shapes", "images"):
        for item in data.get(key, []):
            if item.get("z_index") is None:
                item.pop("z_index", None)


def _strip_none_grid_cell(data: dict) -> None:
    """grid_cell=None인 element 키를 제거하여 JSON을 깔끔하게 유지한다."""
    for key in ("textboxes", "shapes", "images"):
        for item in data.get(key, []):
            if item.get("grid_cell") is None:
                item.pop("grid_cell", None)


def _strip_empty_grid_plan(data: dict) -> None:
    """grid_plan이 None이면 키 자체를 제거한다."""
    if data.get("grid_plan") is None:
        data.pop("grid_plan", None)


def _strip_image_internals(data: dict) -> None:
    """이미지에서 내부 전용 필드를 제거한다."""
    for img in data.get("images", []):
        img.pop("image_bytes", None)
        if not img.get("image_path"):
            img.pop("image_path", None)
        if img.get("corner_radius_px") is None:
            img.pop("corner_radius_px", None)


def _strip_slide_internals(data: dict) -> None:
    """슬라이드 레벨 내부 전용 필드를 제거한다."""
    data.pop("background_image_bytes", None)
    if not data.get("background_image_src"):
        data.pop("background_image_src", None)


def slide_spec_to_json(slide_spec: PptxSlideSpec) -> str:
    """단일 PptxSlideSpec을 JSON 문자열로 직렬화."""
    data = asdict(slide_spec)
    _strip_image_internals(data)
    _strip_slide_internals(data)
    _strip_none_z_index(data)
    _strip_none_grid_cell(data)
    _strip_empty_grid_plan(data)
    return json.dumps(data, ensure_ascii=False, indent=2)


def design_spec_to_json(design_spec: DesignSpec) -> str:
    """DesignSpec을 JSON 문자열로 직렬화."""
    data = asdict(design_spec)
    for slide in data.get("slides", []):
        _strip_image_internals(slide)
        _strip_slide_internals(slide)
        _strip_none_z_index(slide)
        _strip_none_grid_cell(slide)
        _strip_empty_grid_plan(slide)
    return json.dumps(data, ensure_ascii=False, indent=2)
