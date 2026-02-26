"""spec_utils 검증 로직 통합 테스트.

폰트 메트릭 기반 텍스트 오버플로우 방지, 여백 강제, 겹침 해소 검증.
"""

from __future__ import annotations

import pytest

from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import validate_slide_spec
from ppt_generator.interfaces.text_measurement import (
    calculate_required_height,
    calculate_required_height_simple_text,
)

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
# 수직 센터링
# ---------------------------------------------------------------------------


class TestVerticalCentering:
    def test_short_content_gets_centered(self) -> None:
        """짧은 콘텐츠 → vertical_alignment "middle"."""
        tb = _tb("짧은 본문", font=20, top_px=180, width_px=1152, height_px=480)
        tb = PptxTextBox(
            left_px=64, top_px=180, width_px=1152, height_px=480,
            vertical_alignment="top",
            paragraphs=[PptxParagraph(
                runs=[PptxTextRun(text="짧은 본문", font_size_pt=20)],
                bullet_level=0,
            )],
        )
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="content"))
        assert result.textboxes[0].vertical_alignment == "middle"

    def test_long_content_stays_top(self) -> None:
        """긴 콘텐츠 → vertical_alignment "top" 유지."""
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text=f"항목 {i}: 설명 텍스트가 길게 들어갑니다", font_size_pt=20)],
                bullet_level=0,
            )
            for i in range(12)
        ]
        tb = PptxTextBox(
            left_px=64, top_px=180, width_px=1152, height_px=480,
            vertical_alignment="top", paragraphs=paras,
        )
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="content"))
        assert result.textboxes[0].vertical_alignment == "top"


# ---------------------------------------------------------------------------
# title/closing 메인 텍스트 위치 고정
# ---------------------------------------------------------------------------


class TestTitleClosingPositionFix:
    def test_title_main_text_fixed_to_260(self) -> None:
        """title 슬라이드 메인 텍스트 → top=260, left=64, width=1152로 보정."""
        tb = _tb("대제목", font=36, top_px=72, width_px=1152, height_px=48)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="title"))
        v = result.textboxes[0]
        assert (v.top_px, v.left_px, v.width_px) == (260, 64, 1152)
        assert v.height_px >= 80

    def test_closing_main_text_fixed_to_240(self) -> None:
        """closing 슬라이드 메인 텍스트 → top=240으로 보정."""
        tb = _tb("감사합니다", font=40, top_px=72, width_px=1152, height_px=48)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="closing"))
        v = result.textboxes[0]
        assert (v.top_px, v.left_px, v.width_px) == (240, 64, 1152)
        assert v.height_px >= 80

    def test_title_small_font_enforced_to_40(self) -> None:
        """title 슬라이드 메인 텍스트 폰트가 40pt 미만이면 40pt로 강제."""
        tb = _tb("대제목", font=24, top_px=260, width_px=1152, height_px=80)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="title"))
        v = result.textboxes[0]
        assert v.paragraphs[0].runs[0].font_size_pt == 40

    def test_closing_small_font_enforced_to_40(self) -> None:
        """closing 슬라이드 메인 텍스트 폰트가 40pt 미만이면 40pt로 강제."""
        tb = _tb("감사합니다", font=20, top_px=240, width_px=1152, height_px=80)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="closing"))
        v = result.textboxes[0]
        assert v.paragraphs[0].runs[0].font_size_pt == 40

    def test_title_large_font_unchanged(self) -> None:
        """title 슬라이드 메인 텍스트 폰트가 40pt 이상이면 변경 없음."""
        tb = _tb("대제목", font=44, top_px=260, width_px=1152, height_px=120)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="title"))
        v = result.textboxes[0]
        assert v.paragraphs[0].runs[0].font_size_pt == 44

    def test_title_long_text_height_expanded(self) -> None:
        """title 슬라이드 긴 제목(2줄) → height가 80 이상으로 확장."""
        long_title = "에이전트 시대의 기초: LLM, 도구, 에이전트, MCP 이해하기"
        tb = _tb(long_title, font=36, top_px=72, width_px=1152, height_px=80)
        result = validate_slide_spec(_slide(textboxes=[tb], slide_type="title"))
        v = result.textboxes[0]
        assert v.top_px == 260
        assert v.height_px >= 80
