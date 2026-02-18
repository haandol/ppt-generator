import json
from pathlib import Path

from strands import Agent
from strands.models.bedrock import BedrockModel

from ppt_generator.interfaces.constants import (
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
        self._script_service: ScriptService | None = None
        self._outline_service: OutlineService | None = None
        self._export_service: ExportService | None = None
        self._slides_service: SlidesService | None = None
        self._design_service: DesignService | None = None
        self._project_service: ProjectService | None = None

    def _create_bedrock_model(self) -> BedrockModel:
        return BedrockModel(
            model_id=BEDROCK_MODEL_ID,
            region_name=BEDROCK_REGION,
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

    def _create_script_agent(self) -> Agent:
        model = BedrockModel(
            model_id=BEDROCK_OUTLINE_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=1.0,
            max_tokens=BEDROCK_SCRIPT_MAX_TOKENS,
            additional_request_fields={
                "thinking": {
                    "type": "adaptive",
                },
                "output_config": {
                    "effort": "high",
                },
            },
            additional_args=self._build_json_schema_args(SCRIPT_JSON_SCHEMA, "script_output"),
        )
        return Agent(model=model, system_prompt=SCRIPT_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_outline_agent(self) -> Agent:
        model = BedrockModel(
            model_id=BEDROCK_OUTLINE_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=1.0,
            max_tokens=BEDROCK_OUTLINE_MAX_TOKENS,
            additional_request_fields={
                "thinking": {
                    "type": "adaptive",
                },
                "output_config": {
                    "effort": "high",
                },
            },
            additional_args=self._build_json_schema_args(OUTLINE_JSON_SCHEMA, "outline_output"),
        )
        return Agent(model=model, system_prompt=OUTLINE_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_design_agent(self) -> Agent:
        model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=DESIGN_SPEC_SYSTEM_PROMPT, callback_handler=None, tools=[])

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
