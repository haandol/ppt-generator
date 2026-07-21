"""Tests for html_renderer image support."""

from __future__ import annotations

import pytest

from ppt_generator.interfaces.line_geometry import line_endpoints
from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.slides.html_renderer import (
    image_to_html,
    spec_to_html_section,
    textbox_to_html,
)
from ppt_generator.tools.slides.html_safety import safe_image_src
from ppt_generator.tools.slides.shape_renderer import shape_to_html
from ppt_generator.tools.slides.text_renderer import paragraph_to_html, run_to_html


class TestImageToHtmlWithSrc:
    """image_src가 주어지면 <img> 태그로 실제 이미지를 표시."""

    def test_renders_img_tag(self):
        img = PptxImage(left_px=10, top_px=20, width_px=300, height_px=200)
        html = image_to_html(img, image_src="images/slide_01_img_01.png")

        assert "<img " in html
        assert 'src="images/slide_01_img_01.png"' in html
        assert "object-fit:contain" in html

    def test_no_placeholder_when_src_present(self):
        img = PptxImage(left_px=0, top_px=0, width_px=100, height_px=100)
        html = image_to_html(img, image_src="images/slide_01_img_01.png")

        assert "IMAGE</span>" not in html
        assert "<svg" not in html

    def test_position_and_size(self):
        img = PptxImage(left_px=50, top_px=60, width_px=400, height_px=300)
        html = image_to_html(img, image_src="images/slide_02_img_01.png")

        assert "left:50px" in html
        assert "top:60px" in html
        assert "width:400px" in html
        assert "height:300px" in html


class TestImageToHtmlPlaceholder:
    """image_src가 없으면 플레이스홀더를 표시."""

    def test_placeholder_when_no_src(self):
        img = PptxImage(left_px=100, top_px=50, width_px=300, height_px=200)
        html = image_to_html(img)

        assert "position:absolute" in html
        assert "left:100px" in html
        assert "top:50px" in html
        assert "width:300px" in html
        assert "height:200px" in html

    def test_placeholder_style(self):
        img = PptxImage(left_px=0, top_px=0, width_px=100, height_px=100)
        html = image_to_html(img)

        assert "rgba(128,128,128,0.15)" in html
        assert "dashed" in html
        assert "<svg" in html
        assert "IMAGE</span>" in html

    def test_placeholder_with_empty_src(self):
        img = PptxImage(left_px=0, top_px=0, width_px=100, height_px=100)
        html = image_to_html(img, image_src="")

        assert "IMAGE</span>" in html
        assert "<img " not in html

    def test_placeholder_with_none_src(self):
        img = PptxImage(left_px=0, top_px=0, width_px=100, height_px=100)
        html = image_to_html(img, image_src=None)

        assert "IMAGE</span>" in html
        assert "<img " not in html

    def test_float_coordinates(self):
        img = PptxImage(left_px=10.5, top_px=20.3, width_px=150.7, height_px=80.2)
        html = image_to_html(img)

        assert "left:10.5px" in html
        assert "top:20.3px" in html
        assert "width:150.7px" in html
        assert "height:80.2px" in html


class TestSpecToHtmlSectionWithImages:
    def test_images_with_srcs_rendered(self):
        spec = PptxSlideSpec(
            images=[PptxImage(left_px=10, top_px=20, width_px=200, height_px=150)],
        )
        html = spec_to_html_section(
            0,
            spec,
            image_srcs=["images/slide_01_img_01.png"],
        )

        assert "<img " in html
        assert 'src="images/slide_01_img_01.png"' in html

    def test_images_without_srcs_show_placeholder(self):
        spec = PptxSlideSpec(
            images=[PptxImage(left_px=10, top_px=20, width_px=200, height_px=150)],
        )
        html = spec_to_html_section(0, spec)

        assert "IMAGE</span>" in html

    def test_images_between_shapes_and_textboxes(self):
        """images는 shapes 다음, textboxes 전에 렌더링되어야 한다."""
        from ppt_generator.interfaces.schemas import PptxShape, PptxTextBox

        spec = PptxSlideSpec(
            shapes=[
                PptxShape(
                    left_px=0, top_px=0, width_px=50, height_px=50, fill_color="#ff0000"
                )
            ],
            images=[PptxImage(left_px=100, top_px=100, width_px=200, height_px=200)],
            textboxes=[
                PptxTextBox(
                    left_px=0, top_px=0, width_px=100, height_px=30, paragraphs=[]
                )
            ],
        )
        html = spec_to_html_section(0, spec)

        shape_pos = html.find("background-color:#ff0000")
        image_pos = html.find("IMAGE</span>")
        assert shape_pos < image_pos

    def test_no_images_no_placeholder(self):
        spec = PptxSlideSpec()
        html = spec_to_html_section(0, spec)

        assert "IMAGE" not in html
        assert "<img " not in html

    def test_multiple_images_mixed(self):
        """image_src가 있는 것과 없는 것이 섞여도 올바르게 렌더링."""
        spec = PptxSlideSpec(
            images=[
                PptxImage(left_px=10, top_px=10, width_px=100, height_px=100),
                PptxImage(left_px=200, top_px=200, width_px=150, height_px=150),
            ],
        )
        html = spec_to_html_section(
            0,
            spec,
            image_srcs=["images/slide_01_img_01.png", ""],
        )

        assert "<img " in html
        assert "IMAGE</span>" in html
        assert "left:10px" in html
        assert "left:200px" in html

    def test_image_srcs_shorter_than_images(self):
        """image_srcs 리스트가 images보다 짧으면 나머지는 플레이스홀더."""
        spec = PptxSlideSpec(
            images=[
                PptxImage(left_px=10, top_px=10, width_px=100, height_px=100),
                PptxImage(left_px=200, top_px=200, width_px=150, height_px=150),
            ],
        )
        html = spec_to_html_section(
            0,
            spec,
            image_srcs=["images/slide_01_img_01.png"],
        )

        assert "<img " in html
        assert "IMAGE</span>" in html

    def test_explicit_z_index_can_place_shape_above_textbox(self):
        spec = PptxSlideSpec(
            textboxes=[
                PptxTextBox(
                    left_px=0,
                    top_px=0,
                    width_px=100,
                    height_px=30,
                    z_index=0,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="behind")])],
                )
            ],
            shapes=[
                PptxShape(
                    left_px=0,
                    top_px=0,
                    width_px=100,
                    height_px=30,
                    z_index=1,
                    fill_color="#FF0000",
                )
            ],
        )

        html = spec_to_html_section(0, spec)

        assert html.index("behind") < html.index("background-color:#FF0000")


