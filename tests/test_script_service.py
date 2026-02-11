import json
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import OutlineResponse, ScriptRequest, SlideOutline
from ppt_generator.tools.script.service import ScriptService

SAMPLE_SLIDES = [
    SlideOutline(
        title="클라우드 컴퓨팅 트렌드",
        bullets=["핵심 트렌드 소개", "시장 현황"],
        image_idea="클라우드 인프라 개념도",
        layout_type="title",
        speaker_notes="",
    ),
    SlideOutline(
        title="멀티클라우드 전략",
        bullets=["AWS, Azure, GCP 비교", "하이브리드 접근"],
        image_idea="멀티클라우드 아키텍처 다이어그램",
        layout_type="text_image",
        speaker_notes="",
    ),
    SlideOutline(
        title="감사합니다",
        bullets=["Q&A"],
        image_idea="",
        layout_type="closing",
        speaker_notes="",
    ),
]

VALID_SCRIPTS_JSON = json.dumps(
    {
        "scripts": [
            {"slide_index": 0, "speaker_notes": "안녕하세요, 오늘은 클라우드 컴퓨팅 트렌드에 대해 발표하겠습니다."},
            {"slide_index": 1, "speaker_notes": "첫 번째 트렌드는 멀티클라우드 전략입니다."},
            {"slide_index": 2, "speaker_notes": "이상으로 발표를 마치겠습니다."},
        ]
    },
    ensure_ascii=False,
)


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.return_value = VALID_SCRIPTS_JSON
    return agent


@pytest.fixture
def service(mock_agent):
    return ScriptService(agent=mock_agent)


class TestScriptService:
    def test_generate_returns_script_response_with_speaker_notes(self, service):
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert len(response.slides) == 3
        assert response.slides[0].speaker_notes == "안녕하세요, 오늘은 클라우드 컴퓨팅 트렌드에 대해 발표하겠습니다."
        assert response.slides[1].speaker_notes == "첫 번째 트렌드는 멀티클라우드 전략입니다."
        assert response.slides[2].speaker_notes == "이상으로 발표를 마치겠습니다."

    def test_generate_preserves_slide_fields(self, service):
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert response.slides[0].title == "클라우드 컴퓨팅 트렌드"
        assert response.slides[0].layout_type == "title"
        assert response.slides[1].bullets == ["AWS, Azure, GCP 비교", "하이브리드 접근"]

    def test_generate_calls_agent_with_outline(self, service, mock_agent):
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        service.generate(request)

        mock_agent.assert_called_once()
        prompt = mock_agent.call_args[0][0]
        assert "클라우드 컴퓨팅 트렌드" in prompt

    def test_generate_raises_on_empty_slides(self, service):
        outline = OutlineResponse(slides=[])
        request = ScriptRequest(outline=outline)
        with pytest.raises(ValueError, match="아웃라인에 슬라이드가 없습니다"):
            service.generate(request)

    def test_generate_parses_json_in_code_block(self, mock_agent):
        mock_agent.return_value = f"결과입니다:\n```json\n{VALID_SCRIPTS_JSON}\n```"
        service = ScriptService(agent=mock_agent)
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert len(response.slides) == 3
        assert response.slides[0].speaker_notes != ""

    def test_generate_raises_on_invalid_json(self, mock_agent):
        mock_agent.return_value = "이것은 JSON이 아닙니다"
        service = ScriptService(agent=mock_agent)
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)

        with pytest.raises(ValueError, match="유효하지 않은 JSON"):
            service.generate(request)

    def test_generate_raises_on_missing_scripts_key(self, mock_agent):
        mock_agent.return_value = '{"data": []}'
        service = ScriptService(agent=mock_agent)
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)

        with pytest.raises(ValueError, match="scripts"):
            service.generate(request)

    def test_generate_keeps_original_notes_for_missing_indices(self, mock_agent):
        partial_scripts = json.dumps(
            {
                "scripts": [
                    {"slide_index": 0, "speaker_notes": "첫 번째 노트"},
                ]
            },
            ensure_ascii=False,
        )
        mock_agent.return_value = partial_scripts
        service = ScriptService(agent=mock_agent)
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert response.slides[0].speaker_notes == "첫 번째 노트"
        assert response.slides[1].speaker_notes == ""
        assert response.slides[2].speaker_notes == ""
