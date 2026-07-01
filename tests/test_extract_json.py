"""extract_json_from_response 견고성 단위 테스트.

adaptive thinking 모델의 다양한 응답 형식(코드블록 유무, 다중 블록, 산문 혼합)에서
slides JSON 을 안정적으로 뽑아내는지 검증한다.
"""

import pytest

from ppt_generator.interfaces.utils import extract_json_from_response


class TestExtractJsonFromResponse:
    def test_plain_json(self) -> None:
        data = extract_json_from_response('{"slides": [{"title": "a"}]}')
        assert data["slides"][0]["title"] == "a"

    def test_json_code_block(self) -> None:
        text = '```json\n{"slides": [{"title": "a"}]}\n```'
        assert extract_json_from_response(text)["slides"][0]["title"] == "a"

    def test_bare_code_block(self) -> None:
        text = '```\n{"slides": []}\n```'
        assert extract_json_from_response(text) == {"slides": []}

    def test_prose_wrapped_json(self) -> None:
        """코드블록 없이 산문과 JSON 이 섞인 경우 최외곽 객체를 뽑는다."""
        text = '설명입니다.\n{"slides": [{"title": "a"}]}\n이상입니다.'
        assert extract_json_from_response(text)["slides"][0]["title"] == "a"

    def test_multiple_blocks_prefers_slides(self) -> None:
        """예시 코드블록이 먼저 나와도 slides 를 가진 블록을 우선한다."""
        text = (
            '예시:\n```json\n{"example": 1}\n```\n'
            '결과:\n```json\n{"slides": [{"title": "real"}]}\n```'
        )
        assert extract_json_from_response(text)["slides"][0]["title"] == "real"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ValueError):
            extract_json_from_response("this is not json at all")

    def test_no_object_raises(self) -> None:
        with pytest.raises(ValueError):
            extract_json_from_response("[1, 2, 3]")
