import os
from pathlib import Path

from strands import Agent

from ppt_generator.di.model_factory import (
    CachingAnthropicModel,
    create_anthropic_design_model,
    create_anthropic_outline_model,
    create_bedrock_design_model,
    create_bedrock_outline_model,
)
from ppt_generator.interfaces.constants import (
    BEDROCK_OUTLINE_MAX_TOKENS,
    BEDROCK_SCRIPT_MAX_TOKENS,
    DESIGN_SPEC_SYSTEM_PROMPTS,
    OUTLINE_JSON_SCHEMA,
    OUTLINE_SYSTEM_PROMPT,
    SCRIPT_JSON_SCHEMA,
    SCRIPT_SYSTEM_PROMPT,
)
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.script.service import ScriptService
from ppt_generator.tools.slides.service import SlidesService

# Re-export for backward compatibility
__all__ = ["CachingAnthropicModel", "DIContainer"]


class DIContainer:
    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[3]
        self._provider = self._resolve_provider()
        self._script_service: ScriptService | None = None
        self._outline_service: OutlineService | None = None
        self._export_service: ExportService | None = None
        self._slides_service: SlidesService | None = None
        self._project_service: ProjectService | None = None

    @staticmethod
    def _resolve_provider() -> str:
        explicit = os.environ.get("LLM_PROVIDER", "").lower()
        if explicit in ("anthropic", "bedrock"):
            return explicit
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "bedrock"

    # ---- Agent creation (provider-aware) ----

    def _create_script_agent(self) -> Agent:
        if self._provider == "anthropic":
            model = create_anthropic_outline_model(
                max_tokens=BEDROCK_SCRIPT_MAX_TOKENS,
                json_schema=SCRIPT_JSON_SCHEMA,
                json_schema_name="script_output",
            )
        else:
            model = create_bedrock_outline_model(
                max_tokens=BEDROCK_SCRIPT_MAX_TOKENS,
                json_schema=SCRIPT_JSON_SCHEMA,
                json_schema_name="script_output",
            )
        return Agent(model=model, system_prompt=SCRIPT_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_outline_agent(self) -> Agent:
        if self._provider == "anthropic":
            model = create_anthropic_outline_model(
                max_tokens=BEDROCK_OUTLINE_MAX_TOKENS,
                json_schema=OUTLINE_JSON_SCHEMA,
                json_schema_name="outline_output",
            )
        else:
            model = create_bedrock_outline_model(
                max_tokens=BEDROCK_OUTLINE_MAX_TOKENS,
                json_schema=OUTLINE_JSON_SCHEMA,
                json_schema_name="outline_output",
            )
        return Agent(model=model, system_prompt=OUTLINE_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_design_agent(self, thinking_effort: str, slide_type: str = "content") -> Agent:
        if self._provider == "anthropic":
            model = create_anthropic_design_model(thinking_effort=thinking_effort)
        else:
            model = create_bedrock_design_model(thinking_effort=thinking_effort)
        system_prompt = DESIGN_SPEC_SYSTEM_PROMPTS.get(slide_type, DESIGN_SPEC_SYSTEM_PROMPTS["content"])
        return Agent(model=model, system_prompt=system_prompt, callback_handler=None, tools=[])

    # ---- Service properties (lazy init) ----

    @property
    def script_service(self) -> ScriptService:
        if self._script_service is None:
            self._script_service = ScriptService(agent=self._create_script_agent())
        return self._script_service

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

    def create_design_service(self, thinking_effort: str, slide_type: str = "content") -> DesignService:
        """새 Agent를 포함한 DesignService 인스턴스를 생성한다."""
        return DesignService(agent=self._create_design_agent(thinking_effort=thinking_effort, slide_type=slide_type))

    @property
    def project_service(self) -> ProjectService:
        if self._project_service is None:
            self._project_service = ProjectService()
        return self._project_service