class TestBackgroundImageRendering:
    """슬라이드 단위 배경 이미지(`background_image_src`)가 CSS에 적용되는지 검증."""

    def test_background_image_src_applied(self):
        spec = PptxSlideSpec(
            background_color="#FFFFFF",
            background_image_src="images/slide_03_bg.png",
        )
        html = spec_to_html_section(0, spec)

        assert "background-image:url(images/slide_03_bg.png)" in html
        assert "background-size:cover" in html

    def test_background_image_src_overrides_default_bg(self):
        """spec에 배경 이미지가 있으면 title/closing의 기본 배경 base64보다 우선해야 한다."""
        spec = PptxSlideSpec(
            background_color="#FFFFFF",
            background_image_src="images/slide_01_bg.png",
            slide_type="title",
        )
        html = spec_to_html_section(
            0,
            spec,
            bg_image_base64="ZmFsbGJhY2tfYmFzZTY0",
        )

        assert "background-image:url(images/slide_01_bg.png)" in html
        assert "ZmFsbGJhY2tfYmFzZTY0" not in html

    def test_no_background_image_when_unset(self):
        spec = PptxSlideSpec(background_color="#1A2332")
        html = spec_to_html_section(0, spec)

        assert "background-image" not in html
        assert "background-color:#1A2332" in html

    @pytest.mark.parametrize(
        "payload",
        [
            "not-base64);background-image:url(javascript:alert(1))",
            "%%%%",
            "Zm9v===",
        ],
    )
    def test_invalid_background_base64_is_dropped(self, payload):
        html = spec_to_html_section(
            0,
            PptxSlideSpec(background_color="#FFFFFF"),
            bg_image_base64=payload,
        )

        assert "data:image" not in html
        assert "javascript:" not in html


