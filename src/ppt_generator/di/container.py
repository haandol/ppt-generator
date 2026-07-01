"""의존성 주입 컨테이너.

LLM 호출을 클라이언트로 오프로딩한 뒤로, 서버는 모델·프로바이더 SDK 를
갖지 않는다. 컨테이너는 결정론적 서비스(프롬프트 조립 + 출력 후처리 + 파일 IO)만
구성해 보관한다. 각 서비스는 prepare/ingest 두 단계를 노출한다.
"""

from pathlib import Path

from ppt_generator.tools.design.review_service import DesignReviewService
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.pptx_import.service import ImportService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService
from ppt_generator.tools.visual_qa.service import VisualQAService

__all__ = ["DIContainer"]


class DIContainer:
    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[3]
        self._outline_service: OutlineService | None = None
        self._export_service: ExportService | None = None
        self._slides_service: SlidesService | None = None
        self._project_service: ProjectService | None = None
        self._import_service: ImportService | None = None
        self._design_service: DesignService | None = None
        self._review_service: DesignReviewService | None = None
        self._visual_qa_service: VisualQAService | None = None

    # ---- Service properties (lazy init) ----

    @property
    def outline_service(self) -> OutlineService:
        if self._outline_service is None:
            self._outline_service = OutlineService()
        return self._outline_service

    @property
    def export_service(self) -> ExportService:
        if self._export_service is None:
            self._export_service = ExportService()
        return self._export_service

    @property
    def slides_service(self) -> SlidesService:
        if self._slides_service is None:
            self._slides_service = SlidesService()
        return self._slides_service

    @property
    def design_service(self) -> DesignService:
        if self._design_service is None:
            self._design_service = DesignService()
        return self._design_service

    @property
    def review_service(self) -> DesignReviewService:
        if self._review_service is None:
            self._review_service = DesignReviewService()
        return self._review_service

    @property
    def visual_qa_service(self) -> VisualQAService:
        if self._visual_qa_service is None:
            self._visual_qa_service = VisualQAService()
        return self._visual_qa_service

    @property
    def import_service(self) -> ImportService:
        if self._import_service is None:
            self._import_service = ImportService()
        return self._import_service

    @property
    def project_service(self) -> ProjectService:
        if self._project_service is None:
            self._project_service = ProjectService()
        return self._project_service
