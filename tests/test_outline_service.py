import json
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import OutlineRequest
from ppt_generator.tools.outline.service import OutlineService

VALID_OUTLINE_JSON = json.dumps(
    {
        "slides": [
            {
                "title": "클라우드 컴퓨팅 트렌드",
                "bullets": ["핵심 트렌드 소개", "시장 현황"],
                "image_idea": "클라우드 인프라 개념도",
                "layout_type": "title",
                "speaker_notes": "안녕하세요, 오늘은 클라우드 컴퓨팅 트렌드에 대해 발표하겠습니다.",
            },
            {
                "title": "멀티클라우드 전략",
                "bullets": ["AWS, Azure, GCP 비교", "하이브리드 접근"],
                "image_idea": "멀티클라우드 아키텍처 다이어그램",
                "layout_type": "text_image",
                "speaker_notes": "첫 번째 트렌드는 멀티클라우드 전략입니다.",
            },
            {
                "title": "감사합니다",
                "bullets": ["Q&A"],
                "image_idea": "",
                "layout_type": "closing",
                "speaker_notes": "이상으로 발표를 마치겠습니다.",
            },
        ]
    },
    ensure_ascii=False,
)


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.return_value = VALID_OUTLINE_JSON
    return agent


@pytest.fixture
def service(mock_agent):
    return OutlineService(agent=mock_agent)


class TestOutlineService:
    def test_generate_returns_outline_response(self, service):
        request = OutlineRequest(script="발표 스크립트 내용입니다.")
        response = service.generate(request)

        assert len(response.slides) == 3
        assert response.slides[0].title == "클라우드 컴퓨팅 트렌드"
        assert response.slides[0].layout_type == "title"
        assert response.slides[1].bullets == ["AWS, Azure, GCP 비교", "하이브리드 접근"]
        assert response.slides[2].layout_type == "closing"

    def test_generate_calls_agent_with_script(self, service, mock_agent):
        request = OutlineRequest(script="테스트 스크립트")
        service.generate(request)

        mock_agent.assert_called_once()
        prompt = mock_agent.call_args[0][0]
        assert "테스트 스크립트" in prompt

    def test_generate_raises_on_empty_script(self, service):
        request = OutlineRequest(script="")
        with pytest.raises(ValueError, match="스크립트가 비어있습니다"):
            service.generate(request)

    def test_generate_raises_on_whitespace_script(self, service):
        request = OutlineRequest(script="   ")
        with pytest.raises(ValueError, match="스크립트가 비어있습니다"):
            service.generate(request)

    def test_generate_parses_json_in_code_block(self, mock_agent):
        mock_agent.return_value = f"여기 결과입니다:\n```json\n{VALID_OUTLINE_JSON}\n```"
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(script="스크립트 내용")
        response = service.generate(request)

        assert len(response.slides) == 3

    def test_generate_raises_on_invalid_json(self, mock_agent):
        mock_agent.return_value = "이것은 JSON이 아닙니다"
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(script="스크립트 내용")

        with pytest.raises(ValueError, match="유효하지 않은 JSON"):
            service.generate(request)

    def test_generate_raises_on_missing_slides_key(self, mock_agent):
        mock_agent.return_value = '{"data": []}'
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(script="스크립트 내용")

        with pytest.raises(ValueError, match="slides"):
            service.generate(request)

    def test_generate_falls_back_unknown_layout_type(self, mock_agent):
        data = {
            "slides": [
                {
                    "title": "테스트",
                    "bullets": [],
                    "image_idea": "",
                    "layout_type": "unknown_type",
                    "speaker_notes": "",
                }
            ]
        }
        mock_agent.return_value = json.dumps(data)
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(script="스크립트 내용")
        response = service.generate(request)

        assert response.slides[0].layout_type == "text_only"

    def test_generate_handles_missing_optional_fields(self, mock_agent):
        data = {"slides": [{"title": "최소 슬라이드"}]}
        mock_agent.return_value = json.dumps(data)
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(script="스크립트 내용")
        response = service.generate(request)

        slide = response.slides[0]
        assert slide.title == "최소 슬라이드"
        assert slide.bullets == []
        assert slide.image_idea == ""
        assert slide.layout_type == "text_only"
        assert slide.speaker_notes == ""
