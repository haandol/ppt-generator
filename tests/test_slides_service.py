from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.interfaces.constants import LAYOUT_REGIONS, build_layout_skeleton
from ppt_generator.interfaces.schemas import SlidesResponse, SlideOutline
from ppt_generator.tools.slides.service import SlidesService


def _make_slide(index: int) -> SlideOutline:
    return SlideOutline(
        title=f"슬라이드 {index}",
        content_summary=f"슬라이드 {index} 내용 요약",
        layout_index=22,
    )


# LLM이 반환하는 region 기반 section 요소
SAMPLE_SECTIONS = (
    '<section id="slide-0" data-speaker-notes="">'
    '<div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0; background-color:#0f172a;">'
    '<div data-region="title" style="position:absolute; left:57px; top:96px; width:1152px; height:56px; overflow:hidden;">'
    '<h2 style="color:#fff; font-size:1.875rem; font-weight:bold;">내용</h2>'
    '</div>'
    '<div data-region="body" style="position:absolute; left:64px; top:180px; width:1152px; height:472px; overflow:hidden;">'
    '<p style="color:#fff; font-size:1.125rem;">본문</p>'
    '</div>'
    '</div>'
    '</section>'
)

# 템플릿에 삽입된 완전한 HTML (수정 시 LLM이 반환)
SAMPLE_FULL_HTML = (
    "<!DOCTYPE html>\n"
    '<html lang="ko"><head><meta charset="UTF-8"></head>\n'
    "<body>\n"
    '<section data-speaker-notes="">내용</section>\n'
    "</body></html>"
)

MODIFIED_FULL_HTML = (
    "<!DOCTYPE html>\n"
    '<html lang="ko"><head><meta charset="UTF-8"></head>\n'
    "<body>\n"
    '<section data-speaker-notes="" style="background:blue;">수정됨</section>\n'
    "</body></html>"
)

CONTINUATION_SECTIONS = (
    '<section id="slide-1" data-speaker-notes="">'
    '<div data-wrapper="true" style="position:absolute; top:0; left:0; right:0; bottom:0; background-color:#0f172a;">'
    '<div data-region="title" style="position:absolute; left:57px; top:96px; width:1152px; height:56px; overflow:hidden;">'
    '추가 슬라이드'
    '</div>'
    '<div data-region="body" style="position:absolute; left:64px; top:180px; width:1152px; height:472px; overflow:hidden;">'
    '본문'
    '</div>'
    '</div>'
    '</section>'
)


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.return_value = SAMPLE_SECTIONS
    return agent


@pytest.fixture
def mock_modify_agent():
    agent = MagicMock()
    agent.return_value = MODIFIED_FULL_HTML
    return agent


@pytest.fixture
def service(mock_agent, mock_modify_agent):
    return SlidesService(agent=mock_agent, modify_agent=mock_modify_agent)


class TestGenerate:
    def test_generate_returns_slides_response(self, service):
        response = service.generate(slides=[_make_slide(0)])

        assert isinstance(response, SlidesResponse)
        assert response.session_id
        assert response.html

    def test_generate_produces_html_structure(self, service):
        response = service.generate(slides=[_make_slide(0)])

        assert "<!DOCTYPE html>" in response.html
        assert "<section" in response.html
        assert "<body>" in response.html

    def test_generate_raises_on_empty_slides(self, service):
        with pytest.raises(ValueError, match="슬라이드 목록이 비어있습니다"):
            service.generate(slides=[])

    def test_generate_stores_session(self, service):
        response = service.generate(slides=[_make_slide(0)])

        html = service.get_session_html(response.session_id)
        assert html == response.html


