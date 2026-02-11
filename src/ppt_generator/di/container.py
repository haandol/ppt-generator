from pathlib import Path

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel

from ppt_generator.interfaces.constants import (
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
    BEDROCK_TEMPERATURE,
    OUTLINE_FREEFORM_SYSTEM_PROMPT,
    OUTLINE_SYSTEM_PROMPT,
    PPTX_TEMPLATE_PATH,
    SCRIPT_SYSTEM_PROMPT,
    SLIDES_SYSTEM_PROMPT,
    TITAN_IMAGE_REGION,
)
from ppt_generator.tools.images.service import ImageService
from ppt_generator.tools.outline.service import OutlineService
from ppt_generator.tools.pptx.service import PptxService
from ppt_generator.tools.script.service import ScriptService
from ppt_generator.tools.slides.service import SlidesService


class DIContainer:
    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root or Path(__file__).resolve().parents[3]
        self._script_service: ScriptService | None = None
        self._outline_service: OutlineService | None = None
        self._image_service: ImageService | None = None
        self._pptx_service: PptxService | None = None
        self._slides_service: SlidesService | None = None

    def _create_bedrock_model(self) -> BedrockModel:
        return BedrockModel(
            model_id=BEDROCK_MODEL_ID,
            region_name=BEDROCK_REGION,
            temperature=BEDROCK_TEMPERATURE,
        )

    def _create_script_agent(self) -> Agent:
        model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=SCRIPT_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_outline_agent(self) -> Agent:
        model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=OUTLINE_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_freeform_outline_agent(self) -> Agent:
        model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=OUTLINE_FREEFORM_SYSTEM_PROMPT, callback_handler=None, tools=[])

    def _create_slides_agent(self) -> Agent:
        model = self._create_bedrock_model()
        return Agent(model=model, system_prompt=SLIDES_SYSTEM_PROMPT, callback_handler=None, tools=[])

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
            freeform_agent = self._create_freeform_outline_agent()
            self._outline_service = OutlineService(agent=agent, freeform_agent=freeform_agent)
        return self._outline_service

    @property
    def image_service(self) -> ImageService:
        if self._image_service is None:
            client = boto3.client("bedrock-runtime", region_name=TITAN_IMAGE_REGION)
            self._image_service = ImageService(bedrock_runtime=client)
        return self._image_service

    @property
    def pptx_service(self) -> PptxService:
        if self._pptx_service is None:
            template_path = self._project_root / PPTX_TEMPLATE_PATH
            self._pptx_service = PptxService(template_path=template_path)
        return self._pptx_service

    @property
    def slides_service(self) -> SlidesService:
        if self._slides_service is None:
            agent = self._create_slides_agent()
            self._slides_service = SlidesService(agent=agent)
        return self._slides_service
