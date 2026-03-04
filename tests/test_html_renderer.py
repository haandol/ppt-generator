"""Tests for html_renderer image support."""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxImage, PptxSlideSpec
from ppt_generator.tools.slides.html_renderer import image_to_html, spec_to_html_section


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
            0, spec, image_srcs=["images/slide_01_img_01.png"],
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
            shapes=[PptxShape(left_px=0, top_px=0, width_px=50, height_px=50, fill_color="#ff0000")],
            images=[PptxImage(left_px=100, top_px=100, width_px=200, height_px=200)],
            textboxes=[PptxTextBox(left_px=0, top_px=0, width_px=100, height_px=30, paragraphs=[])],
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
            0, spec, image_srcs=["images/slide_01_img_01.png", ""],
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
            0, spec, image_srcs=["images/slide_01_img_01.png"],
        )

        assert "<img " in html
        assert "IMAGE</span>" in html