class TestBatchedGeneration:
    def test_generate_single_slide_single_call(self, mock_agent, mock_modify_agent):
        """SLIDES_MAX_PER_BATCH=1이므로 1장이면 agent 1회 호출"""
        service = SlidesService(agent=mock_agent, modify_agent=mock_modify_agent)
        slides = [_make_slide(0)]
        service.generate(slides=slides)

        assert mock_agent.call_count == 1

    def test_generate_two_slides_batched(self, mock_modify_agent):
        """SLIDES_MAX_PER_BATCH=1이므로 2장이면 배치 처리 (첫 배치 + 디자인 요약 + 후속 배치)"""
        agent = MagicMock()
        agent.side_effect = [
            SAMPLE_SECTIONS,
            "배경색: 흰색, 폰트: Pretendard, 제목: 28px bold",
            CONTINUATION_SECTIONS,
        ]
        service = SlidesService(agent=agent, modify_agent=mock_modify_agent)
        slides = [_make_slide(i) for i in range(2)]
        service.generate(slides=slides)

        assert agent.call_count == 3

    def test_generate_five_slides_batched(self, mock_modify_agent):
        """5장이면 첫 배치 + 디자인 요약 + 후속 배치 4회 = agent 6회 호출"""
        agent = MagicMock()
        agent.side_effect = [
            SAMPLE_SECTIONS,           # 첫 배치 (1장)
            "디자인 요약",              # 디자인 요약 추출
            CONTINUATION_SECTIONS,     # 후속 배치 2
            CONTINUATION_SECTIONS,     # 후속 배치 3
            CONTINUATION_SECTIONS,     # 후속 배치 4
            CONTINUATION_SECTIONS,     # 후속 배치 5
        ]
        service = SlidesService(agent=agent, modify_agent=mock_modify_agent)
        slides = [_make_slide(i) for i in range(5)]
        service.generate(slides=slides)

        assert agent.call_count == 6

    def test_chunk_slides_with_batch_size_1(self):
        slides = [_make_slide(i) for i in range(5)]
        chunks = SlidesService._chunk_slides(slides, 1)

        assert len(chunks) == 5
        for chunk in chunks:
            assert len(chunk) == 1

    def test_combine_html_batches_inserts_sections(self):
        first_html = (
            "<html><body>"
            "<section>first</section>"
            "</body></html>"
        )
        sections = ["<section>second</section>"]
        result = SlidesService._combine_html_batches(first_html, sections)

        assert "<section>first</section>" in result
        assert "<section>second</section>" in result

    def test_batched_generation_maintains_image_indices(self, mock_modify_agent):
        """전역 인덱스가 유지되는지 확인"""
        agent = MagicMock()
        agent.side_effect = [
            SAMPLE_SECTIONS,       # 첫 배치 (슬라이드 0)
            "디자인 요약",          # 디자인 요약
            CONTINUATION_SECTIONS, # 슬라이드 1
            CONTINUATION_SECTIONS, # 슬라이드 2
        ]
        service = SlidesService(agent=agent, modify_agent=mock_modify_agent)
        slides = [_make_slide(i) for i in range(3)]
        service.generate(slides=slides)

        # 마지막 호출의 프롬프트에서 전역 인덱스(2) 사용 확인
        last_call_prompt = agent.call_args_list[-1][0][0]
        assert "슬라이드 2" in last_call_prompt


