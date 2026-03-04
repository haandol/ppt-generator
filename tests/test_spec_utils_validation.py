"""spec_utils 검증 로직 통합 테스트.

폰트 메트릭 기반 텍스트 오버플로우 방지, 여백 강제 검증.
레이아웃 위치 조정은 validator가 수행하지 않으므로 테스트하지 않는다.
"""

from __future__ import annotations

import pytest

from ppt_generator.interfaces.constants import SPEC_VALIDATE_MIN_GAP_PX
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import validate_slide_spec
from ppt_generator.interfaces.spec_utils.parser import parse_slide_spec
from ppt_generator.interfaces.text_measurement import (
    calculate_required_height,
    calculate_required_height_simple_text,
)
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
# 텍스트박스 높이 확장
# ---------------------------------------------------------------------------


class TestTextboxHeightExpansion:
    def test_shape_with_padding_expands_height(self) -> None:
        """padding 있는 shape → 높이 확장."""
        long_text = "가나다라마바사아자차" * 3
        shape = PptxShape(
            left_px=64, top_px=64, width_px=300, height_px=40,
            shape_type="rounded_rectangle", fill_color="#2a2a4e",
            text=long_text, text_size_pt=16,
            padding_left_px=16, padding_right_px=16,
            padding_top_px=12, padding_bottom_px=12,
        )
        result = validate_slide_spec(_slide(shapes=[shape]))
        required_h = calculate_required_height_simple_text(
            long_text, 16, 300,
            padding_left_px=16, padding_right_px=16,
            padding_top_px=12, padding_bottom_px=12,
        )
        assert result.shapes[0].height_px >= min(required_h, _CANVAS_H - _MARGIN - 64)


# ---------------------------------------------------------------------------
# 폰트 축소
# ---------------------------------------------------------------------------


class TestAutofitFontScale:
    def test_canvas_bottom_font_shrink_with_minimum(self) -> None:
        """캔버스 하단 근접 → 폰트 축소, 최소 10pt 보장."""
        very_long = "가" * 500
        tb = _tb(very_long, font=20, top_px=640, width_px=200, height_px=16)
        result = validate_slide_spec(_slide(textboxes=[tb]))
        font = result.textboxes[0].paragraphs[0].runs[0].font_size_pt
        assert font is not None
        assert font < 20
        assert font >= 10


# ---------------------------------------------------------------------------
# 여백 강제
# ---------------------------------------------------------------------------


class TestMarginEnforcement:
    @pytest.mark.parametrize("left,top,check", [
        (10, 64, "left"),
        (64, 10, "top"),
        (1060, 64, "right"),
    ])
    def test_textbox_margin_enforced(self, left: int, top: int, check: str) -> None:
        """textbox가 캔버스 여백(64px) 안으로 보정된다."""
        tb = _tb("테스트", font=16, left_px=left, top_px=top, width_px=200, height_px=50)
        result = validate_slide_spec(_slide(textboxes=[tb]))
        v = result.textboxes[0]
        if check == "left":
            assert v.left_px >= _MARGIN
        elif check == "top":
            assert v.top_px >= _MARGIN
        else:
            assert v.left_px + v.width_px <= _CANVAS_W - _MARGIN

    def test_decorative_shape_bypasses_margin(self) -> None:
        """장식 shape(텍스트 없음, height<=10) → margin 무시, 높이 확장 없음."""
        shape = PptxShape(
            left_px=0, top_px=100, width_px=1280, height_px=3,
            shape_type="rectangle", fill_color="#FF9900",
        )
        result = validate_slide_spec(_slide(shapes=[shape]))
        assert result.shapes[0].left_px == 0
        assert result.shapes[0].height_px <= 10

    def test_vertical_decorative_line_bypasses_margin(self) -> None:
        """세로 꾸밈 라인(width<=10, height>10) → 장식 요소로 인식, margin 무시."""
        shape = PptxShape(
            left_px=64, top_px=192, width_px=10, height_px=120,
            shape_type="rectangle", fill_color="#FF9900",
        )
        result = validate_slide_spec(_slide(shapes=[shape]))
        assert result.shapes[0].height_px == 120


# ---------------------------------------------------------------------------
# 레이아웃 비개입 확인
# ---------------------------------------------------------------------------


