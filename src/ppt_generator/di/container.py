import os
from pathlib import Path

import boto3
from google import genai
from strands import Agent
from strands.models.bedrock import BedrockModel

from ppt_generator.interfaces.constants import (
    BEDROCK_MAX_TOKENS,
    BEDROCK_MODEL_ID,
    BEDROCK_OUTLINE_MAX_TOKENS,
    BEDROCK_OUTLINE_MODEL_ID,
    BEDROCK_REGION,
    BEDROCK_SCRIPT_MAX_TOKENS,
    BEDROCK_TEMPERATURE,
    OUTLINE_FREEFORM_SYSTEM_PROMPT,
    PPTX_TEMPLATE_PATH,
    SCRIPT_SYSTEM_PROMPT,
    SLIDES_MODIFY_SYSTEM_PROMPT,
    SLIDES_SYSTEM_PROMPT,
)
from ppt_generator.tools.images.service import ImageService
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
        self._image_service: ImageService | None = None
        self._export_service: ExportService | None = None
        self._slides_service: SlidesService | None = None
        self._project_service: ProjectService | None = None

    def _create_bedrock_model(self) -> BedrockModel:
        return BedrockModel(
            model_id=BEDROCK_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=BEDROCK_TEMPERATURE,
            max_tokens=BEDROCK_MAX_TOKENS,
        )

    def _create_script_agent(self) -> Agent:
        model = BedrockModel(
            model_id=BEDROCK_OUTLINE_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=BEDROCK_TEMPERATURE,
            max_tokens=BEDROCK_SCRIPT_MAX_TOKENS,
        )
        return Agent(model=model, system_prompt=SCRIPT_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_outline_agent(self) -> Agent:
        model = BedrockModel(
            model_id=BEDROCK_OUTLINE_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=BEDROCK_TEMPERATURE,
            max_tokens=BEDROCK_OUTLINE_MAX_TOKENS,
        )
        return Agent(model=model, system_prompt=OUTLINE_FREEFORM_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_slides_agent(self) -> Agent:
        model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=SLIDES_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_slides_modify_agent(self) -> Agent:
        model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=SLIDES_MODIFY_SYSTEM_PROMPT, callback_handler=None, tools=[])

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
    def image_service(self) -> ImageService:
        if self._image_service is None:
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            self._image_service = ImageService(client=client)
        return self._image_service

    @property
    def export_service(self) -> ExportService:
        if self._export_service is None:
            template_path = self._project_root / PPTX_TEMPLATE_PATH
            self._export_service = ExportService(
                slides_service=self.slides_service,
                template_path=template_path,
            )
        return self._export_service

    @property
    def slides_service(self) -> SlidesService:
        if self._slides_service is None:
            agent = self._create_slides_agent()
            modify_agent = self._create_slides_modify_agent()
            self._slides_service = SlidesService(agent=agent, modify_agent=modify_agent)
        return self._slides_service

    @property
    def project_service(self) -> ProjectService:
        if self._project_service is None:
            self._project_service = ProjectService(slides_service=self.slides_service)
        return self._project_service
