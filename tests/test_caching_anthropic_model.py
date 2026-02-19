from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.di.container import CachingAnthropicModel


@pytest.fixture
def model():
    with patch("strands.models.anthropic.AnthropicModel.__init__", return_value=None):
        instance = CachingAnthropicModel(model_id="claude-test", max_tokens=1024)
        instance.config = {
            "model_id": "claude-test",
            "max_tokens": 1024,
        }
        return instance


class TestFormatRequest:
    def test_system_prompt_converted_to_cache_control_list(self, model):
        """system_prompt가 있으면 cache_control이 포함된 리스트로 변환되어야 한다."""
        messages = [{"role": "user", "content": [{"text": "hello"}]}]
        result = model.format_request(messages, system_prompt="You are helpful.")

        assert "system" in result
        assert isinstance(result["system"], list)
        assert len(result["system"]) == 1
        assert result["system"][0] == {
            "type": "text",
            "text": "You are helpful.",
            "cache_control": {"type": "ephemeral"},
        }

    def test_no_system_prompt_omits_system_field(self, model):
        """system_prompt가 없으면 system 필드가 없어야 한다."""
        messages = [{"role": "user", "content": [{"text": "hello"}]}]
        result = model.format_request(messages, system_prompt=None)

        assert "system" not in result

    def test_empty_system_prompt_omits_system_field(self, model):
        """빈 문자열 system_prompt도 system 필드를 생성하지 않아야 한다."""
        messages = [{"role": "user", "content": [{"text": "hello"}]}]
        result = model.format_request(messages, system_prompt="")

        assert "system" not in result

    def test_preserves_other_request_fields(self, model):
        """system 외의 다른 필드(model, max_tokens, messages)가 보존되어야 한다."""
        messages = [{"role": "user", "content": [{"text": "hello"}]}]
        result = model.format_request(messages, system_prompt="You are helpful.")

        assert result["model"] == "claude-test"
        assert result["max_tokens"] == 1024
        assert "messages" in result

    def test_tool_specs_passed_through(self, model):
        """tool_specs가 정상적으로 전달되어야 한다."""
        messages = [{"role": "user", "content": [{"text": "hello"}]}]
        tool_specs = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "inputSchema": {"json": {"type": "object"}},
            }
        ]
        result = model.format_request(messages, tool_specs=tool_specs, system_prompt="test")

        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "test_tool"