class TestNoLayoutIntervention:
    """validator가 레이아웃 위치를 변경하지 않는 것을 확인한다."""

    def test_content_title_position_preserved(self) -> None:
        """content 슬라이드 제목 위치가 변경되지 않는다."""
        tb = PptxTextBox(
            left_px=100, top_px=100, width_px=1000, height_px=60,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="제목", font_size_pt=32, bold=True)])],
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
            left_px=64, top_px=180, width_px=1152, height_px=480,
            vertical_alignment="top",
            paragraphs=[PptxParagraph(
                runs=[PptxTextRun(text="짧은 본문", font_size_pt=20)],
                bullet_level=0,
            )],
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
            left_px=64, top_px=200, width_px=500, height_px=100,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])],
            padding_left_px=16, padding_right_px=16,
            padding_top_px=12, padding_bottom_px=12,
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
            left_px=64, top_px=200, width_px=300, height_px=60,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text=long_text, font_size_pt=18)])],
        )
        # padding 있는 textbox (같은 크기이지만 실제 텍스트 영역이 줄어듦)
        tb_with_pad = PptxTextBox(
            left_px=64, top_px=200, width_px=300, height_px=60,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text=long_text, font_size_pt=18)])],
            padding_left_px=20, padding_right_px=20,
            padding_top_px=16, padding_bottom_px=16,
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
            left_px=64, top_px=100, width_px=500, height_px=200,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])],
            padding_left_px=16, padding_right_px=20,
            padding_top_px=12, padding_bottom_px=14,
        )
        html = textbox_to_html(tb)
        assert "padding:12px 20px 14px 16px" in html

    def test_no_padding_renders_zero(self) -> None:
        """padding이 없는 textbox → CSS에 padding:0 반영."""
        tb = PptxTextBox(
            left_px=64, top_px=100, width_px=500, height_px=200,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=18)])],
        )
        html = textbox_to_html(tb)
        assert "padding:0px 0px 0px 0px" in html


class TestTextboxPaddingParsing:
    """textbox padding의 JSON 파싱 테스트."""

    def test_padding_parsed_from_json(self) -> None:
        """JSON에 padding이 있으면 PptxTextBox에 반영된다."""
        data = {
            "textboxes": [{
                "left_px": 64, "top_px": 100, "width_px": 500, "height_px": 200,
                "padding_left_px": 16, "padding_right_px": 20,
                "padding_top_px": 12, "padding_bottom_px": 14,
                "paragraphs": [{"runs": [{"text": "테스트", "font_size_pt": 18}]}],
            }],
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
            "textboxes": [{
                "left_px": 64, "top_px": 100, "width_px": 500, "height_px": 200,
                "paragraphs": [{"runs": [{"text": "테스트", "font_size_pt": 18}]}],
            }],
        }
        spec = parse_slide_spec(data)
        tb = spec.textboxes[0]
        assert tb.padding_left_px is None
        assert tb.padding_right_px is None
        assert tb.padding_top_px is None
        assert tb.padding_bottom_px is None


# ---------------------------------------------------------------------------
# 텍스트-배경 대비 보정
# ---------------------------------------------------------------------------


