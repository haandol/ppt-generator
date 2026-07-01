"""Design 핸들러 공통 의존성 번들."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ppt_generator.tools.design.review_service import DesignReviewService
    from ppt_generator.tools.design.service import DesignService
    from ppt_generator.tools.project.service import ProjectService
    from ppt_generator.tools.slides.service import SlidesService


@dataclass(frozen=True)
class DesignDeps:
    """Design 도구 핸들러에 주입되는 의존성 번들.

    LLM 오프로딩 후로 서비스는 상태 없는(stateless) 결정론적 컴포넌트이므로
    팩토리 대신 단일 인스턴스를 공유한다.
    """

    project_service: ProjectService
    design_service: DesignService
    slides_service: SlidesService | None = None
    review_service: DesignReviewService | None = None
