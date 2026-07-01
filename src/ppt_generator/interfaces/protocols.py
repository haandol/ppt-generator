"""서비스 및 콜백의 타입 정의.

순환 임포트를 피하기 위해 interfaces 레이어에 Protocol을 정의한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ppt_generator.interfaces.schemas import DesignSpec, PptxSlideSpec


class SaveSlideFn(Protocol):
    """디자인 스펙 슬라이드 저장 콜백."""

    def __call__(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None: ...


class LoadDesignSpecFn(Protocol):
    """디자인 스펙 전체 로드 콜백."""

    def __call__(self, project_dir: Path) -> DesignSpec: ...
