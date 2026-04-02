"""Design 핸들러 공통 의존성 번들."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ppt_generator.tools.design.review_service import DesignReviewService
    from ppt_generator.tools.design.service import DesignService
    from ppt_generator.tools.project.service import ProjectService
    from ppt_generator.tools.slides.service import SlidesService


@dataclass(frozen=True)
class DesignDeps:
    """Design 도구 핸들러에 주입되는 의존성 번들."""

    project_service: ProjectService
    design_service_factory: Callable[[str, str], DesignService]
    slides_service: SlidesService | None = None
    review_service_factory: Callable[[], DesignReviewService] | None = None
