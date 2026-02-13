from pathlib import Path

import pytest
from pptx import Presentation

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
