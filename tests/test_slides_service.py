from unittest.mock import MagicMock, call

import pytest

from ppt_generator.interfaces.schemas import SlidesRequest, SlidesResponse, SlideOutline
from ppt_generator.tools.slides.service import SlidesService


def _make_slide(index: int) -> SlideOutline:
    return SlideOutline(
        title=f"슬라이드 {index}",
        bullets=[f"항목 {index}-1"],
        image_idea="",
        layout_type="text_only",
        speaker_notes="",
    )


SAMPLE_HTML = (
    "<!DOCTYPE html>\n"
    "<html><head><meta charset=\"UTF-8\"></head>\n"
    "<body>\n"
    "<div class=\"slide\" data-speaker-notes=\"\">내용</div>\n"
    "</body></html>"
)

MODIFIED_HTML = (
    "<!DOCTYPE html>\n"
    "<html><head><meta charset=\"UTF-8\"></head>\n"
    "<body>\n"
    "<div class=\"slide\" data-speaker-notes=\"\" style=\"background:blue;\">수정됨</div>\n"
    "</body></html>"
)

CONTINUATION_DIVS = '<div class="slide" data-speaker-notes="">추가 슬라이드</div>'


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.return_value = SAMPLE_HTML
    return agent


@pytest.fixture
def mock_modify_agent():
    agent = MagicMock()
    agent.return_value = MODIFIED_HTML
    return agent


@pytest.fixture
def service(mock_agent, mock_modify_agent):
    return SlidesService(agent=mock_agent, modify_agent=mock_modify_agent)


class TestGenerate:
    def test_generate_returns_slides_response(self, service):
        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        response = service.generate(request)

        assert isinstance(response, SlidesResponse)
        assert response.session_id
        assert response.html

    def test_generate_raises_on_empty_slides(self, service):
        request = SlidesRequest(slides=[], image_paths={})
        with pytest.raises(ValueError, match="슬라이드 목록이 비어있습니다"):
            service.generate(request)

    def test_generate_stores_session(self, service):
        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        response = service.generate(request)

        html = service.get_session_html(response.session_id)
        assert html == response.html


class TestBatchedGeneration:
    def test_generate_small_outline_single_call(self, mock_agent, mock_modify_agent):
        """10장 이하면 agent 1회 호출"""
        service = SlidesService(agent=mock_agent, modify_agent=mock_modify_agent)
        slides = [_make_slide(i) for i in range(5)]
        request = SlidesRequest(slides=slides, image_paths={})
        service.generate(request)

        assert mock_agent.call_count == 1

    def test_generate_large_outline_batched_calls(self, mock_modify_agent):
        """15장이면 agent 여러 회 호출 (첫 배치 + 디자인 요약 + 후속 배치)"""
        agent = MagicMock()
        # 첫 호출: 전체 HTML, 두 번째: 디자인 요약, 세 번째: 후속 배치 div
        agent.side_effect = [
            SAMPLE_HTML,
            "배경색: 흰색, 폰트: Pretendard, 제목: 28px bold",
            CONTINUATION_DIVS,
        ]
        service = SlidesService(agent=agent, modify_agent=mock_modify_agent)
        slides = [_make_slide(i) for i in range(15)]
        request = SlidesRequest(slides=slides, image_paths={})
        service.generate(request)

        assert agent.call_count == 3

    def test_chunk_slides_correct_sizes(self):
        slides = [_make_slide(i) for i in range(23)]
        chunks = SlidesService._chunk_slides(slides, 10)

        assert len(chunks) == 3
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 3

    def test_combine_html_batches_inserts_before_body(self):
        first_html = "<html><body><div>first</div></body></html>"
        divs = ['<div class="slide">second</div>']
        result = SlidesService._combine_html_batches(first_html, divs)

        assert "<div>first</div>" in result
        assert '<div class="slide">second</div>' in result
        # 후속 div가 </body> 앞에 삽입되었는지 확인
        body_close = result.index("</body>")
        second_div = result.index('<div class="slide">second</div>')
        assert second_div < body_close

    def test_batched_generation_maintains_image_indices(self, mock_modify_agent):
        """전역 인덱스가 유지되는지 확인"""
        agent = MagicMock()
        agent.side_effect = [
            SAMPLE_HTML,
            "디자인 요약",
            CONTINUATION_DIVS,
        ]
        service = SlidesService(agent=agent, modify_agent=mock_modify_agent)
        slides = [_make_slide(i) for i in range(12)]
        request = SlidesRequest(slides=slides, image_paths={})
        service.generate(request)

        # 후속 배치 호출의 프롬프트에서 전역 인덱스(10, 11) 사용 확인
        third_call_prompt = agent.call_args_list[2][0][0]
        assert "슬라이드 10" in third_call_prompt
        assert "슬라이드 11" in third_call_prompt


