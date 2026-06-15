import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
    SlidesResponse,
)
from ppt_generator.tools.slides.html_renderer import shape_to_html
from ppt_generator.tools.slides.service import SlidesService


def _make_design_spec(num_slides: int = 1) -> DesignSpec:
    slides = []
    for i in range(num_slides):
        slides.append(
            PptxSlideSpec(
                background_color="#1a1a2e",
                textboxes=[
                    PptxTextBox(
                        left_px=40,
                        top_px=40,
                        width_px=600,
                        height_px=60,
                        paragraphs=[
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(text=f"슬라이드 {i}", font_size_pt=32)
                                ]
                            )
                        ],
                    ),
                ],
                speaker_notes=f"노트 {i}" if i > 0 else "",
            ),
        )
    return DesignSpec(slides=slides)


@pytest.fixture
def service():
    return SlidesService()


class TestGenerateFromDesignSpec:
    def test_returns_slides_response(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        assert isinstance(response, SlidesResponse)
        assert response.session_id
        assert len(response.slide_htmls) == 1
        assert response.container_html

    def test_slide_html_is_complete_document(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        slide_html = response.slide_htmls[0]
        assert "<!DOCTYPE html>" in slide_html
        assert "<section" in slide_html
        assert "<body" in slide_html
        assert "</html>" in slide_html

    def test_container_html_has_iframes(self, service):
        spec = _make_design_spec(3)
        response = service.generate_from_design_spec(spec)

        assert "iframe" in response.container_html
        assert 'src="slides/slide_01.html"' in response.container_html
        assert 'src="slides/slide_02.html"' in response.container_html
        assert 'src="slides/slide_03.html"' in response.container_html

    def test_container_html_has_slide_numbers(self, service):
        spec = _make_design_spec(3)
        response = service.generate_from_design_spec(spec)

        assert "1 / 3" in response.container_html
        assert "2 / 3" in response.container_html
        assert "3 / 3" in response.container_html

    def test_raises_on_empty_slides(self, service):
        spec = DesignSpec(slides=[])
        with pytest.raises(ValueError, match="디자인 스펙에 슬라이드가 없습니다"):
            service.generate_from_design_spec(spec)

    def test_stores_session(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        html = service.get_session_html(response.session_id)
        assert html == response.container_html

    def test_multiple_slides(self, service):
        spec = _make_design_spec(3)
        response = service.generate_from_design_spec(spec)

        assert len(response.slide_htmls) == 3
        assert "slide-0" in response.slide_htmls[0]
        assert "slide-1" in response.slide_htmls[1]
        assert "slide-2" in response.slide_htmls[2]

    def test_speaker_notes_in_slide_html(self, service):
        spec = _make_design_spec(2)
        response = service.generate_from_design_spec(spec)

        assert "data-speaker-notes" in response.slide_htmls[1]
        assert "노트 1" in response.slide_htmls[1]

    def test_background_color_in_slide_html(self, service):
        spec = _make_design_spec()
        response = service.generate_from_design_spec(spec)

        assert "#1a1a2e" in response.slide_htmls[0]


class TestBgImagePolicy:
    """title/closing 배경 자동 주입이 bg_image_policy 로 제어되는지 검증 (design/0016)."""

    @staticmethod
    def _title_spec() -> DesignSpec:
        return DesignSpec(
            slides=[
                PptxSlideSpec(
                    background_color=None,
                    slide_type="title",
                    textboxes=[
                        PptxTextBox(
                            left_px=64,
                            top_px=260,
                            width_px=1152,
                            height_px=80,
                            paragraphs=[
                                PptxParagraph(
                                    runs=[PptxTextRun(text="제목", font_size_pt=40)]
                                )
                            ],
                        )
                    ],
                    speaker_notes="",
                )
            ]
        )

    def test_title_gets_bg_by_default(self, service):
        resp = service.generate_from_design_spec(self._title_spec())
        assert "data:image" in resp.slide_htmls[0]

    def test_title_no_bg_when_policy_none(self, service):
        resp = service.generate_from_design_spec(
            self._title_spec(), bg_image_policy="none"
        )
        assert "data:image" not in resp.slide_htmls[0]

    def test_single_render_respects_policy_none(self):
        spec = self._title_spec().slides[0]
        html = SlidesService.render_single_slide_html(0, spec, bg_image_policy="none")
        assert "data:image" not in html

    def test_single_render_bg_by_default(self):
        spec = self._title_spec().slides[0]
        html = SlidesService.render_single_slide_html(0, spec)
        assert "data:image" in html


class TestGetSessionHtml:
    def test_raises_on_invalid_session(self, service):
        with pytest.raises(KeyError, match="세션을 찾을 수 없습니다"):
            service.get_session_html("nonexistent-id")


class TestLineShapeHtml:
    """line shape가 SVG로 렌더링되고 화살표/대시가 올바르게 표현되는지 검증."""

    @staticmethod
    def _make_line(
        *,
        width_px: int = 200,
        height_px: int = 0,
        end_arrow: bool = False,
        start_arrow: bool = False,
        dash_style: str | None = None,
    ) -> PptxShape:
        return PptxShape(
            left_px=100,
            top_px=300,
            width_px=width_px,
            height_px=height_px,
            shape_type="line",
            border_color="#FFC000",
            border_width_pt=2,
            end_arrow=end_arrow,
            start_arrow=start_arrow,
            dash_style=dash_style,
        )

    def test_line_renders_as_svg(self):
        html = shape_to_html(self._make_line())
        assert "<svg" in html
        assert "<line" in html
        assert "<div" not in html

    def test_end_arrow_marker(self):
        html = shape_to_html(self._make_line(end_arrow=True))
        assert 'marker-end="url(#ah-end)"' in html
        assert 'id="ah-end"' in html
        assert "<polygon" in html

    def test_start_arrow_marker(self):
        html = shape_to_html(self._make_line(start_arrow=True))
        assert 'marker-start="url(#ah-start)"' in html
        assert 'id="ah-start"' in html

    def test_bidirectional_arrows(self):
        html = shape_to_html(self._make_line(end_arrow=True, start_arrow=True))
        assert "ah-end" in html
        assert "ah-start" in html

    def test_no_arrows_no_markers(self):
        html = shape_to_html(self._make_line())
        assert "marker-end" not in html
        assert "marker-start" not in html
        assert "<defs>" not in html

    def test_dash_style(self):
        html = shape_to_html(self._make_line(dash_style="dash"))
        assert "stroke-dasharray" in html

    def test_dot_style(self):
        html = shape_to_html(self._make_line(dash_style="dot"))
        assert "stroke-dasharray" in html

    def test_stroke_color(self):
        html = shape_to_html(self._make_line())
        assert 'stroke="#FFC000"' in html

    def test_vertical_line(self):
        shape = PptxShape(
            left_px=640,
            top_px=200,
            width_px=0,
            height_px=100,
            shape_type="line",
            border_color="#FF9900",
            border_width_pt=2,
            end_arrow=True,
        )
        html = shape_to_html(shape)
        assert "<svg" in html
        assert "ah-end" in html

    def test_horizontal_snap_short_arrow(self):
        """width=28, height=10 (하단 화살표 패턴)도 수평선으로 보정되어야 한다."""
        html = shape_to_html(self._make_line(width_px=28, height_px=10, end_arrow=True))
        # height=10 <= 12(threshold) → h=0으로 보정 → y 좌표 동일
        import re

        y_vals = re.findall(r'y[12]="([^"]+)"', html)
        assert len(y_vals) == 2
        assert y_vals[0] == y_vals[1], "수평선이므로 y1 == y2"
        assert "ah-end" in html

    def test_horizontal_snap_wide_arrow(self):
        """width=48, height=10 (상단 화살표 패턴)도 수평선으로 보정되어야 한다."""
        import re

        html = shape_to_html(self._make_line(width_px=48, height_px=10))
        y_vals = re.findall(r'y[12]="([^"]+)"', html)
        assert len(y_vals) == 2
        assert y_vals[0] == y_vals[1], "수평선이므로 y1 == y2"

    def test_vertical_snap_small_width(self):
        """width=10, height=56 (수직 대시선 패턴)은 수직선으로 보정되어야 한다."""
        import re

        shape = PptxShape(
            left_px=1100,
            top_px=472,
            width_px=10,
            height_px=56,
            shape_type="line",
            border_color="#3B4A5C",
            border_width_pt=1.5,
            dash_style="dash",
        )
        html = shape_to_html(shape)
        x_vals = re.findall(r'x[12]="([^"]+)"', html)
        assert len(x_vals) == 2
        assert x_vals[0] == x_vals[1], "수직선이므로 x1 == x2"

    def test_short_arrow_scales_down_marker(self):
        """짧은 화살표(line_length < _ARROW_SIZE)에서 화살표 머리가 자동 축소되어야 한다."""
        import re

        # 10px 수직선 (스냅 후 h=0 → line_length=width 사용)
        # width=10도 스냅되므로, 스냅 안 되는 15px 수직선 테스트
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=0,
            height_px=15,
            shape_type="line",
            border_color="#FFC000",
            border_width_pt=2,
            end_arrow=True,
        )
        html = shape_to_html(shape)
        # markerWidth가 기본값(14)보다 작아야 한다
        marker_widths = re.findall(r'markerWidth="([^"]+)"', html)
        assert len(marker_widths) >= 1
        assert float(marker_widths[0]) < 14, "짧은 선에서 화살표 머리가 축소되어야 한다"

    def test_long_arrow_keeps_full_marker(self):
        """긴 화살표에서 화살표 머리가 기본 크기를 유지해야 한다."""
        import re

        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=0,
            height_px=100,
            shape_type="line",
            border_color="#FFC000",
            border_width_pt=2,
            end_arrow=True,
        )
        html = shape_to_html(shape)
        marker_widths = re.findall(r'markerWidth="([^"]+)"', html)
        assert len(marker_widths) >= 1
        assert float(marker_widths[0]) == 14, (
            "긴 선에서 화살표 머리가 기본 크기여야 한다"
        )

    def test_diagonal_line_preserved(self):
        """width와 height가 모두 threshold 초과이면 사선이 유지되어야 한다."""
        import re

        html = shape_to_html(self._make_line(width_px=100, height_px=100))
        x_vals = re.findall(r'x[12]="([^"]+)"', html)
        y_vals = re.findall(r'y[12]="([^"]+)"', html)
        assert float(x_vals[1]) > float(x_vals[0]), "x2 > x1"
        assert float(y_vals[1]) > float(y_vals[0]), "y2 > y1"

    def test_negative_height_diagonal(self):
        """음수 height → 좌하→우상(↗) 대각선: y1 > y2이어야 한다."""
        import re

        html = shape_to_html(self._make_line(width_px=100, height_px=-100))
        y_vals = re.findall(r'y[12]="([^"]+)"', html)
        assert len(y_vals) == 2
        assert float(y_vals[0]) > float(y_vals[1]), "↗ 대각선이므로 y1 > y2"

    def test_negative_height_snap(self):
        """음수 height(-10)도 snap threshold 내이면 수평선으로 보정되어야 한다."""
        import re

        html = shape_to_html(self._make_line(width_px=200, height_px=-10))
        y_vals = re.findall(r'y[12]="([^"]+)"', html)
        assert len(y_vals) == 2
        assert y_vals[0] == y_vals[1], "수평선이므로 y1 == y2"

    def test_negative_height_arrow_marker_size(self):
        """음수 height 대각선에서도 화살표 머리 크기가 정상 계산되어야 한다."""
        import re

        shape = PptxShape(
            left_px=100,
            top_px=300,
            width_px=200,
            height_px=-200,
            shape_type="line",
            border_color="#FFC000",
            border_width_pt=2,
            end_arrow=True,
        )
        html = shape_to_html(shape)
        marker_widths = re.findall(r'markerWidth="([^"]+)"', html)
        assert len(marker_widths) >= 1
        assert float(marker_widths[0]) == 14, (
            "긴 대각선에서 화살표 머리가 기본 크기여야 한다"
        )

    def test_negative_height_container_top_anchored_at_top_px(self):
        """음수 height(↗) 대각선의 SVG 컨테이너 top은 항상 shape.top_px - pad 여야 한다.

        과거에는 음수 height 시 container_top = top_px + h - pad 로 계산해 박스가
        |h|만큼 위로 떠올라 화살표가 의도한 위치보다 위에 그려지던 회귀가 있었다.
        """
        import re

        shape = PptxShape(
            left_px=854,
            top_px=344,
            width_px=218,
            height_px=-60,
            shape_type="line",
            border_color="#FF9900",
            border_width_pt=2,
        )
        html = shape_to_html(shape)
        top_match = re.search(r"top:(-?\d+(?:\.\d+)?)px;", html)
        assert top_match is not None
        # pad = max(stroke_width*2, 8) = max(4, 8) = 8
        # 음수 height fix: container_top = top_px - pad = 344 - 8 = 336
        assert float(top_match.group(1)) == 336.0, (
            f"음수 height 박스 top은 top_px-pad(=336)이어야 함, 실제={top_match.group(1)}"
        )


class TestClipPathShapes:
    """clip-path 기반 도형 HTML 렌더링 테스트."""

    @pytest.mark.parametrize(
        "shape_type",
        [
            "up_arrow",
            "down_arrow",
            "left_arrow",
            "right_arrow",
            "chevron",
            "triangle",
            "diamond",
            "pentagon",
            "hexagon",
            "trapezoid",
            "parallelogram",
            "cross",
            "star_4",
            "star_5",
            "heart",
            "flowchart_decision",
        ],
    )
    def test_clip_path_applied(self, shape_type):
        """polygon clip-path가 적용된 도형은 clip-path CSS가 포함되어야 한다."""
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=200,
            shape_type=shape_type,
            fill_color="#4472C4",
        )
        html = shape_to_html(shape)
        assert "clip-path:polygon(" in html

    def test_flowchart_process_no_clip(self):
        """flowchart_process는 rectangle과 동일하게 clip-path 없이 렌더링."""
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=200,
            height_px=200,
            shape_type="flowchart_process",
            fill_color="#4472C4",
        )
        html = shape_to_html(shape)
        assert "clip-path" not in html

    def test_flowchart_terminator_border_radius(self):
        """flowchart_terminator는 큰 border-radius로 렌더링."""
        shape = PptxShape(
            left_px=100,
            top_px=100,
            width_px=300,
            height_px=100,
            shape_type="flowchart_terminator",
            fill_color="#4472C4",
        )
        html = shape_to_html(shape)
        assert "border-radius:50.0px" in html
        assert "clip-path" not in html