class TestModify:
    def test_modify_returns_updated_html(self, service):
        # 먼저 세션 생성
        gen_response = service.generate(slides=[_make_slide(0)])

        response = service.modify(gen_response.session_id, "배경색을 파란색으로 변경")
        assert isinstance(response, SlidesResponse)
        assert response.html == MODIFIED_FULL_HTML

    def test_modify_updates_session(self, service):
        gen_response = service.generate(slides=[_make_slide(0)])

        service.modify(gen_response.session_id, "배경색을 파란색으로 변경")
        assert service.get_session_html(gen_response.session_id) == MODIFIED_FULL_HTML

    def test_modify_preserves_session_id(self, service):
        gen_response = service.generate(slides=[_make_slide(0)])

        mod_response = service.modify(gen_response.session_id, "배경색 변경")
        assert mod_response.session_id == gen_response.session_id

    def test_modify_raises_on_invalid_session(self, service):
        with pytest.raises(KeyError, match="세션을 찾을 수 없습니다"):
            service.modify("nonexistent-id", "수정 요청")

    def test_modify_raises_on_empty_request(self, service):
        gen_response = service.generate(slides=[_make_slide(0)])

        with pytest.raises(ValueError, match="수정 요청이 비어있습니다"):
            service.modify(gen_response.session_id, "   ")

    def test_modify_calls_modify_agent(self, service, mock_agent, mock_modify_agent):
        gen_response = service.generate(slides=[_make_slide(0)])

        service.modify(gen_response.session_id, "배경색 변경")

        # modify_agent가 호출되었는지 확인
        mock_modify_agent.assert_called_once()
        # generate agent는 generate 시 1회만 호출
        assert mock_agent.call_count == 1

    def test_modify_multiple_times(self, mock_agent):
        """누적 수정이 동작하는지 확인"""
        modify_agent = MagicMock()
        modify_agent.side_effect = [
            MODIFIED_FULL_HTML,
            "<!DOCTYPE html><html><body>"
            "<section>최종</section></body></html>",
        ]
        service = SlidesService(agent=mock_agent, modify_agent=modify_agent)

        gen_response = service.generate(slides=[_make_slide(0)])

        # 첫 번째 수정
        service.modify(gen_response.session_id, "배경색 변경")
        # 두 번째 수정 — modify_agent에 전달되는 current_html이 첫 번째 수정 결과여야 함
        service.modify(gen_response.session_id, "텍스트 변경")

        second_call_prompt = modify_agent.call_args_list[1][0][0]
        assert "수정됨" in second_call_prompt  # MODIFIED_FULL_HTML의 내용이 포함


class TestModifySingleSlide:
    MULTI_SLIDE_HTML = (
        "<!DOCTYPE html>\n"
        '<html lang="ko"><head><meta charset="UTF-8"></head>\n'
        "<body>\n"
        '<section data-speaker-notes="">슬라이드 0</section>\n'
        '<section data-speaker-notes="">슬라이드 1</section>\n'
        '<section data-speaker-notes="">슬라이드 2</section>\n'
        "</body></html>"
    )

    def test_modify_single_slide(self, mock_agent):
        """slide_index 지정 시 해당 슬라이드만 수정"""
        modify_agent = MagicMock()
        modify_agent.return_value = '<section data-speaker-notes="">수정된 슬라이드 1</section>'
        service = SlidesService(agent=mock_agent, modify_agent=modify_agent)

        # 세션에 직접 HTML 등록
        session_id = "test-session"
        service._sessions[session_id] = self.MULTI_SLIDE_HTML

        response = service.modify(session_id, "텍스트 변경", slide_index=1)

        assert "수정된 슬라이드 1" in response.html
        assert "슬라이드 0" in response.html
        assert "슬라이드 2" in response.html

    def test_modify_single_preserves_others(self, mock_agent):
        """다른 슬라이드 변경 없음 확인"""
        modify_agent = MagicMock()
        modify_agent.return_value = '<section data-speaker-notes="">변경됨</section>'
        service = SlidesService(agent=mock_agent, modify_agent=modify_agent)

        session_id = "test-session"
        service._sessions[session_id] = self.MULTI_SLIDE_HTML

        response = service.modify(session_id, "수정", slide_index=0)

        # 슬라이드 0만 변경되고, 1과 2는 그대로
        assert "변경됨" in response.html
        assert "슬라이드 1" in response.html
        assert "슬라이드 2" in response.html

    def test_modify_raises_on_invalid_index(self, mock_agent):
        """범위 초과 시 IndexError"""
        modify_agent = MagicMock()
        service = SlidesService(agent=mock_agent, modify_agent=modify_agent)

        session_id = "test-session"
        service._sessions[session_id] = self.MULTI_SLIDE_HTML

        with pytest.raises(IndexError, match="슬라이드 인덱스 범위 초과"):
            service.modify(session_id, "수정", slide_index=5)

    def test_modify_negative_index_modifies_all(self, mock_agent):
        """slide_index=-1이면 전체 수정 (기존 동작)"""
        modify_agent = MagicMock()
        modify_agent.return_value = MODIFIED_FULL_HTML
        service = SlidesService(agent=mock_agent, modify_agent=modify_agent)

        session_id = "test-session"
        service._sessions[session_id] = self.MULTI_SLIDE_HTML

        response = service.modify(session_id, "전체 수정")
        assert response.html == MODIFIED_FULL_HTML


