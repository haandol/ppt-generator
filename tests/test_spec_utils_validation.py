"""spec_utils 검증 로직 통합 테스트.

폰트 메트릭 기반 텍스트 오버플로우 방지, 여백 강제, 겹침 해소 검증.
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

# 검증 로직의 margin (64px)
_MARGIN = 64


def _make_slide(
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
# 텍스트박스 검증
# ---------------------------------------------------------------------------


class TestTextboxValidation:
    def test_long_korean_text_expands_height(self) -> None:
        """긴 한글 텍스트 → 줄바꿈 계산 후 높이가 확장되어야 한다."""
        long_text = "가나다라마바사아자차카타파하" * 5  # 70자
        tb = PptxTextBox(
            left_px=64, top_px=64, width_px=500, height_px=50,
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
        assert validated_tb.height_px >= min(required_h, 720 - _MARGIN - 64)

    def test_short_text_no_change(self) -> None:
        """짧은 텍스트 → 높이가 충분하면 변경 없음."""
        tb = PptxTextBox(
            left_px=64, top_px=64, width_px=500, height_px=200,
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
            left_px=64, top_px=64, width_px=500, height_px=30,
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
            left_px=64, top_px=64, width_px=300, height_px=40,
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
        assert validated_shape.height_px >= min(required_h, 720 - _MARGIN - 64)

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
            left_px=64, top_px=200, width_px=280, height_px=40,
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
            left_px=64, top_px=100, width_px=1152, height_px=3,
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
            left_px=64, top_px=600, width_px=400, height_px=56,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text=long_text, font_size_pt=20)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)

        validated_tb = result.textboxes[0]
        # top=600이므로 max_available = 720-64-600 = 56px
        # 긴 텍스트이므로 폰트 축소가 적용되어야 함
        original_font = 20
        result_font = validated_tb.paragraphs[0].runs[0].font_size_pt
        assert result_font is not None
        assert result_font <= original_font

    def test_font_not_below_minimum(self) -> None:
        """폰트 축소 시 최소 폰트 크기(10pt) 이하로 내려가지 않아야 한다."""
        very_long_text = "가" * 500
        tb = PptxTextBox(
            left_px=64, top_px=640, width_px=200, height_px=16,
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


# ---------------------------------------------------------------------------
# 여백 강제 검증
# ---------------------------------------------------------------------------


class TestMarginEnforcement:
    def test_textbox_left_margin_enforced(self) -> None:
        """left=10 → 64으로 보정되어야 한다."""
        tb = PptxTextBox(
            left_px=10, top_px=64, width_px=200, height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="테스트", font_size_pt=16)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)
        assert result.textboxes[0].left_px >= _MARGIN

    def test_textbox_right_margin_enforced(self) -> None:
        """left+width가 캔버스 오른쪽 margin을 초과 → width가 축소되어 right가 1216 이하."""
        tb = PptxTextBox(
            left_px=1060, top_px=64, width_px=200, height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="테스트", font_size_pt=16)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)
        validated_tb = result.textboxes[0]
        assert validated_tb.left_px + validated_tb.width_px <= 1280 - _MARGIN

    def test_textbox_top_margin_enforced(self) -> None:
        """top=10 → 64으로 보정되어야 한다."""
        tb = PptxTextBox(
            left_px=64, top_px=10, width_px=200, height_px=50,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="테스트", font_size_pt=16)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb])
        result = validate_slide_spec(slide)
        assert result.textboxes[0].top_px >= _MARGIN

    def test_decorative_shape_no_margin(self) -> None:
        """장식 shape(텍스트 없음, height<=10)는 left=0 허용."""
        shape = PptxShape(
            left_px=0, top_px=100, width_px=1280, height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        slide = _make_slide(shapes=[shape])
        result = validate_slide_spec(slide)
        # 장식 요소는 left=0 그대로 허용
        assert result.shapes[0].left_px == 0

    def test_shape_with_text_margin_enforced(self) -> None:
        """텍스트가 있는 shape도 여백이 강제되어야 한다."""
        shape = PptxShape(
            left_px=10, top_px=10, width_px=200, height_px=50,
            shape_type="rounded_rectangle",
            fill_color="#2a2a4e",
            text="카드 텍스트",
            text_size_pt=16,
        )
        slide = _make_slide(shapes=[shape])
        result = validate_slide_spec(slide)
        validated_shape = result.shapes[0]
        assert validated_shape.left_px >= _MARGIN
        assert validated_shape.top_px >= _MARGIN


# ---------------------------------------------------------------------------
# 겹침 해소 검증
# ---------------------------------------------------------------------------


class TestOverlapDetection:
    def test_no_overlap_no_change(self) -> None:
        """겹침이 없으면 위치가 변경되지 않아야 한다."""
        tb1 = PptxTextBox(
            left_px=64, top_px=96, width_px=500, height_px=56,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="제목", font_size_pt=32)],
                ),
            ],
        )
        tb2 = PptxTextBox(
            left_px=64, top_px=180, width_px=500, height_px=200,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="본문", font_size_pt=18)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb1, tb2])
        result = validate_slide_spec(slide)
        assert result.textboxes[0].top_px == 96
        assert result.textboxes[1].top_px == 180

    def test_vertical_overlap_pushdown(self) -> None:
        """수직 겹침 → 아래 요소가 push-down되어야 한다."""
        tb1 = PptxTextBox(
            left_px=64, top_px=96, width_px=500, height_px=100,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="제목", font_size_pt=32)],
                ),
            ],
        )
        # top=150으로 tb1(top=96, height=100)과 겹침
        tb2 = PptxTextBox(
            left_px=64, top_px=150, width_px=500, height_px=200,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="본문", font_size_pt=18)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb1, tb2])
        result = validate_slide_spec(slide)
        # tb2가 tb1의 아래쪽으로 밀려야 함 (tb1.top + tb1.height + gap)
        assert result.textboxes[1].top_px >= result.textboxes[0].top_px + result.textboxes[0].height_px

    def test_pushdown_respects_canvas_bottom(self) -> None:
        """push-down 후 캔버스 초과 시 height가 축소되어야 한다."""
        tb1 = PptxTextBox(
            left_px=64, top_px=500, width_px=500, height_px=100,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="상단", font_size_pt=18)],
                ),
            ],
        )
        # 겹치게 배치
        tb2 = PptxTextBox(
            left_px=64, top_px=550, width_px=500, height_px=200,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="하단", font_size_pt=18)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb1, tb2])
        result = validate_slide_spec(slide)
        validated_tb2 = result.textboxes[1]
        # 캔버스 하단(656 = 720 - 64) 초과하면 안 됨
        assert validated_tb2.top_px + validated_tb2.height_px <= 720 - _MARGIN

    def test_decorative_excluded(self) -> None:
        """장식 shape는 겹침 해소에서 제외되어야 한다."""
        # 장식용 구분선이 텍스트박스와 겹침
        decorative = PptxShape(
            left_px=64, top_px=155, width_px=1152, height_px=3,
            shape_type="rectangle",
            fill_color="#FF9900",
        )
        tb = PptxTextBox(
            left_px=64, top_px=150, width_px=500, height_px=200,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="본문", font_size_pt=18)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb], shapes=[decorative])
        result = validate_slide_spec(slide)
        # 장식 shape 위치는 변경되지 않아야 함
        assert result.shapes[0].top_px == 155

    def test_shape_textbox_overlap(self) -> None:
        """shape와 textbox 간 겹침도 해소되어야 한다."""
        tb = PptxTextBox(
            left_px=64, top_px=96, width_px=400, height_px=100,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="제목", font_size_pt=32)],
                ),
            ],
        )
        shape = PptxShape(
            left_px=64, top_px=150, width_px=380, height_px=200,
            shape_type="rounded_rectangle",
            fill_color="#2a2a4e",
            text="카드 내용",
            text_size_pt=16,
        )
        slide = _make_slide(textboxes=[tb], shapes=[shape])
        result = validate_slide_spec(slide)
        # shape가 textbox 아래로 밀려야 함
        tb_result = result.textboxes[0]
        shape_result = result.shapes[0]
        assert shape_result.top_px >= tb_result.top_px + tb_result.height_px

    def test_overlap_gap_is_16px(self) -> None:
        """겹침 해소 시 간격이 16px 이상이어야 한다."""
        tb1 = PptxTextBox(
            left_px=64, top_px=96, width_px=500, height_px=100,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="제목", font_size_pt=32)],
                ),
            ],
        )
        # tb1과 겹치게 배치
        tb2 = PptxTextBox(
            left_px=64, top_px=150, width_px=500, height_px=200,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="본문", font_size_pt=18)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb1, tb2])
        result = validate_slide_spec(slide)
        tb1_bottom = result.textboxes[0].top_px + result.textboxes[0].height_px
        tb2_top = result.textboxes[1].top_px
        # 간격이 16px 이상이어야 함
        assert tb2_top - tb1_bottom >= 16

    def test_container_child_no_pushdown(self) -> None:
        """컨테이너-자식 관계(완전 포함) → push-down하지 않아야 한다."""
        # 큰 배경 패널
        container = PptxShape(
            left_px=64, top_px=180, width_px=1152, height_px=440,
            shape_type="rounded_rectangle",
            fill_color="#1B2A3D",
            text="",
        )
        # 컨테이너 안에 완전히 포함되는 작은 블록
        child = PptxShape(
            left_px=100, top_px=200, width_px=200, height_px=100,
            shape_type="rounded_rectangle",
            fill_color="#2E3D50",
            text="블록 A",
            text_size_pt=16,
        )
        slide = _make_slide(shapes=[container, child])
        result = validate_slide_spec(slide)
        # child가 push-down되지 않고 원래 위치를 유지해야 함
        assert result.shapes[1].top_px == 200

    def test_line_shape_no_pushdown(self) -> None:
        """line shape(화살표)는 다른 shape와 겹쳐도 push-down하지 않아야 한다."""
        block = PptxShape(
            left_px=100, top_px=200, width_px=200, height_px=100,
            shape_type="rounded_rectangle",
            fill_color="#2E3D50",
            text="블록",
            text_size_pt=16,
        )
        # 블록과 겹치는 화살표
        arrow = PptxShape(
            left_px=150, top_px=250, width_px=300, height_px=20,
            shape_type="line",
            border_color="#FF9900",
            border_width_pt=2,
        )
        slide = _make_slide(shapes=[block, arrow])
        result = validate_slide_spec(slide)
        # arrow가 push-down되지 않아야 함
        assert result.shapes[1].top_px == 250


# ---------------------------------------------------------------------------
# 수직 센터링 검증
# ---------------------------------------------------------------------------


class TestVerticalCentering:
    def test_short_content_gets_centered(self) -> None:
        """짧은 콘텐츠 → vertical_alignment이 "middle"로 변경되어야 한다."""
        tb = PptxTextBox(
            left_px=64, top_px=180, width_px=1152, height_px=480,
            vertical_alignment="top",
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="짧은 본문", font_size_pt=20)],
                    bullet_level=0,
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb], slide_type="content")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].vertical_alignment == "middle"

    def test_long_content_stays_top(self) -> None:
        """긴 콘텐츠 → vertical_alignment이 "top"으로 유지되어야 한다."""
        # 많은 paragraph로 콘텐츠 높이를 height_px의 65% 이상으로 만듦
        paras = [
            PptxParagraph(
                runs=[PptxTextRun(text=f"항목 {i}: 상세한 설명 텍스트가 여기에 길게 들어갑니다", font_size_pt=20)],
                bullet_level=0,
            )
            for i in range(12)
        ]
        tb = PptxTextBox(
            left_px=64, top_px=180, width_px=1152, height_px=480,
            vertical_alignment="top",
            paragraphs=paras,
        )
        slide = _make_slide(textboxes=[tb], slide_type="content")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].vertical_alignment == "top"

    def test_title_slide_no_centering(self) -> None:
        """title 슬라이드 → 수직 센터링이 적용되지 않아야 한다."""
        tb = PptxTextBox(
            left_px=64, top_px=180, width_px=1152, height_px=480,
            vertical_alignment="top",
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="짧은 본문", font_size_pt=20)],
                    bullet_level=0,
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb], slide_type="title")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].vertical_alignment == "top"


# ---------------------------------------------------------------------------
# title/closing 메인 텍스트 위치 고정
# ---------------------------------------------------------------------------


class TestTitleClosingMainPositionFix:
    """title/closing 슬라이드 첫 번째 textbox 좌표 보정 테스트."""

    def test_title_main_text_fixed_to_260(self) -> None:
        """title 슬라이드의 메인 텍스트가 top=260으로 보정된다."""
        tb = PptxTextBox(
            left_px=64, top_px=72, width_px=1152, height_px=48,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="대제목", font_size_pt=36, bold=True)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb], slide_type="title")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].top_px == 260
        assert result.textboxes[0].left_px == 64
        assert result.textboxes[0].width_px == 1152
        assert result.textboxes[0].height_px == 80

    def test_closing_main_text_fixed_to_240(self) -> None:
        """closing 슬라이드의 메인 텍스트가 top=240으로 보정된다."""
        tb = PptxTextBox(
            left_px=64, top_px=72, width_px=1152, height_px=48,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="감사합니다", font_size_pt=40, bold=True)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb], slide_type="closing")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].top_px == 240
        assert result.textboxes[0].left_px == 64
        assert result.textboxes[0].width_px == 1152
        assert result.textboxes[0].height_px == 80

    def test_already_correct_position_unchanged(self) -> None:
        """이미 올바른 위치이면 변경하지 않는다."""
        tb = PptxTextBox(
            left_px=64, top_px=260, width_px=1152, height_px=80,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="대제목", font_size_pt=36, bold=True)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb], slide_type="title")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].top_px == 260
        assert result.textboxes[0].height_px == 80

    def test_second_textbox_not_moved(self) -> None:
        """두 번째 textbox(부제목)는 이동하지 않는다."""
        title_tb = PptxTextBox(
            left_px=64, top_px=72, width_px=1152, height_px=48,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="대제목", font_size_pt=36, bold=True)],
                ),
            ],
        )
        subtitle_tb = PptxTextBox(
            left_px=64, top_px=360, width_px=1152, height_px=100,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="부제목", font_size_pt=16)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[title_tb, subtitle_tb], slide_type="title")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].top_px == 260  # 보정됨
        assert result.textboxes[1].top_px == 360  # 변경 없음

    def test_content_slide_not_affected(self) -> None:
        """content 슬라이드는 이 보정의 영향을 받지 않는다."""
        tb = PptxTextBox(
            left_px=64, top_px=72, width_px=1152, height_px=48,
            paragraphs=[
                PptxParagraph(
                    runs=[PptxTextRun(text="콘텐츠 제목", font_size_pt=32, bold=True)],
                ),
            ],
        )
        slide = _make_slide(textboxes=[tb], slide_type="content")
        result = validate_slide_spec(slide)
        assert result.textboxes[0].top_px == 72  # content는 top=72 유지
