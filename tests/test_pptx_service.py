from pathlib import Path
from unittest.mock import patch

import pytest
from pptx import Presentation
from pptx.oxml.ns import qn

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    ExportPptxResponse,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.pptx.service import ExportService


def _make_design_spec() -> DesignSpec:
    return DesignSpec(slides=[
        PptxSlideSpec(
            background_color="#1a1a2e",
            textboxes=[
                PptxTextBox(
                    left_px=40, top_px=40, width_px=600, height_px=60,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="제목", font_size_pt=32, bold=True, color="#ffffff")])],
                ),
                PptxTextBox(
                    left_px=40, top_px=120, width_px=600, height_px=400,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="본문 텍스트", font_size_pt=18, color="#cccccc")])],
                ),
            ],
            shapes=[
                PptxShape(
                    left_px=700, top_px=120, width_px=500, height_px=400,
                    fill_color="#2a2a4e", shape_type="rounded_rectangle",
                    text="도형 텍스트", text_color="#ffffff",
                ),
            ],
            speaker_notes="발표자 노트",
        ),
    ])


@pytest.fixture
def service():
    return ExportService()


class TestExportFromDesignSpec:
    def test_creates_pptx_file(self, service, tmp_path):
        spec = _make_design_spec()
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        path = Path(response.pptx_path)
        assert path.exists()
        assert path.suffix == ".pptx"

    def test_raises_on_empty_slides(self, service):
        spec = DesignSpec(slides=[])
        with pytest.raises(ValueError, match="디자인 스펙에 슬라이드가 없습니다"):
            service.export_from_design_spec(spec)

    def test_extracts_text(self, service, tmp_path):
        spec = _make_design_spec()
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        all_text = " ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame)
        assert "제목" in all_text
        assert "본문 텍스트" in all_text

    def test_preserves_speaker_notes(self, service, tmp_path):
        spec = _make_design_spec()
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        assert slide.notes_slide.notes_text_frame.text == "발표자 노트"

    def test_preserves_background_color(self, service, tmp_path):
        spec = _make_design_spec()
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        fill = slide.background.fill
        assert fill.fore_color.rgb is not None
        assert str(fill.fore_color.rgb) == "1A1A2E"

    def test_multiple_slides(self, service, tmp_path):
        spec = DesignSpec(slides=[
            PptxSlideSpec(
                background_color="#111111",
                textboxes=[PptxTextBox(
                    left_px=40, top_px=40, width_px=600, height_px=60,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text=f"슬라이드 {i}")])],
                )],
            )
            for i in range(3)
        ])
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        assert len(prs.slides) == 3

    def test_creates_output_dir(self, service, tmp_path):
        nested_dir = tmp_path / "a" / "b" / "export"
        spec = _make_design_spec()
        response = service.export_from_design_spec(spec, output_dir=nested_dir)

        assert nested_dir.exists()
        assert Path(response.pptx_path).exists()

    def test_auto_creates_output_dir(self, service):
        spec = _make_design_spec()
        response = service.export_from_design_spec(spec)

        path = Path(response.pptx_path)
        assert path.exists()
        assert path.name == "presentation.pptx"


class TestBackgroundImage:
    """배경 이미지가 슬라이드 배경 속성(p:bg/a:blipFill)으로 설정되는지 검증."""

    @staticmethod
    def _make_title_spec() -> DesignSpec:
        return DesignSpec(slides=[
            PptxSlideSpec(
                background_color="#1a1a2e",
                slide_type="title",
                textboxes=[
                    PptxTextBox(
                        left_px=100, top_px=200, width_px=1080, height_px=80,
                        paragraphs=[PptxParagraph(runs=[PptxTextRun(
                            text="Title", font_size_pt=40, bold=True, color="#ffffff",
                        )])],
                    ),
                ],
                shapes=[
                    PptxShape(
                        left_px=100, top_px=400, width_px=200, height_px=4,
                        fill_color="#4a90d9", shape_type="rectangle",
                    ),
                ],
            ),
        ])

    def test_bg_image_set_as_background_property(self, service, tmp_path):
        """배경 이미지는 shape이 아닌 슬라이드 배경 속성(a:blipFill)으로 설정되어야 한다."""
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
        fake_png = buf.getvalue()

        with patch(
            "ppt_generator.tools.pptx.service.bg_image_utils.get_bg_image_bytes",
            return_value=fake_png,
        ):
            spec = self._make_title_spec()
            response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]

        # 배경에 blipFill이 설정되어 있어야 함
        cSld = slide._element.find(qn("p:cSld"))
        bgEl = cSld.find(qn("p:bg"))
        assert bgEl is not None, "p:bg 요소가 존재해야 함"
        bgPr = bgEl.find(qn("p:bgPr"))
        assert bgPr is not None, "p:bgPr 요소가 존재해야 함"
        blipFill = bgPr.find(qn("a:blipFill"))
        assert blipFill is not None, "a:blipFill이 배경에 설정되어야 함"

        # blip의 r:embed가 존재해야 함
        blip = blipFill.find(qn("a:blip"))
        assert blip is not None, "a:blip 요소가 존재해야 함"
        assert blip.get(qn("r:embed")), "r:embed 속성이 있어야 함"

        # shapes에 전체 크기 배경 이미지가 없어야 함 (shape으로 추가되면 안 됨)
        pic_tag = qn("p:pic")
        sp_tree = slide.shapes._spTree
        bg_pics = [
            c for c in sp_tree if c.tag == pic_tag
            and any(
                s.left == 0 and s.top == 0 and s.width > 12_000_000
                for s in slide.shapes if id(s._element) == id(c)
            )
        ]
        assert len(bg_pics) == 0, "배경 이미지가 shape으로 존재하면 안 됨"