class TestExtractSections:
    def test_extract_sections_from_code_block(self):
        text = "결과:\n```html\n<section>hello</section>\n```"
        result = SlidesService._extract_sections(text)
        assert result == "<section>hello</section>"

    def test_extract_sections_from_full_html(self):
        text = (
            "<!DOCTYPE html><html><body>"
            "<section>test</section>"
            "</body></html>"
        )
        result = SlidesService._extract_sections(text)
        assert "<section>test</section>" in result

    def test_extract_sections_raw(self):
        text = '<section data-speaker-notes="">content</section>'
        result = SlidesService._extract_sections(text)
        assert "<section" in result
        assert "content" in result

    def test_extract_sections_fallback(self):
        text = "그냥 텍스트입니다"
        result = SlidesService._extract_sections(text)
        assert result == "그냥 텍스트입니다"

    def test_extract_sections_with_style(self):
        """style 태그가 포함된 입력에서 section만 추출"""
        text = "<style>.custom { color: red; }</style>\n<section>styled</section>"
        result = SlidesService._extract_sections(text)
        assert "<style>" not in result
        assert "<section>styled</section>" in result


class TestExtractFullHtml:
    def test_extract_from_code_block(self):
        text = "결과:\n```html\n<!DOCTYPE html><html><body>hello</body></html>\n```"
        result = SlidesService._extract_full_html(text)
        assert "<!DOCTYPE html>" in result

    def test_extract_from_doctype(self):
        text = "여기 결과입니다.\n<!DOCTYPE html><html><body>test</body></html>"
        result = SlidesService._extract_full_html(text)
        assert result.startswith("<!DOCTYPE html>")

    def test_extract_fallback(self):
        text = "그냥 텍스트입니다"
        result = SlidesService._extract_full_html(text)
        assert result == "그냥 텍스트입니다"


class TestBuildLayoutSkeleton:
    def test_text_only_skeleton_has_title_and_body(self):
        skeleton = build_layout_skeleton(22, 0)
        assert 'data-region="title"' in skeleton
        assert 'data-region="body"' in skeleton
        assert 'id="slide-0"' in skeleton
        assert "<!-- CONTENT:title -->" in skeleton
        assert "<!-- CONTENT:body -->" in skeleton

    def test_title_skeleton_has_title_and_subtitle(self):
        skeleton = build_layout_skeleton(0, 0)
        assert 'data-region="title"' in skeleton
        assert 'data-region="subtitle"' in skeleton

    def test_text_image_layout_falls_back_to_text_only(self):
        skeleton = build_layout_skeleton(28, 0)
        assert 'data-region="title"' in skeleton
        assert 'data-region="body"' in skeleton
        # layout 28은 제거되었으므로 text_only(22)로 폴백
        assert 'data-region="image"' not in skeleton

    def test_speaker_notes_included(self):
        skeleton = build_layout_skeleton(22, 0, speaker_notes="테스트 노트")
        assert 'data-speaker-notes="테스트 노트"' in skeleton

    def test_wrapper_div_present(self):
        skeleton = build_layout_skeleton(22, 0)
        assert 'data-wrapper="true"' in skeleton

    def test_position_absolute_in_region_style(self):
        skeleton = build_layout_skeleton(22, 0)
        assert "position:absolute" in skeleton

    def test_all_layout_indices_generate_skeleton(self):
        for layout_index in LAYOUT_REGIONS:
            skeleton = build_layout_skeleton(layout_index, 0)
            assert 'data-wrapper="true"' in skeleton
            assert "<section" in skeleton

    def test_unknown_layout_falls_back_to_text_only(self):
        skeleton = build_layout_skeleton(999, 0)
        assert 'data-region="title"' in skeleton
        assert 'data-region="body"' in skeleton

    def test_coordinates_match_layout_regions(self):
        regions = LAYOUT_REGIONS[22]
        skeleton = build_layout_skeleton(22, 0)
        assert f"left:{regions['title']['left']}px" in skeleton
        assert f"top:{regions['title']['top']}px" in skeleton
        assert f"width:{regions['title']['width']}px" in skeleton
        assert f"height:{regions['title']['height']}px" in skeleton


