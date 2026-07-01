import os
from pathlib import Path
from typing import TYPE_CHECKING

from strands import Agent

from ppt_generator.di.model_factory import (
    create_anthropic_design_model,
    create_anthropic_outline_model,
    create_anthropic_review_model,
    create_anthropic_visual_qa_analysis_model,
    create_anthropic_visual_qa_model,
    create_bedrock_design_model,
    create_bedrock_outline_model,
    create_bedrock_review_model,
    create_bedrock_visual_qa_analysis_model,
    create_bedrock_visual_qa_model,
)
from ppt_generator.interfaces.constants import (
    BACKFILL_DESIGN_DOC_SYSTEM_PROMPT,
    BEDROCK_OUTLINE_MAX_TOKENS,
    DESIGN_REVIEW_SYSTEM_PROMPT,
    DESIGN_SPEC_SYSTEM_PROMPTS,
    OUTLINE_SYSTEM_PROMPT,
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.pptx_import.service import ImportService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService

if TYPE_CHECKING:
    from ppt_generator.tools.design.review_service import DesignReviewService
    from ppt_generator.tools.visual_qa.service import VisualQAService

__all__ = ["DIContainer"]


class DIContainer:
    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[3]
        self._provider = self._resolve_provider()
        self._outline_service: OutlineService | None = None
        self._export_service: ExportService | None = None
        self._slides_service: SlidesService | None = None
        self._project_service: ProjectService | None = None
        self._import_service: ImportService | None = None

    @staticmethod
    def _resolve_provider() -> str:
        explicit = os.environ.get("LLM_PROVIDER", "").lower()
        if explicit in ("anthropic", "bedrock"):
            return explicit
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "bedrock"

    # ---- Agent creation (provider-aware) ----

    def _create_agent(self, *, model, prompt_text: str) -> Agent:
        """Agent를 생성한다."""
        return Agent(
            model=model,
            system_prompt=prompt_text,
            callback_handler=None,
            tools=[],
            retry_strategy=None,
        )

    def _create_outline_agent(self) -> Agent:
        model = (
            create_anthropic_outline_model
            if self._provider == "anthropic"
            else create_bedrock_outline_model
        )(max_tokens=BEDROCK_OUTLINE_MAX_TOKENS)
        return self._create_agent(model=model, prompt_text=OUTLINE_SYSTEM_PROMPT)

    def _create_visual_qa_analysis_agent(self) -> Agent:
        model = (
            create_anthropic_visual_qa_analysis_model
            if self._provider == "anthropic"
            else create_bedrock_visual_qa_analysis_model
        )()
        return self._create_agent(
            model=model, prompt_text=VISUAL_QA_ANALYSIS_SYSTEM_PROMPT
        )

    def _create_visual_qa_fix_agent(self) -> Agent:
        model = (
            create_anthropic_visual_qa_model
            if self._provider == "anthropic"
            else create_bedrock_visual_qa_model
        )()
        return self._create_agent(model=model, prompt_text=VISUAL_QA_FIX_SYSTEM_PROMPT)

    def _create_design_agent(
        self, slide_type: str = "content", effort: str = "medium"
    ) -> Agent:
        prompt_text = DESIGN_SPEC_SYSTEM_PROMPTS.get(
            slide_type, DESIGN_SPEC_SYSTEM_PROMPTS["content"]
        )
        model = (
            create_anthropic_design_model
            if self._provider == "anthropic"
            else create_bedrock_design_model
        )(effort=effort)
        return self._create_agent(model=model, prompt_text=prompt_text)

    # ---- Service properties (lazy init) ----

    @property
    def outline_service(self) -> OutlineService:
        if self._outline_service is None:
            self._outline_service = OutlineService(agent=self._create_outline_agent())
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

    def _create_review_agent(self) -> Agent:
        model = (
            create_anthropic_review_model
            if self._provider == "anthropic"
            else create_bedrock_review_model
        )()
        return self._create_agent(model=model, prompt_text=DESIGN_REVIEW_SYSTEM_PROMPT)

    def create_review_service(self) -> "DesignReviewService":
        """DesignReviewService 인스턴스를 생성한다."""
        from ppt_generator.tools.design.review_service import DesignReviewService

        return DesignReviewService(agent=self._create_review_agent())

    def _create_backfill_agent(self) -> Agent:
        """imported 슬라이드의 design_doc 추론용 agent (review 모델 재사용)."""
        model = (
            create_anthropic_review_model
            if self._provider == "anthropic"
            else create_bedrock_review_model
        )()
        return self._create_agent(
            model=model, prompt_text=BACKFILL_DESIGN_DOC_SYSTEM_PROMPT
        )

    def create_design_service(
        self, slide_type: str = "content", effort: str = "medium"
    ) -> DesignService:
        """새 Agent를 포함한 DesignService 인스턴스를 생성한다."""
        return DesignService(
            agent=self._create_design_agent(slide_type=slide_type, effort=effort),
            backfill_agent=self._create_backfill_agent(),
        )

    def create_visual_qa_service(self) -> "VisualQAService":
        """VisualQAService 인스턴스를 생성한다 (Playwright 필요)."""
        from ppt_generator.tools.visual_qa.service import VisualQAService

        return VisualQAService(
            analysis_agent_factory=self._create_visual_qa_analysis_agent,
            fix_agent_factory=self._create_visual_qa_fix_agent,
        )

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
