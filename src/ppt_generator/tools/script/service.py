from strands import Agent

from ppt_generator.interfaces.constants import SCRIPT_USER_PROMPT_TEMPLATE
from ppt_generator.interfaces.schemas import ScriptRequest, ScriptResponse


class ScriptService:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def generate(self, request: ScriptRequest) -> ScriptResponse:
        if not request.topic.strip():
            raise ValueError("주제가 비어있습니다.")

        prompt = SCRIPT_USER_PROMPT_TEMPLATE.format(
            topic=request.topic,
            num_slides=request.num_slides,
        )
        result = str(self._agent(prompt))

        return ScriptResponse(
            script=result,
            topic=request.topic,
            num_slides=request.num_slides,
        )
