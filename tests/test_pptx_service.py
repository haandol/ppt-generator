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


class TestConnectorArrow:
    """line shape가 connector로 렌더링되고 화살표 머리가 올바르게 설정되는지 검증."""

    @staticmethod
    def _make_arrow_spec(
        end_arrow: bool = False,
        start_arrow: bool = False,
        dash_style: str | None = None,
    ) -> DesignSpec:
        return DesignSpec(slides=[
            PptxSlideSpec(
                background_color="#232F3E",
                shapes=[
                    PptxShape(
                        left_px=100, top_px=300, width_px=200, height_px=0,
                        shape_type="line",
                        border_color="#FFC000",
                        border_width_pt=2,
                        end_arrow=end_arrow,
                        start_arrow=start_arrow,
                        dash_style=dash_style,
                    ),
                ],
            ),
        ])

    def test_line_rendered_as_connector(self, service, tmp_path):
        """line shape는 p:cxnSp(connector)로 렌더링되어야 한다."""
        spec = self._make_arrow_spec()
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        sp_tree = slide.shapes._spTree
        cxn_tag = qn("p:cxnSp")
        connectors = [c for c in sp_tree if c.tag == cxn_tag]
        assert len(connectors) == 1, "line shape가 p:cxnSp(connector)로 렌더링되어야 함"

    def test_end_arrow_triangle(self, service, tmp_path):
        """end_arrow=True → a:tailEnd type=triangle이 있어야 한다."""
        spec = self._make_arrow_spec(end_arrow=True)
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connector = next(c for c in slide.shapes._spTree if c.tag == cxn_tag)

        ln = connector.find(f".//{qn('a:ln')}")
        assert ln is not None
        tail = ln.find(qn("a:tailEnd"))
        assert tail is not None, "end_arrow=True이면 a:tailEnd가 있어야 함"
        assert tail.get("type") == "triangle"

    def test_start_arrow_triangle(self, service, tmp_path):
        """start_arrow=True → a:headEnd type=triangle이 있어야 한다."""
        spec = self._make_arrow_spec(start_arrow=True)
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connector = next(c for c in slide.shapes._spTree if c.tag == cxn_tag)

        ln = connector.find(f".//{qn('a:ln')}")
        assert ln is not None
        head = ln.find(qn("a:headEnd"))
        assert head is not None, "start_arrow=True이면 a:headEnd가 있어야 함"
        assert head.get("type") == "triangle"

    def test_bidirectional_arrows(self, service, tmp_path):
        """양방향 화살표: headEnd와 tailEnd 모두 있어야 한다."""
        spec = self._make_arrow_spec(end_arrow=True, start_arrow=True)
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connector = next(c for c in slide.shapes._spTree if c.tag == cxn_tag)

        ln = connector.find(f".//{qn('a:ln')}")
        assert ln.find(qn("a:tailEnd")) is not None
        assert ln.find(qn("a:headEnd")) is not None

    def test_no_arrow_no_ends(self, service, tmp_path):
        """화살표 미지정 → headEnd/tailEnd가 없어야 한다."""
        spec = self._make_arrow_spec(end_arrow=False, start_arrow=False)
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connector = next(c for c in slide.shapes._spTree if c.tag == cxn_tag)

        ln = connector.find(f".//{qn('a:ln')}")
        assert ln.find(qn("a:tailEnd")) is None
        assert ln.find(qn("a:headEnd")) is None

    def test_dash_style(self, service, tmp_path):
        """dash_style="dash" → a:prstDash val=dash가 있어야 한다."""
        spec = self._make_arrow_spec(dash_style="dash")
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connector = next(c for c in slide.shapes._spTree if c.tag == cxn_tag)

        ln = connector.find(f".//{qn('a:ln')}")
        prstDash = ln.find(qn("a:prstDash"))
        assert prstDash is not None, "dash_style=dash이면 a:prstDash가 있어야 함"
        assert prstDash.get("val") == "dash"

    def test_vertical_connector(self, service, tmp_path):
        """수직 커넥터(width=0, height>0)도 정상 렌더링되어야 한다."""
        spec = DesignSpec(slides=[
            PptxSlideSpec(
                background_color="#232F3E",
                shapes=[
                    PptxShape(
                        left_px=640, top_px=200, width_px=0, height_px=100,
                        shape_type="line",
                        border_color="#FF9900",
                        border_width_pt=2,
                        end_arrow=True,
                    ),
                ],
            ),
        ])
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connectors = [c for c in slide.shapes._spTree if c.tag == cxn_tag]
        assert len(connectors) == 1

    def test_negative_height_connector_flipV(self, service, tmp_path):
        """음수 height → connector에 flipV="1"이 설정되어야 한다."""
        spec = DesignSpec(slides=[
            PptxSlideSpec(
                background_color="#232F3E",
                shapes=[
                    PptxShape(
                        left_px=100, top_px=100, width_px=200, height_px=-150,
                        shape_type="line",
                        border_color="#FFC000",
                        border_width_pt=2,
                        end_arrow=True,
                    ),
                ],
            ),
        ])
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connector = next(c for c in slide.shapes._spTree if c.tag == cxn_tag)
        xfrm = connector.find(f".//{qn('a:xfrm')}")
        assert xfrm is not None
        assert xfrm.get("flipV") == "1", "음수 height이면 flipV=1이어야 한다"

    def test_positive_height_no_flipV(self, service, tmp_path):
        """양수 height → connector에 flipV가 없어야 한다."""
        spec = DesignSpec(slides=[
            PptxSlideSpec(
                background_color="#232F3E",
                shapes=[
                    PptxShape(
                        left_px=100, top_px=100, width_px=200, height_px=150,
                        shape_type="line",
                        border_color="#FFC000",
                        border_width_pt=2,
                        end_arrow=True,
                    ),
                ],
            ),
        ])
        response = service.export_from_design_spec(spec, output_dir=tmp_path)

        prs = Presentation(response.pptx_path)
        slide = prs.slides[0]
        cxn_tag = qn("p:cxnSp")
        connector = next(c for c in slide.shapes._spTree if c.tag == cxn_tag)
        xfrm = connector.find(f".//{qn('a:xfrm')}")
        assert xfrm is None or xfrm.get("flipV") is None, "양수 height이면 flipV 없어야 한다"