class TestModify:
    def test_modify_returns_updated_html(self, service):
        # 먼저 세션 생성
        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        gen_response = service.generate(request)

        response = service.modify(gen_response.session_id, "배경색을 파란색으로 변경")
        assert isinstance(response, SlidesResponse)
        assert response.html == MODIFIED_HTML

    def test_modify_updates_session(self, service):
        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        gen_response = service.generate(request)

        service.modify(gen_response.session_id, "배경색을 파란색으로 변경")
        assert service.get_session_html(gen_response.session_id) == MODIFIED_HTML

    def test_modify_preserves_session_id(self, service):
        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        gen_response = service.generate(request)

        mod_response = service.modify(gen_response.session_id, "배경색 변경")
        assert mod_response.session_id == gen_response.session_id

    def test_modify_raises_on_invalid_session(self, service):
        with pytest.raises(KeyError, match="세션을 찾을 수 없습니다"):
            service.modify("nonexistent-id", "수정 요청")

    def test_modify_raises_on_empty_request(self, service):
        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        gen_response = service.generate(request)

        with pytest.raises(ValueError, match="수정 요청이 비어있습니다"):
            service.modify(gen_response.session_id, "   ")

    def test_modify_calls_modify_agent(self, service, mock_agent, mock_modify_agent):
        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        gen_response = service.generate(request)

        service.modify(gen_response.session_id, "배경색 변경")

        # modify_agent가 호출되었는지 확인
        mock_modify_agent.assert_called_once()
        # generate agent는 generate 시 1회만 호출
        assert mock_agent.call_count == 1

    def test_modify_multiple_times(self, mock_agent):
        """누적 수정이 동작하는지 확인"""
        modify_agent = MagicMock()
        modify_agent.side_effect = [
            MODIFIED_HTML,
            "<!DOCTYPE html><html><body><div class=\"slide\">최종</div></body></html>",
        ]
        service = SlidesService(agent=mock_agent, modify_agent=modify_agent)

        request = SlidesRequest(slides=[_make_slide(0)], image_paths={})
        gen_response = service.generate(request)

        # 첫 번째 수정
        service.modify(gen_response.session_id, "배경색 변경")
        # 두 번째 수정 — modify_agent에 전달되는 current_html이 첫 번째 수정 결과여야 함
        service.modify(gen_response.session_id, "텍스트 변경")

        second_call_prompt = modify_agent.call_args_list[1][0][0]
        assert "수정됨" in second_call_prompt  # MODIFIED_HTML의 내용이 포함


class TestExtractHtml:
    def test_extract_html_from_code_block(self):
        text = "결과:\n```html\n<html><body>hello</body></html>\n```"
        result = SlidesService._extract_html(text)
        assert result == "<html><body>hello</body></html>"

    def test_extract_html_from_doctype(self):
        text = "여기 결과입니다.\n<!DOCTYPE html><html><body>test</body></html>"
        result = SlidesService._extract_html(text)
        assert result.startswith("<!DOCTYPE html>")

    def test_extract_html_wraps_slide_divs(self):
        text = '<div class="slide" data-speaker-notes="">content</div>'
        result = SlidesService._extract_html(text)
        assert "<!DOCTYPE html>" in result
        assert '<div class="slide"' in result
        assert "</body></html>" in result

    def test_extract_html_fallback(self):
        text = "그냥 텍스트입니다"
        result = SlidesService._extract_html(text)
        assert result == "그냥 텍스트입니다"


class TestExtractDivs:
    def test_extract_divs_from_code_block(self):
        text = '```html\n<div class="slide">내용</div>\n```'
        result = SlidesService._extract_divs(text)
        assert '<div class="slide">내용</div>' == result

    def test_extract_divs_fallback(self):
        text = "그냥 텍스트"
        result = SlidesService._extract_divs(text)
        assert result == "그냥 텍스트"
