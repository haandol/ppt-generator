"""spec_utils 검증 로직 통합 테스트.

validator는 최소한의 보정만 수행한다:
- 슬라이드 제목(첫 번째 textbox) 최소 폰트 크기 보장
- title/closing 슬라이드 제목: 36pt 이상
- content 슬라이드 제목: 24pt 이상
- 빈 textbox 제거
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import validate_slide_spec
from ppt_generator.interfaces.spec_utils.parser import parse_slide_spec
from ppt_generator.tools.slides.html_renderer import textbox_to_html

_MARGIN = 64
_CANVAS_W = 1280
_CANVAS_H = 720


def _tb(text: str, font: int = 18, **kw) -> PptxTextBox:
    defaults = dict(left_px=64, top_px=64, width_px=500, height_px=50)
    defaults.update(kw)
    return PptxTextBox(
        paragraphs=[PptxParagraph(runs=[PptxTextRun(text=text, font_size_pt=font)])],
        **defaults,
    )


def _slide(
    textboxes: list[PptxTextBox] | None = None,
    shapes: list[PptxShape] | None = None,
    slide_type: str = "content",
) -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=textboxes or [],
        shapes=shapes or [],
        slide_type=slide_type,
    )


# ---------------------------------------------------------------------------
# 슬라이드 제목 최소 폰트 보장
# ---------------------------------------------------------------------------


class TestSlideTitleFontFloor:
    """슬라이드 제목(첫 번째 textbox) 최소 폰트 크기를 보장한다."""

    def test_content_slide_title_floor_24pt(self) -> None:
        """content 슬라이드 제목이 24pt 미만이면 24pt로 올린다."""
        tb = _tb("제목 텍스트", font=16)
        result = validate_slide_spec(_slide(textboxes=[tb]))
        font = result.textboxes[0].paragraphs[0].runs[0].font_size_pt
        assert font is not None
        assert font >= 24

    def test_title_slide_title_floor_36pt(self) -> None:
        """title 슬라이드 제목이 36pt 미만이면 36pt로 올린다."""
        tb = _tb("발표 제목", font=24)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="title"))
        font = result.textboxes[0].paragraphs[0].runs[0].font_size_pt
        assert font is not None
        assert font >= 36

    def test_closing_slide_title_floor_36pt(self) -> None:
        """closing 슬라이드 제목이 36pt 미만이면 36pt로 올린다."""
        tb = _tb("감사합니다", font=20)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="closing"))
        font = result.textboxes[0].paragraphs[0].runs[0].font_size_pt
        assert font is not None
        assert font >= 36

    def test_title_above_min_not_changed(self) -> None:
        """제목이 이미 최소 이상이면 변경하지 않는다."""
        tb = _tb("큰 제목", font=32)
        result = validate_slide_spec(_slide(textboxes=[tb]))
        font = result.textboxes[0].paragraphs[0].runs[0].font_size_pt
        assert font == 32

    def test_second_textbox_not_affected(self) -> None:
        """두 번째 textbox는 제목이 아니므로 폰트 변경 없음."""
        title_tb = _tb("제목", font=28)
        body_tb = _tb("본문 작은 글씨", font=12, top_px=150)
        result = validate_slide_spec(_slide(textboxes=[title_tb, body_tb]))
        body_font = result.textboxes[1].paragraphs[0].runs[0].font_size_pt
        assert body_font == 12

    def test_shapes_not_modified(self) -> None:
        """shape의 폰트는 validator가 수정하지 않는다."""
        shape = PptxShape(
            left_px=64,
            top_px=148,
            width_px=400,
            height_px=200,
            shape_type="rounded_rectangle",
            fill_color="#2E3D50",
            text="카드 본문",
            text_size_pt=12,
        )
        result = validate_slide_spec(_slide(shapes=[shape]))
        assert result.shapes[0].text_size_pt == 12

    def test_shape_position_not_modified(self) -> None:
        """shape의 위치/크기를 validator가 수정하지 않는다."""
        shape = PptxShape(
            left_px=0,
            top_px=100,
            width_px=1280,
            height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        result = validate_slide_spec(_slide(shapes=[shape]))
        assert result.shapes[0].left_px == 0
        assert result.shapes[0].height_px == 3
        assert result.shapes[0].width_px == 1280


# ---------------------------------------------------------------------------
# 레이아웃 비개입 확인
# ---------------------------------------------------------------------------


class TestNoLayoutIntervention:
    """validator가 레이아웃 위치를 변경하지 않는 것을 확인한다."""

    def test_content_title_position_preserved(self) -> None:
        """content 슬라이드 제목 위치가 변경되지 않는다."""
        tb = PptxTextBox(
            left_px=100,
            top_px=100,
            width_px=1000,
            height_px=60,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="제목", font_size_pt=32, bold=True)]
                )
            ],
        )
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="content"))
        v = result.textboxes[0]
        assert v.left_px == 100
        assert v.top_px == 100

    def test_title_slide_position_preserved(self) -> None:
        """title 슬라이드 메인 텍스트 위치가 변경되지 않는다."""
        tb = _tb("대제목", font=36, top_px=72, width_px=1152, height_px=48)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="title"))
        v = result.textboxes[0]
        assert v.top_px == 72

    def test_closing_slide_position_preserved(self) -> None:
        """closing 슬라이드 메인 텍스트 위치가 변경되지 않는다."""
        tb = _tb("감사합니다", font=40, top_px=72, width_px=1152, height_px=48)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="closing"))
        v = result.textboxes[0]
        assert v.top_px == 72

    def test_vertical_alignment_preserved(self) -> None:
        """vertical_alignment이 validator에 의해 변경되지 않는다."""
        tb = PptxTextBox(
            left_px=64,
            top_px=180,
            width_px=1152,
            height_px=480,
            vertical_alignment="top",
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="짧은 본문", font_size_pt=20)],
                    bullet_level=0,
                )
            ],
        )
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="content"))
        assert result.textboxes[0].vertical_alignment == "top"


# ---------------------------------------------------------------------------
# 텍스트박스 padding
# ---------------------------------------------------------------------------


class TestTextboxPadding:
    """PptxTextBox padding 지원 테스트."""

    def test_padding_preserved_through_validation(self) -> None:
        """validator가 textbox의 padding 값을 보존한다."""
        tb = PptxTextBox(
            left_px=64,
            top_px=200,
            width_px=500,
            height_px=100,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])
            ],
            padding_left_px=16,
            padding_right_px=16,
            padding_top_px=12,
            padding_bottom_px=12,
        )
        result = validate_slide_spec(_slide(textboxes=[tb]))
        v = result.textboxes[0]
        assert v.padding_left_px == 16
        assert v.padding_right_px == 16
        assert v.padding_top_px == 12
        assert v.padding_bottom_px == 12

    def test_no_padding_defaults_to_none(self) -> None:
        """padding 미지정 시 None 유지."""
        tb = _tb("테스트", font=18, top_px=200)
        result = validate_slide_spec(_slide(textboxes=[tb]))
        v = result.textboxes[0]
        assert v.padding_left_px is None
        assert v.padding_right_px is None
        assert v.padding_top_px is None
        assert v.padding_bottom_px is None

    def test_padding_affects_autofit_calculation(self) -> None:
        """padding이 있는 textbox는 실제 텍스트 영역이 줄어들어 autofit이 더 공격적으로 작동한다."""
        long_text = "가나다라마바사아자차카타파하" * 3
        # padding 없는 textbox
        tb_no_pad = PptxTextBox(
            left_px=64,
            top_px=200,
            width_px=300,
            height_px=60,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text=long_text, font_size_pt=18)])
            ],
        )
        # padding 있는 textbox (같은 크기이지만 실제 텍스트 영역이 줄어듦)
        tb_with_pad = PptxTextBox(
            left_px=64,
            top_px=200,
            width_px=300,
            height_px=60,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text=long_text, font_size_pt=18)])
            ],
            padding_left_px=20,
            padding_right_px=20,
            padding_top_px=16,
            padding_bottom_px=16,
        )
        result_no_pad = validate_slide_spec(_slide(textboxes=[tb_no_pad]))
        result_with_pad = validate_slide_spec(_slide(textboxes=[tb_with_pad]))
        font_no_pad = result_no_pad.textboxes[0].paragraphs[0].runs[0].font_size_pt
        font_with_pad = result_with_pad.textboxes[0].paragraphs[0].runs[0].font_size_pt
        # padding이 있으면 텍스트 영역이 좁아져서 폰트가 같거나 더 작아야 함
        assert font_with_pad <= font_no_pad


class TestTextboxPaddingHtmlRendering:
    """textbox padding의 HTML 렌더링 테스트."""

    def test_padding_rendered_in_css(self) -> None:
        """padding이 있는 textbox → CSS에 padding 값이 반영된다."""
        tb = PptxTextBox(
            left_px=64,
            top_px=100,
            width_px=500,
            height_px=200,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])
            ],
            padding_left_px=16,
            padding_right_px=20,
            padding_top_px=12,
            padding_bottom_px=14,
        )
        html = textbox_to_html(tb)
        assert "padding:12px 20px 14px 16px" in html

    def test_no_padding_renders_zero(self) -> None:
        """padding이 없는 textbox → CSS에 padding:0 반영."""
        tb = PptxTextBox(
            left_px=64,
            top_px=100,
            width_px=500,
            height_px=200,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])
            ],
        )
        html = textbox_to_html(tb)
        assert "padding:0px 0px 0px 0px" in html


class TestTextboxPaddingParsing:
    """textbox padding의 JSON 파싱 테스트."""

    def test_padding_parsed_from_json(self) -> None:
        """JSON에 padding이 있으면 PptxTextBox에 반영된다."""
        data = {
            "textboxes": [
                {
                    "left_px": 64,
                    "top_px": 100,
                    "width_px": 500,
                    "height_px": 200,
                    "padding_left_px": 16,
                    "padding_right_px": 20,
                    "padding_top_px": 12,
                    "padding_bottom_px": 14,
                    "paragraphs": [{"runs": [{"text": "테스트", "font_size_pt": 18}]}],
                }
            ],
        }
        spec = parse_slide_spec(data)
        tb = spec.textboxes[0]
        assert tb.padding_left_px == 16
        assert tb.padding_right_px == 20
        assert tb.padding_top_px == 12
        assert tb.padding_bottom_px == 14

    def test_missing_padding_defaults_to_none(self) -> None:
        """JSON에 padding이 없으면 None."""
        data = {
            "textboxes": [
                {
                    "left_px": 64,
                    "top_px": 100,
                    "width_px": 500,
                    "height_px": 200,
                    "paragraphs": [{"runs": [{"text": "테스트", "font_size_pt": 18}]}],
                }
            ],
        }
        spec = parse_slide_spec(data)
        tb = spec.textboxes[0]
        assert tb.padding_left_px is None
        assert tb.padding_right_px is None
        assert tb.padding_top_px is None
        assert tb.padding_bottom_px is None


# ---------------------------------------------------------------------------
# 색상/간격 비개입 확인
# ---------------------------------------------------------------------------


class TestNoColorIntervention:
    """validator가 텍스트 색상을 변경하지 않는 것을 확인한다."""

    def test_text_color_preserved_on_dark_bg(self) -> None:
        """다크 배경에서도 텍스트 색상을 변경하지 않는다."""
        tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[
                        PptxTextRun(text="테스트", font_size_pt=18, color="#222222"),
                    ]
                )
            ],
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            textboxes=[tb],
            shapes=[],
        )
        result = validate_slide_spec(spec)
        assert result.textboxes[0].paragraphs[0].runs[0].color == "#222222"

    def test_none_color_preserved(self) -> None:
        """color=None은 그대로 유지된다."""
        tb = PptxTextBox(
            left_px=64,
            top_px=64,
            width_px=500,
            height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[
                        PptxTextRun(text="테스트", font_size_pt=18),
                    ]
                )
            ],
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            textboxes=[tb],
            shapes=[],
        )
        result = validate_slide_spec(spec)
        assert result.textboxes[0].paragraphs[0].runs[0].color is None

    def test_shape_text_color_preserved(self) -> None:
        """shape의 text_color를 변경하지 않는다."""
        shape = PptxShape(
            left_px=64,
            top_px=64,
            width_px=200,
            height_px=60,
            shape_type="rectangle",
            fill_color="#FFFFFF",
            text="label",
            text_color="#EEEEEE",
            text_size_pt=16,
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            textboxes=[],
            shapes=[shape],
        )
        result = validate_slide_spec(spec)
        assert result.shapes[0].text_color == "#EEEEEE"


# ---------------------------------------------------------------------------
class TestNoGapIntervention:
    """validator가 shape 간 간격을 변경하지 않는 것을 확인한다."""

    def test_close_shapes_position_preserved(self) -> None:
        """가까운 shape의 위치를 변경하지 않는다."""
        s1 = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=50,
            shape_type="rectangle",
            text="A",
            text_size_pt=16,
        )
        s2 = PptxShape(
            left_px=100,
            top_px=153,
            width_px=200,
            height_px=50,
            shape_type="rectangle",
            text="B",
            text_size_pt=16,
        )
        spec = PptxSlideSpec(
            background_color="#FFFFFF",
            textboxes=[],
            shapes=[s1, s2],
        )
        result = validate_slide_spec(spec)
        assert result.shapes[0].top_px == s1.top_px
        assert result.shapes[1].top_px == s2.top_px
