from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import ScriptRequest
from ppt_generator.tools.script.service import ScriptService


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.return_value = "생성된 발표 스크립트입니다."
    return agent


@pytest.fixture
def service(mock_agent):
    return ScriptService(agent=mock_agent)


class TestScriptService:
    def test_generate_returns_script_response(self, service, mock_agent):
        request = ScriptRequest(topic="클라우드 컴퓨팅", num_slides=5)
        response = service.generate(request)

        assert response.script == "생성된 발표 스크립트입니다."
        assert response.topic == "클라우드 컴퓨팅"
        assert response.num_slides == 5

    def test_generate_calls_agent_with_formatted_prompt(self, service, mock_agent):
        request = ScriptRequest(topic="AI 트렌드", num_slides=3)
        service.generate(request)

        mock_agent.assert_called_once()
        prompt = mock_agent.call_args[0][0]
        assert "AI 트렌드" in prompt
        assert "3" in prompt

    def test_generate_raises_on_empty_topic(self, service):
        request = ScriptRequest(topic="", num_slides=5)
        with pytest.raises(ValueError, match="주제가 비어있습니다"):
            service.generate(request)

    def test_generate_raises_on_whitespace_topic(self, service):
        request = ScriptRequest(topic="   ", num_slides=5)
        with pytest.raises(ValueError, match="주제가 비어있습니다"):
            service.generate(request)

    def test_generate_converts_agent_result_to_string(self, mock_agent):
        mock_agent.return_value = 12345
        service = ScriptService(agent=mock_agent)
        request = ScriptRequest(topic="테스트", num_slides=5)
        response = service.generate(request)

        assert response.script == "12345"
