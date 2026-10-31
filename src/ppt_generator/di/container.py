"""의존성 주입 컨테이너.

LLM 호출을 클라이언트로 오프로딩한 뒤로, 서버는 모델·프로바이더 SDK 를
갖지 않는다. 컨테이너는 결정론적 서비스(프롬프트 조립 + 출력 후처리 + 파일 IO)만
구성해 보관한다. 각 서비스는 prepare/ingest 두 단계를 노출한다.
"""

from functools import cached_property
from pathlib import Path

from ppt_generator.tools.design.review_service import DesignReviewService
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.pptx_import.service import ImportService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.script.service import SpeakerScriptService
from ppt_generator.tools.slides.service import SlidesService
from ppt_generator.tools.visual_qa.service import VisualQAService

__all__ = ["DIContainer"]


class DIContainer:
    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[3]

    # ---- Service properties (lazy init) ----

    @cached_property
    def outline_service(self) -> OutlineService:
        return OutlineService()

    @cached_property
    def export_service(self) -> ExportService:
        return ExportService()

    @cached_property
    def slides_service(self) -> SlidesService:
        return SlidesService()

    @cached_property
    def design_service(self) -> DesignService:
        return DesignService()

    @cached_property
    def review_service(self) -> DesignReviewService:
        return DesignReviewService()

    @cached_property
    def visual_qa_service(self) -> VisualQAService:
        return VisualQAService()

    @cached_property
    def import_service(self) -> ImportService:
        return ImportService()

    @cached_property
    def script_service(self) -> SpeakerScriptService:
        return SpeakerScriptService()

    @cached_property
    def project_service(self) -> ProjectService:
        return ProjectService()
