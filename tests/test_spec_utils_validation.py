"""spec_utils 검증 로직 통합 테스트.

폰트 메트릭 기반 텍스트 오버플로우 방지 검증.
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
from ppt_generator.interfaces.text_measurement import (
    calculate_required_height,
    calculate_required_height_simple_text,
)


def _make_slide(
    textboxes: list[PptxTextBox] | None = None,
    shapes: list[PptxShape] | None = None,
) -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=textboxes or [],
        shapes=shapes or [],
    )


# ---------------------------------------------------------------------------
# 텍스트박스 검증
# ---------------------------------------------------------------------------


class TestTextboxValidation:
    def test_long_korean_text_expands_height(self) -> None:
        """긴 한글 텍스트 → 줄바꿈 계산 후 높이가 확장되어야 한다."""
        long_text = "가나다라마바사아자차카타파하" * 5  # 70자
        tb = PptxTextBox(
            left_px=40, top_px=40, width_px=500, height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text=long_text, font_size_pt=18)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)

        validated_tb = result.textboxes[0]
        # 필요 높이 계산
        required_h = calculate_required_height(
            tb.paragraphs, tb.width_px,
        )
        # 원래 50px보다 확장되어야 한다
        assert validated_tb.height_px > 50
        # required_h 이상이거나 캔버스 제한에 걸려야 한다
        assert validated_tb.height_px >= min(required_h, 720 - 40 - 40)

    def test_short_text_no_change(self) -> None:
        """짧은 텍스트 → 높이가 충분하면 변경 없음."""
        tb = PptxTextBox(
            left_px=40, top_px=40, width_px=500, height_px=200,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="짧은 텍스트", font_size_pt=18)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)
        assert result.textboxes[0].height_px == 200

    def test_multiple_paragraphs_height(self) -> None:
        """여러 paragraph → 각각의 줄바꿈이 합산되어야 한다."""
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text="첫 번째 항목입니다", font_size_pt=20)],
                bullet_level=0,
            ),
            PptxParagraph(
                runs=[PptxTextRun(text="두 번째 항목입니다", font_size_pt=20)],
                bullet_level=0,
            ),
            PptxParagraph(
                runs=[PptxTextRun(text="세 번째 항목입니다", font_size_pt=20)],
                bullet_level=0,
            ),
        ]
        tb = PptxTextBox(
            left_px=40, top_px=40, width_px=500, height_px=30,
            paragraphs=paras,
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)
        # 3줄 × 20 × 2.0 = 120px 이상이어야 함
        assert result.textboxes[0].height_px >= 120


# ---------------------------------------------------------------------------
# Shape 검증
# ---------------------------------------------------------------------------


class TestShapeValidation:
    def test_shape_with_padding(self) -> None:
        """padding이 있는 shape → padding 반영되어 높이 확장."""
        long_text = "가나다라마바사아자차" * 3
        shape = PptxShape(
            left_px=40, top_px=40, width_px=300, height_px=40,
            shape_type="rounded_rectangle",
            fill_color="#2a2a4e",
            text=long_text,
            text_size_pt=16,
            padding_left_px=16, padding_right_px=16,
            padding_top_px=12, padding_bottom_px=12,
        )
        slide = _make_slide(shapes=[shape])
        result = validate_slide_spec(slide)

        validated_shape = result.shapes[0]
        # padding을 반영한 필요 높이 계산
        required_h = calculate_required_height_simple_text(
            long_text, 16, 300,
            padding_left_px=16, padding_right_px=16,
            padding_top_px=12, padding_bottom_px=12,
        )
        assert validated_shape.height_px >= min(required_h, 720 - 40 - 40)

    def test_shape_paragraphs_validation(self) -> None:
        """shape.paragraphs → 구조화 텍스트 높이 계산 반영."""
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text="카드 제목", font_size_pt=18, bold=True)],
            ),
            PptxParagraph(
                runs=[PptxTextRun(text="카드 본문 내용이 길게 들어갑니다 " * 3, font_size_pt=14)],
            ),
        ]
        shape = PptxShape(
            left_px=40, top_px=200, width_px=280, height_px=40,
            shape_type="rounded_rectangle",
            fill_color="#2a2a4e",
            paragraphs=paras,
            padding_left_px=12, padding_right_px=12,
            padding_top_px=8, padding_bottom_px=8,
        )
        slide = _make_slide(shapes=[shape])
        result = validate_slide_spec(slide)
        assert result.shapes[0].height_px > 40

    def test_decorative_shape_no_change(self) -> None:
        """장식용 shape(텍스트 없음, height≤10) → 텍스트 기반 확장 없음."""
        shape = PptxShape(
            left_px=40, top_px=100, width_px=1200, height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        slide = _make_slide(shapes=[shape])
        result = validate_slide_spec(slide)
        # _clip_rect의 max(10, ...) 보정은 적용되지만, 텍스트 기반 확장은 없어야 함
        assert result.shapes[0].height_px <= 10
        # 텍스트 관련 필드는 그대로
        assert result.shapes[0].text is None
        assert result.shapes[0].paragraphs == []


# ---------------------------------------------------------------------------
# 폰트 축소 검증
# ---------------------------------------------------------------------------


class TestAutofitFontScale:
    def test_canvas_bottom_font_shrink(self) -> None:
        """캔버스 하단 가까이 → 확장 불가능 → 폰트가 축소되어야 한다."""
        long_text = "가나다라마바사아자차카타파하" * 10  # 매우 긴 텍스트
        tb = PptxTextBox(
            left_px=40, top_px=600, width_px=400, height_px=80,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text=long_text, font_size_pt=20)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)

        validated_tb = result.textboxes[0]
        # top=600이므로 max_available = 720-40-600 = 80px
        # 긴 텍스트이므로 폰트 축소가 적용되어야 함
        original_font = 20
        result_font = validated_tb.paragraphs[0].runs[0].font_size_pt
        assert result_font is not None
        assert result_font <= original_font

    def test_font_not_below_minimum(self) -> None:
        """폰트 축소 시 최소 폰트 크기(10pt) 이하로 내려가지 않아야 한다."""
        very_long_text = "가" * 500
        tb = PptxTextBox(
            left_px=40, top_px=650, width_px=200, height_px=30,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text=very_long_text, font_size_pt=20)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)

        for para in result.textboxes[0].paragraphs:
            for run in para.runs:
                if run.font_size_pt is not None:
                    assert run.font_size_pt >= 10
