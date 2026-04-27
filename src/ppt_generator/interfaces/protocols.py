"""서비스 팩토리 및 콜백의 타입 정의.

순환 임포트를 피하기 위해 interfaces 레이어에 Protocol을 정의한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ppt_generator.interfaces.schemas import DesignSpec, PptxSlideSpec


class DesignServiceLike(Protocol):
    """DesignService의 공개 인터페이스."""

    def generate_single_slide(
        self, slide_outline, design_summary=None, **kwargs
    ) -> PptxSlideSpec: ...

    @property
    def last_token_usage(self) -> dict[str, int]: ...


class DesignServiceFactory(Protocol):
    """(slide_type, budget_tokens) → DesignService 팩토리."""

    def __call__(
        self, slide_type: str = "content", budget_tokens: int = 4096
    ) -> DesignServiceLike: ...


class ReviewServiceLike(Protocol):
    """DesignReviewService의 공개 인터페이스."""

    def review(self, spec: PptxSlideSpec, slide_index: int): ...

    @property
    def last_token_usage(self) -> dict[str, int]: ...


class ReviewServiceFactory(Protocol):
    """() → DesignReviewService 팩토리."""

    def __call__(self) -> ReviewServiceLike: ...


class VisualQAServiceFactory(Protocol):
    """() → VisualQAService 팩토리."""

    def __call__(self): ...


class SaveSlideFn(Protocol):
    """디자인 스펙 슬라이드 저장 콜백."""

    def __call__(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None: ...


class LoadDesignSpecFn(Protocol):
    """디자인 스펙 전체 로드 콜백."""

    def __call__(self, project_dir: Path) -> DesignSpec: ...
