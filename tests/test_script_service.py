import json
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import OutlineResponse, ScriptRequest, SlideOutline
from ppt_generator.tools.script.service import ScriptService

SAMPLE_SLIDES = [
    SlideOutline(
        title="클라우드 컴퓨팅 트렌드",
        content_summary="핵심 트렌드 소개, 시장 현황 개요",
        layout_index=0,
    ),
    SlideOutline(
        title="멀티클라우드 전략",
        content_summary="AWS, Azure, GCP 비교 및 하이브리드 접근 방식",
        layout_index=28,
    ),
    SlideOutline(
        title="감사합니다",
        content_summary="Q&A 시간",
        layout_index=87,
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
    def test_generate_returns_script_response(self, service):
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert len(response.slides) == 3

    def test_generate_preserves_slide_fields(self, service):
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert response.slides[0].title == "클라우드 컴퓨팅 트렌드"
        assert response.slides[0].layout_index == 0
        assert response.slides[1].content_summary == "AWS, Azure, GCP 비교 및 하이브리드 접근 방식"

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

    def test_generate_raises_on_invalid_json(self, mock_agent):
        mock_agent.return_value = "이것은 JSON이 아닙니다"
        service = ScriptService(agent=mock_agent)
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)

        with pytest.raises(ValueError, match="유효하지 않은 JSON"):
            service.generate(request)

    def test_generate_returns_slides_with_speaker_notes(self, service):
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert response.slides[0].speaker_notes == "안녕하세요, 오늘은 클라우드 컴퓨팅 트렌드에 대해 발표하겠습니다."
        assert response.slides[1].speaker_notes == "첫 번째 트렌드는 멀티클라우드 전략입니다."
        assert response.slides[2].speaker_notes == "이상으로 발표를 마치겠습니다."

    def test_generate_preserves_component_hint(self, service):
        slides_with_hint = [
            SlideOutline(title="제목", content_summary="요약", layout_index=0, component_hint="agenda"),
        ]
        outline = OutlineResponse(slides=slides_with_hint)
        request = ScriptRequest(outline=outline)
        response = service.generate(request)

        assert response.slides[0].component_hint == "agenda"

    def test_generate_raises_on_missing_scripts_key(self, mock_agent):
        mock_agent.return_value = '{"data": []}'
        service = ScriptService(agent=mock_agent)
        outline = OutlineResponse(slides=SAMPLE_SLIDES)
        request = ScriptRequest(outline=outline)

        with pytest.raises(ValueError, match="scripts"):
            service.generate(request)
