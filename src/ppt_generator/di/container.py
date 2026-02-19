import json
import os
from pathlib import Path
from typing import Any

from botocore.config import Config as BotocoreConfig
from strands import Agent
from strands.models.bedrock import BedrockModel

from ppt_generator.interfaces.constants import (
    ANTHROPIC_MODEL_ID,
    ANTHROPIC_OUTLINE_MODEL_ID,
    BEDROCK_MAX_TOKENS,
    BEDROCK_MODEL_ID,
    BEDROCK_OUTLINE_MAX_TOKENS,
    BEDROCK_OUTLINE_MODEL_ID,
    BEDROCK_REGION,
    BEDROCK_SCRIPT_MAX_TOKENS,
    DESIGN_SPEC_SYSTEM_PROMPT,
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


class DIContainer:
    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[3]
        self._provider = self._resolve_provider()
        self._script_service: ScriptService | None = None
        self._outline_service: OutlineService | None = None
        self._export_service: ExportService | None = None
        self._slides_service: SlidesService | None = None
        self._design_service: DesignService | None = None
        self._project_service: ProjectService | None = None

    @staticmethod
    def _resolve_provider() -> str:
        explicit = os.environ.get("LLM_PROVIDER", "").lower()
        if explicit in ("anthropic", "bedrock"):
            return explicit
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
        return "bedrock"

    # ---- Bedrock model helpers ----

    @staticmethod
    def _build_client_config() -> BotocoreConfig:
        return BotocoreConfig(
            auth_scheme_preference=["httpBearerAuth", "sigv4"],
        )

    @staticmethod
    def _build_json_schema_args(schema: dict, name: str) -> dict:
        return {
            "outputConfig": {
                "textFormat": {
                    "type": "json_schema",
                    "structure": {
                        "jsonSchema": {
                            "schema": json.dumps(schema),
                            "name": name,
                        },
                    },
                },
            },
        }

    def _create_bedrock_model(self) -> BedrockModel:
        return BedrockModel(
            model_id=BEDROCK_MODEL_ID,
            region_name=BEDROCK_REGION,
            boto_client_config=self._build_client_config(),
            temperature=1.0,
            max_tokens=BEDROCK_MAX_TOKENS,
            additional_request_fields={
                "thinking": {
                    "type": "adaptive",
                },
                "output_config": {
                    "effort": "high",
                },
            },
        )

    def _create_bedrock_outline_model(
        self,
        max_tokens: int,
        json_schema: dict | None = None,
        json_schema_name: str | None = None,
    ) -> BedrockModel:
        additional_args: dict[str, Any] = {}
        if json_schema and json_schema_name:
            additional_args = self._build_json_schema_args(json_schema, json_schema_name)
        return BedrockModel(
            model_id=BEDROCK_OUTLINE_MODEL_ID,
            region_name=BEDROCK_REGION,
            boto_client_config=self._build_client_config(),
            temperature=1.0,
            max_tokens=max_tokens,
            additional_request_fields={
                "thinking": {
                    "type": "adaptive",
                },
                "output_config": {
                    "effort": "high",
                },
            },
            additional_args=additional_args,
        )

    # ---- Anthropic model helpers ----

    def _create_anthropic_model(self) -> Any:
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(
            model_id=ANTHROPIC_MODEL_ID,
            max_tokens=BEDROCK_MAX_TOKENS,
            params={
                "temperature": 1.0,
                "thinking": {
                    "type": "adaptive",
                },
                "output_config": {
                    "effort": "high",
                },
            },
        )

    def _create_anthropic_outline_model(
        self,
        max_tokens: int,
        json_schema: dict | None = None,
        json_schema_name: str | None = None,
    ) -> Any:
        from strands.models.anthropic import AnthropicModel

        params: dict[str, Any] = {
            "temperature": 1.0,
            "thinking": {
                "type": "adaptive",
            },
            "output_config": {
                "effort": "high",
            },
        }
        if json_schema and json_schema_name:
            params["output_config"] = {
                **params["output_config"],
                "format": {
                    "type": "json_schema",
                    "schema": json_schema,
                    "name": json_schema_name,
                },
            }
        return AnthropicModel(
            model_id=ANTHROPIC_OUTLINE_MODEL_ID,
            max_tokens=max_tokens,
            params=params,
        )

    # ---- Agent creation (provider-aware) ----

    def _create_script_agent(self) -> Agent:
        if self._provider == "anthropic":
            model = self._create_anthropic_outline_model(
                max_tokens=BEDROCK_SCRIPT_MAX_TOKENS,
                json_schema=SCRIPT_JSON_SCHEMA,
                json_schema_name="script_output",
            )
        else:
            model = self._create_bedrock_outline_model(
                max_tokens=BEDROCK_SCRIPT_MAX_TOKENS,
                json_schema=SCRIPT_JSON_SCHEMA,
                json_schema_name="script_output",
            )
        return Agent(model=model, system_prompt=SCRIPT_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_outline_agent(self) -> Agent:
        if self._provider == "anthropic":
            model = self._create_anthropic_outline_model(
                max_tokens=BEDROCK_OUTLINE_MAX_TOKENS,
                json_schema=OUTLINE_JSON_SCHEMA,
                json_schema_name="outline_output",
            )
        else:
            model = self._create_bedrock_outline_model(
                max_tokens=BEDROCK_OUTLINE_MAX_TOKENS,
                json_schema=OUTLINE_JSON_SCHEMA,
                json_schema_name="outline_output",
            )
        return Agent(model=model, system_prompt=OUTLINE_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_design_agent(self) -> Agent:
        if self._provider == "anthropic":
            model = self._create_anthropic_model()
        else:
            model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=DESIGN_SPEC_SYSTEM_PROMPT, callback_handler=None, tools=[])

    # ---- Service properties (lazy init) ----

    @property
    def script_service(self) -> ScriptService:
        if self._script_service is None:
            agent = self._create_script_agent()
            self._script_service = ScriptService(agent=agent)
        return self._script_service

    @property
    def outline_service(self) -> OutlineService:
        if self._outline_service is None:
            agent = self._create_outline_agent()
            self._outline_service = OutlineService(agent=agent)
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
            agent = self._create_design_agent()
            self._design_service = DesignService(agent=agent)
        return self._design_service

    @property
    def project_service(self) -> ProjectService:
        if self._project_service is None:
            self._project_service = ProjectService()
        return self._project_service