class TestHtmlInjectionSafety:
    def test_attribute_quotes_are_escaped(self):
        spec = PptxSlideSpec(speaker_notes='" onmouseover="alert(1)<x>')
        html = spec_to_html_section(0, spec)

        assert 'onmouseover="alert(1)' not in html
        assert "&quot; onmouseover=&quot;" in html

    def test_dangerous_link_scheme_is_not_clickable(self):
        html = run_to_html(PptxTextRun(text="click", href="javascript:alert(1)"))

        assert html == "click"
        assert "<a " not in html

    def test_escapable_image_source_stays_inside_src_attribute(self):
        image = PptxImage(left_px=0, top_px=0, width_px=100, height_px=100)
        html = image_to_html(image, image_src='x" onerror="alert(1).png')

        assert "<img " in html
        assert 'src="x&quot; onerror=&quot;alert(1).png"' in html
        assert '" onerror="' not in html

    def test_css_color_injection_is_dropped(self):
        shape = PptxShape(
            left_px=0,
            top_px=0,
            width_px=100,
            height_px=100,
            fill_color='red;background-image:url("javascript:alert(1)")',
        )
        html = shape_to_html(shape)

        assert "javascript:" not in html
        assert "background-image" not in html

    def test_svg_path_cannot_break_out_of_attribute(self):
        shape = PptxShape(
            left_px=0,
            top_px=0,
            width_px=100,
            height_px=100,
            shape_type="custom",
            svg_path='100 100 M0 0 L10 10" onload="alert(1)',
        )
        html = shape_to_html(shape)

        assert "<path " not in html
        assert "onload=" not in html

    def test_text_content_is_escaped_but_preserved(self):
        textbox = PptxTextBox(
            left_px=0,
            top_px=0,
            width_px=100,
            height_px=30,
            paragraphs=[PptxParagraph(runs=[PptxTextRun(text='<b>"hello"</b>')])],
        )
        html = spec_to_html_section(0, PptxSlideSpec(textboxes=[textbox]))

        assert "<b>" not in html
        assert '&lt;b&gt;"hello"&lt;/b&gt;' in html

    @pytest.mark.parametrize("bullet_level", [-1, 0])
    def test_paragraph_alignment_injection_is_dropped(self, bullet_level: int) -> None:
        para = PptxParagraph(
            runs=[PptxTextRun(text="safe")],
            bullet_level=bullet_level,
            alignment='left;background-image:url("javascript:alert(1)")',
        )

        html = paragraph_to_html(para)

        assert "javascript:" not in html
        assert "text-align:" not in html

    def test_numeric_fields_are_finite_and_cannot_inject_css(self):
        payload = '0;background-image:url("javascript:alert(1)")'
        textbox = PptxTextBox(
            left_px=payload,
            top_px=float("nan"),
            width_px=float("inf"),
            height_px=30,
            padding_left_px=payload,
            paragraphs=[
                PptxParagraph(runs=[PptxTextRun(text="safe", font_size_pt=payload)])
            ],
        )
        shape = PptxShape(
            left_px=payload,
            top_px=0,
            width_px=100,
            height_px=payload,
            shape_type="line",
            border_width_pt=payload,
        )
        image = PptxImage(
            left_px=payload,
            top_px=0,
            width_px=float("nan"),
            height_px=100,
            corner_radius_px=payload,
        )

        html = "\n".join(
            [
                textbox_to_html(textbox),
                shape_to_html(shape),
                image_to_html(image),
            ]
        )

        assert "javascript:" not in html
        assert "nan" not in html.lower()
        assert "inf" not in html.lower()

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("./images/a.png", "./images/a.png"),
            ("images/team's-photo.png", "images/team's-photo.png"),
            ("images/%2e%2e/secret.png", None),
            ("images/%252e%252e/secret.png", None),
        ],
    )
    def test_relative_image_path_normalization(self, source, expected):
        assert safe_image_src(source) == expected


class TestLineDirectionEndpoints:
    """line bbox 계약: (left,top)=최소 모서리, 부호는 끝점 대각 방향만 결정.

    렌더된 <svg> 의 절대 끝점 = 컨테이너 원점(left-pad, top-pad) + svg 내부 좌표.
    부호가 어떻든 두 끝점이 bbox 의 올바른 대각 꼭짓점(절대좌표)에 와야 한다.
    """

    import re

    def _abs_endpoints(self, shape):
        html = shape_to_html(shape)
        pad = max((shape.border_width_pt or 1) * 2, 8)
        origin_x = shape.left_px - pad
        origin_y = shape.top_px - pad
        m = self.re.search(
            r'x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"', html
        )
        assert m, html
        x1, y1, x2, y2 = (float(g) for g in m.groups())
        return (origin_x + x1, origin_y + y1), (origin_x + x2, origin_y + y2)

    def _line(self, w: float, h: float) -> PptxShape:
        return PptxShape(
            left_px=200,
            top_px=300,
            width_px=w,
            height_px=h,
            shape_type="line",
            border_color="#1E8C86",
            border_width_pt=2,
            end_arrow=True,
        )

    def test_positive_dims_start_min_end_max(self):
        p1, p2 = self._abs_endpoints(self._line(60, 80))
        assert p1 == (200, 300)  # 최소 모서리
        assert p2 == (260, 380)  # 최대 모서리

    def test_negative_height_flips_y_only(self):
        # ↗: bbox 는 그대로 (200,300)~(260,380), y 끝점만 뒤바뀐다.
        p1, p2 = self._abs_endpoints(self._line(60, -80))
        assert p1 == (200, 380)
        assert p2 == (260, 300)

    def test_negative_width_flips_x_only(self):
        # ↙: x 끝점만 뒤바뀐다. top 은 여전히 최소 y.
        p1, p2 = self._abs_endpoints(self._line(-60, 80))
        assert p1 == (260, 300)
        assert p2 == (200, 380)

    def test_both_negative_flips_both(self):
        # ↖: 두 축 모두 뒤바뀜. bbox 최소 모서리(200,300)는 불변.
        p1, p2 = self._abs_endpoints(self._line(-60, -80))
        assert p1 == (260, 380)
        assert p2 == (200, 300)

    @pytest.mark.parametrize(
        ("width", "height", "expected"),
        [
            (60, 80, ((200, 300), (260, 380))),
            (60, -80, ((200, 380), (260, 300))),
            (-60, 80, ((260, 300), (200, 380))),
            (-60, -80, ((260, 380), (200, 300))),
        ],
    )
    def test_shared_endpoint_contract(self, width, height, expected):
        assert line_endpoints(200, 300, width, height) == expected
