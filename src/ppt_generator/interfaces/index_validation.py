"""공개 1-based 슬라이드 인덱스 검증."""

from __future__ import annotations


def require_positive_slide_index(slide_index: int) -> None:
    """파일 I/O 전에 1-based 양수 인덱스를 강제한다."""
    if slide_index < 1:
        raise ValueError(f"slide_index must be >= 1: {slide_index}")