class TestContrastCorrection:
    """validator가 WCAG AA 미달 텍스트 색상을 자동 보정하는지 검증."""

    def test_textbox_dark_on_dark_corrected(self) -> None:
        """어두운 배경 + 어두운 텍스트 → 흰색으로 보정."""
        tb = PptxTextBox(
            left_px=64, top_px=64, width_px=500, height_px=50,
            paragraphs=[PptxParagraph(runs=[
                PptxTextRun(text="테스트", font_size_pt=18, color="#222222"),
            ])],
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e", textboxes=[tb], shapes=[],
        )
        result = validate_slide_spec(spec)
        assert result.textboxes[0].paragraphs[0].runs[0].color == "#FFFFFF"

    def test_textbox_good_contrast_unchanged(self) -> None:
        """이미 충분한 대비 → 변경 없음."""
        tb = PptxTextBox(
            left_px=64, top_px=64, width_px=500, height_px=50,
            paragraphs=[PptxParagraph(runs=[
                PptxTextRun(text="테스트", font_size_pt=18, color="#FFFFFF"),
            ])],
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e", textboxes=[tb], shapes=[],
        )
        result = validate_slide_spec(spec)
        assert result.textboxes[0].paragraphs[0].runs[0].color == "#FFFFFF"

    def test_textbox_no_color_unchanged(self) -> None:
        """color=None인 run은 대비 검사 건너뜀."""
        tb = PptxTextBox(
            left_px=64, top_px=64, width_px=500, height_px=50,
            paragraphs=[PptxParagraph(runs=[
                PptxTextRun(text="테스트", font_size_pt=18),
            ])],
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e", textboxes=[tb], shapes=[],
        )
        result = validate_slide_spec(spec)
        assert result.textboxes[0].paragraphs[0].runs[0].color is None

    def test_shape_text_color_corrected(self) -> None:
        """shape의 text_color가 fill_color 대비 부족 시 보정."""
        shape = PptxShape(
            left_px=64, top_px=64, width_px=200, height_px=60,
            shape_type="rectangle",
            fill_color="#FFFFFF",
            text="label", text_color="#EEEEEE", text_size_pt=16,
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e", textboxes=[], shapes=[shape],
        )
        result = validate_slide_spec(spec)
        assert result.shapes[0].text_color == "#000000"

    def test_shape_uses_slide_bg_when_no_fill(self) -> None:
        """fill_color 없는 shape → slide background_color 기준으로 대비 검사."""
        shape = PptxShape(
            left_px=64, top_px=64, width_px=200, height_px=60,
            shape_type="rectangle",
            text="label", text_color="#222222", text_size_pt=16,
        )
        spec = PptxSlideSpec(
            background_color="#1a1a2e", textboxes=[], shapes=[shape],
        )
        result = validate_slide_spec(spec)
        assert result.shapes[0].text_color == "#FFFFFF"

    def test_shape_paragraph_run_contrast(self) -> None:
        """shape paragraphs의 run color도 보정."""
        shape = PptxShape(
            left_px=64, top_px=64, width_px=200, height_px=60,
            shape_type="rectangle",
            fill_color="#000000",
            paragraphs=[PptxParagraph(runs=[
                PptxTextRun(text="test", font_size_pt=16, color="#111111"),
            ])],
        )
        spec = PptxSlideSpec(
            background_color="#FFFFFF", textboxes=[], shapes=[shape],
        )
        result = validate_slide_spec(spec)
        assert result.shapes[0].paragraphs[0].runs[0].color == "#FFFFFF"


# ---------------------------------------------------------------------------
# 최소 간격 보정
# ---------------------------------------------------------------------------


class TestZeroGap:
    """텍스트 있는 shape 간 최소 간격 확보 검증."""

    def test_shapes_too_close_vertically(self) -> None:
        """수직 간격 < 8px → 벌림."""
        s1 = PptxShape(
            left_px=100, top_px=100, width_px=200, height_px=50,
            shape_type="rectangle", text="A", text_size_pt=16,
        )
        s2 = PptxShape(
            left_px=100, top_px=153, width_px=200, height_px=50,
            shape_type="rectangle", text="B", text_size_pt=16,
        )
        # gap = 153 - 150 = 3px < 8px
        spec = PptxSlideSpec(
            background_color="#FFFFFF", textboxes=[], shapes=[s1, s2],
        )
        result = validate_slide_spec(spec)
        gap = result.shapes[1].top_px - (result.shapes[0].top_px + result.shapes[0].height_px)
        assert gap >= SPEC_VALIDATE_MIN_GAP_PX - 0.1

    def test_shapes_far_apart_unchanged(self) -> None:
        """간격 충분 → 변경 없음."""
        s1 = PptxShape(
            left_px=100, top_px=100, width_px=200, height_px=50,
            shape_type="rectangle", text="A", text_size_pt=16,
        )
        s2 = PptxShape(
            left_px=100, top_px=200, width_px=200, height_px=50,
            shape_type="rectangle", text="B", text_size_pt=16,
        )
        # gap = 200 - 150 = 50px > 8px
        spec = PptxSlideSpec(
            background_color="#FFFFFF", textboxes=[], shapes=[s1, s2],
        )
        result = validate_slide_spec(spec)
        assert result.shapes[0].top_px == s1.top_px
        assert result.shapes[1].top_px == s2.top_px

    def test_decorative_shapes_excluded(self) -> None:
        """텍스트 없는 장식 shape은 간격 보정 대상이 아님."""
        s1 = PptxShape(
            left_px=100, top_px=100, width_px=200, height_px=3,
            shape_type="rectangle", fill_color="#FF0000",
        )
        s2 = PptxShape(
            left_px=100, top_px=104, width_px=200, height_px=3,
            shape_type="rectangle", fill_color="#0000FF",
        )
        spec = PptxSlideSpec(
            background_color="#FFFFFF", textboxes=[], shapes=[s1, s2],
        )
        result = validate_slide_spec(spec)
        # 장식 요소 → 간격 보정 안 함, 위치 그대로 (margin 보정만 적용될 수 있음)
        assert result.shapes[0].height_px <= 10
        assert result.shapes[1].height_px <= 10