class TestValidateRegionStyles:
    def test_restores_modified_coordinates(self):
        """LLM이 좌표를 변경해도 원래 값으로 복원"""
        html = (
            '<section id="slide-0" data-speaker-notes="">'
            '<div data-wrapper="true" class="absolute inset-0">'
            '<div data-region="title" style="position:absolute; left:999px; top:999px; width:100px; height:100px; overflow:hidden;">'
            '<h2>제목</h2></div>'
            '<div data-region="body" style="position:absolute; left:0px; top:0px; width:50px; height:50px; overflow:hidden;">'
            '<p>본문</p></div>'
            '</div></section>'
        )
        result = SlidesService._validate_region_styles(html, 22)
        regions = LAYOUT_REGIONS[22]
        assert f"left:{regions['title']['left']}px" in result
        assert f"top:{regions['title']['top']}px" in result
        assert f"width:{regions['body']['width']}px" in result

    def test_preserves_content(self):
        """좌표 복원 시 콘텐츠는 보존"""
        html = (
            '<section id="slide-0" data-speaker-notes="">'
            '<div data-wrapper="true">'
            '<div data-region="title" style="position:absolute; left:0px; top:0px; width:100px; height:100px;">'
            '<h2 style="color:#fff; font-size:1.875rem; font-weight:bold;">중요 제목</h2></div>'
            '</div></section>'
        )
        result = SlidesService._validate_region_styles(html, 0)
        assert "중요 제목" in result
        assert 'style="color:#fff; font-size:1.875rem; font-weight:bold;"' in result

    def test_skips_unknown_region(self):
        """LAYOUT_REGIONS에 없는 region은 건드리지 않음"""
        html = (
            '<section><div data-wrapper="true">'
            '<div data-region="custom" style="position:absolute; left:10px; top:10px; width:100px; height:100px;">'
            'text</div></div></section>'
        )
        result = SlidesService._validate_region_styles(html, 22)
        assert "left:10px" in result


class TestDetectLayoutIndex:
    def test_detect_from_data_layout_index(self):
        html = (
            '<section data-layout-index="22"><div data-wrapper="true">'
            '<div data-region="title">t</div>'
            '<div data-region="body">b</div>'
            '</div></section>'
        )
        result = SlidesService._detect_layout_index_from_html(html)
        assert result == 22

    def test_detect_from_data_layout_index_overrides_regions(self):
        html = (
            '<section data-layout-index="87"><div data-wrapper="true">'
            '<div data-region="title">t</div>'
            '<div data-region="body">b</div>'
            '</div></section>'
        )
        result = SlidesService._detect_layout_index_from_html(html)
        assert result == 87

    def test_detect_text_image_falls_back(self):
        html = (
            '<section><div data-wrapper="true">'
            '<div data-region="title">t</div>'
            '<div data-region="body">b</div>'
            '<div data-region="image">i</div>'
            '</div></section>'
        )
        result = SlidesService._detect_layout_index_from_html(html)
        # title+body+image 조합 매칭 또는 default(22)로 폴백
        assert isinstance(result, int)

    def test_detect_title(self):
        html = (
            '<section data-layout-index="0"><div data-wrapper="true">'
            '<div data-region="title">t</div>'
            '<div data-region="subtitle">s</div>'
            '</div></section>'
        )
        result = SlidesService._detect_layout_index_from_html(html)
        assert result == 0

    def test_fallback_no_regions(self):
        html = '<section><div>no regions</div></section>'
        result = SlidesService._detect_layout_index_from_html(html)
        assert result == 22
