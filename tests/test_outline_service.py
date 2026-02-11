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
                "speaker_notes": "",
            },
            {
                "title": "멀티클라우드 전략",
                "bullets": ["AWS, Azure, GCP 비교", "하이브리드 접근"],
                "image_idea": "멀티클라우드 아키텍처 다이어그램",
                "layout_type": "text_image",
                "speaker_notes": "",
            },
            {
                "title": "감사합니다",
                "bullets": ["Q&A"],
                "image_idea": "",
                "layout_type": "closing",
                "speaker_notes": "",
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
        request = OutlineRequest(topic="클라우드 컴퓨팅 트렌드", num_slides=5)
        response = service.generate(request)

        assert len(response.slides) == 3
        assert response.slides[0].title == "클라우드 컴퓨팅 트렌드"
        assert response.slides[0].layout_type == "title"
        assert response.slides[1].bullets == ["AWS, Azure, GCP 비교", "하이브리드 접근"]
        assert response.slides[2].layout_type == "closing"

    def test_generate_calls_agent_with_topic(self, service, mock_agent):
        request = OutlineRequest(topic="테스트 주제", num_slides=5)
        service.generate(request)

        mock_agent.assert_called_once()
        prompt = mock_agent.call_args[0][0]
        assert "테스트 주제" in prompt

    def test_generate_raises_on_empty_topic(self, service):
        request = OutlineRequest(topic="", num_slides=5)
        with pytest.raises(ValueError, match="주제가 비어있습니다"):
            service.generate(request)

    def test_generate_raises_on_whitespace_topic(self, service):
        request = OutlineRequest(topic="   ", num_slides=5)
        with pytest.raises(ValueError, match="주제가 비어있습니다"):
            service.generate(request)

    def test_generate_parses_json_in_code_block(self, mock_agent):
        mock_agent.return_value = f"여기 결과입니다:\n```json\n{VALID_OUTLINE_JSON}\n```"
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        response = service.generate(request)

        assert len(response.slides) == 3

    def test_generate_raises_on_invalid_json_after_retries(self, mock_agent):
        mock_agent.return_value = "이것은 JSON이 아닙니다"
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)

        with pytest.raises(ValueError, match="유효하지 않은 JSON"):
            service.generate(request)

        assert mock_agent.call_count == 3

    def test_generate_raises_on_missing_slides_key_after_retries(self, mock_agent):
        mock_agent.return_value = '{"data": []}'
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)

        with pytest.raises(ValueError, match="slides"):
            service.generate(request)

        assert mock_agent.call_count == 3

    def test_generate_retries_on_invalid_json_then_succeeds(self, mock_agent):
        mock_agent.side_effect = ["잘못된 JSON", VALID_OUTLINE_JSON]
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        response = service.generate(request)

        assert mock_agent.call_count == 2
        assert len(response.slides) == 3

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
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        response = service.generate(request)

        assert response.slides[0].layout_type == "text_only"

    def test_generate_handles_missing_optional_fields(self, mock_agent):
        data = {"slides": [{"title": "최소 슬라이드"}]}
        mock_agent.return_value = json.dumps(data)
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        response = service.generate(request)

        slide = response.slides[0]
        assert slide.title == "최소 슬라이드"
        assert slide.bullets == []
        assert slide.image_idea == ""
        assert slide.layout_type == "text_only"
        assert slide.speaker_notes == ""

    def test_generate_parses_elements(self, mock_agent):
        data = {
            "slides": [
                {
                    "title": "Freeform 슬라이드",
                    "bullets": [],
                    "image_idea": "",
                    "layout_type": "freeform",
                    "speaker_notes": "",
                    "elements": [
                        {
                            "type": "textbox",
                            "left": 0.5,
                            "top": 0.5,
                            "width": 12.0,
                            "height": 1.5,
                            "content": "제목",
                            "font_size_pt": 28,
                            "bold": True,
                        }
                    ],
                }
            ]
        }
        mock_agent.return_value = json.dumps(data, ensure_ascii=False)
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        response = service.generate(request)

        slide = response.slides[0]
        assert slide.layout_type == "freeform"
        assert len(slide.elements) == 1
        elem = slide.elements[0]
        assert elem.type == "textbox"
        assert elem.left == 0.5
        assert elem.top == 0.5
        assert elem.width == 12.0
        assert elem.height == 1.5
        assert elem.content == "제목"
        assert elem.font_size_pt == 28
        assert elem.bold is True

    def test_generate_elements_default_empty_list(self, mock_agent):
        data = {
            "slides": [
                {
                    "title": "일반 슬라이드",
                    "layout_type": "text_only",
                }
            ]
        }
        mock_agent.return_value = json.dumps(data)
        service = OutlineService(agent=mock_agent)
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        response = service.generate(request)

        assert response.slides[0].elements == []

    def test_generate_prompt_contains_freeform(self, service, mock_agent):
        request = OutlineRequest(topic="테스트 주제", num_slides=5)
        service.generate(request)

        prompt = mock_agent.call_args[0][0]
        assert "freeform" in prompt.lower() or "free-form" in prompt.lower()
