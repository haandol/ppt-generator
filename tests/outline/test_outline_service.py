"""OutlineService prepare/ingest 단위 테스트.

LLM 호출은 클라이언트로 오프로딩됐다. OutlineService 는
- prepare(request) → 프롬프트 + 출력 스키마 조립
- ingest(outline_text, request) → 클라이언트 JSON 검증·발표자 주입·파싱
두 단계를 제공한다. (재시도 루프는 클라이언트 몫이라 서비스에서 사라졌다.)
"""

import json

import pytest

from ppt_generator.interfaces.llm_output_models import OutlineOutput
from ppt_generator.interfaces.schemas import OutlineRequest
from ppt_generator.tools.outline.service import OutlineService


def _slide(
    title: str,
    content_summary: str,
    *,
    slide_type: str = "content",
    layout_plan: str = "single column",
    speaker_notes: str = "",
) -> dict:
    return {
        "title": title,
        "content_summary": content_summary,
        "component_hint": "bullets",
        "slide_type": slide_type,
        "layout_plan": layout_plan,
        "speaker_notes": speaker_notes,
    }


VALID_OUTLINE_JSON = json.dumps(
    {
        "slides": [
            _slide("클라우드 컴퓨팅 트렌드", "핵심 트렌드 소개, 시장 현황 개요"),
            _slide(
                "멀티클라우드 전략",
                "AWS, Azure, GCP 비교 및 하이브리드 접근 방식",
                layout_plan="horizontal 3 cards",
                speaker_notes="세 클라우드의 장단점을 비교하겠습니다.",
            ),
            _slide("감사합니다", "Q&A 시간", slide_type="closing"),
        ]
    },
    ensure_ascii=False,
)


@pytest.fixture
def service():
    return OutlineService()


class TestOutlineServicePrepare:
    """prepare — 프롬프트/스키마 조립 (부작용 없음)."""

    def test_prepare_returns_prompt_and_schema(self, service):
        request = OutlineRequest(
            topic="클라우드 컴퓨팅 트렌드",
            num_slides=5,
            audience_type="general",
            presentation_minutes=15,
        )
        task = service.prepare(request)

        assert "system_prompt" in task
        assert "user_prompt" in task
        assert "response_schema" in task
        assert task["response_schema"] == OutlineOutput.model_json_schema()

    def test_prepare_raises_on_empty_topic(self, service):
        request = OutlineRequest(
            topic="", num_slides=5, audience_type="general", presentation_minutes=15
        )
        with pytest.raises(ValueError, match="Topic is empty"):
            service.prepare(request)

    def test_prepare_raises_on_whitespace_topic(self, service):
        request = OutlineRequest(
            topic="   ", num_slides=5, audience_type="general", presentation_minutes=15
        )
        with pytest.raises(ValueError, match="Topic is empty"):
            service.prepare(request)

    def test_prepare_prompt_contains_topic(self, service):
        request = OutlineRequest(topic="테스트 주제", num_slides=5)
        task = service.prepare(request)
        assert "테스트 주제" in task["user_prompt"]

    def test_prepare_prompt_contains_audience_type_and_minutes(self, service):
        request = OutlineRequest(
            topic="AI 트렌드",
            num_slides=5,
            audience_type="technical",
            presentation_minutes=20,
        )
        task = service.prepare(request)
        assert "technical" in task["user_prompt"]
        assert "20" in task["user_prompt"]

    def test_prepare_prompt_contains_executive_and_minutes(self, service):
        request = OutlineRequest(
            topic="AI 트렌드",
            num_slides=5,
            audience_type="executive",
            presentation_minutes=30,
        )
        task = service.prepare(request)
        assert "executive" in task["user_prompt"]
        assert "30" in task["user_prompt"]


class TestOutlineServiceIngest:
    """ingest — 클라이언트 JSON 검증·파싱·발표자 주입."""

    def test_ingest_returns_outline_response(self, service):
        request = OutlineRequest(
            topic="클라우드 컴퓨팅 트렌드",
            num_slides=5,
            audience_type="general",
            presentation_minutes=15,
        )
        response = service.ingest(VALID_OUTLINE_JSON, request)

        assert len(response.slides) == 3
        assert response.slides[0].title == "클라우드 컴퓨팅 트렌드"
        assert (
            response.slides[1].content_summary
            == "AWS, Azure, GCP 비교 및 하이브리드 접근 방식"
        )
        assert response.slides[1].layout_plan == "horizontal 3 cards"
        assert (
            response.slides[1].speaker_notes == "세 클라우드의 장단점을 비교하겠습니다."
        )

    def test_ingest_parses_json_in_code_block(self, service):
        wrapped = f"여기 결과입니다:\n```json\n{VALID_OUTLINE_JSON}\n```"
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        response = service.ingest(wrapped, request)

        assert len(response.slides) == 3

    def test_ingest_raises_on_invalid_json(self, service):
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        with pytest.raises(ValueError, match="LLM returned invalid JSON"):
            service.ingest("이것은 JSON이 아닙니다", request)

    def test_ingest_raises_on_missing_slides_key(self, service):
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        with pytest.raises(ValueError, match="slides"):
            service.ingest('{"data": []}', request)

    def test_ingest_rejects_fields_required_by_prepare_schema(self, service):
        data = {"slides": [{"title": "최소 슬라이드"}]}
        request = OutlineRequest(topic="스크립트 내용", num_slides=5)
        with pytest.raises(ValueError, match="content_summary"):
            service.ingest(json.dumps(data), request)

    def test_ingest_injects_presenter_into_title_slide(self, service):
        data = {
            "slides": [
                _slide(
                    "표지",
                    "발표 개요",
                    slide_type="title",
                    layout_plan="centered title",
                    speaker_notes="발표를 시작하겠습니다.",
                ),
                _slide("본문", "내용"),
            ]
        }
        request = OutlineRequest(
            topic="주제",
            num_slides=2,
            presenter_name="홍길동",
            presenter_title="Solutions Architect",
            presenter_org="ACME",
        )
        response = service.ingest(json.dumps(data), request)

        # title 슬라이드에만 발표자 정보 주입.
        assert "홍길동" in response.slides[0].content_summary
        assert "Solutions Architect" in response.slides[0].content_summary
        assert "ACME" in response.slides[0].content_summary
        assert "홍길동" not in response.slides[1].content_summary
        assert response.slides[0].layout_plan == "centered title"
        assert response.slides[0].speaker_notes == "발표를 시작하겠습니다."
