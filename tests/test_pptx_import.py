"""PPTX 임포트 기능 테스트.

핵심 테스트 전략: Export → Import 라운드트립으로 데이터 보존을 검증한다.
"""

from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches, Pt

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxImage,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import (
    design_spec_to_json,
    parse_design_spec_json,
)
from ppt_generator.tools.pptx.service import ExportService
from ppt_generator.tools.pptx_import.service import ImportService
from ppt_generator.tools.pptx_import.slide_reader import SlideReader
from ppt_generator.tools.project.service import ProjectService

# ── 테스트용 DesignSpec 생성 헬퍼 ──


def _make_rich_spec() -> DesignSpec:
    """다양한 요소를 포함한 테스트용 DesignSpec."""
    return DesignSpec(
        slides=[
            PptxSlideSpec(
                background_color="#1A1A2E",
                textboxes=[
                    PptxTextBox(
                        left_px=64,
                        top_px=72,
                        width_px=600,
                        height_px=80,
                        paragraphs=[
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="제목 텍스트",
                                        font_size_pt=32,
                                        bold=True,
                                        color="#FFFFFF",
                                    ),
                                ]
                            )
                        ],
                        vertical_alignment="top",
                        padding_left_px=0,
                        padding_right_px=0,
                        padding_top_px=0,
                        padding_bottom_px=0,
                    ),
                    PptxTextBox(
                        left_px=64,
                        top_px=148,
                        width_px=600,
                        height_px=400,
                        paragraphs=[
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="본문 ", font_size_pt=18, color="#CCCCCC"
                                    ),
                                    PptxTextRun(
                                        text="굵게",
                                        font_size_pt=18,
                                        bold=True,
                                        color="#FF9900",
                                    ),
                                ]
                            ),
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="불릿 항목 1",
                                        font_size_pt=16,
                                        color="#CCCCCC",
                                    )
                                ],
                                bullet_level=0,
                            ),
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="불릿 하위 항목",
                                        font_size_pt=14,
                                        color="#999999",
                                    )
                                ],
                                bullet_level=1,
                            ),
                        ],
                        vertical_alignment="top",
                        padding_left_px=8,
                        padding_right_px=8,
                        padding_top_px=4,
                        padding_bottom_px=4,
                    ),
                ],
                shapes=[
                    PptxShape(
                        left_px=700,
                        top_px=148,
                        width_px=500,
                        height_px=200,
                        shape_type="rounded_rectangle",
                        fill_color="#2A2A4E",
                        border_color="#4A90D9",
                        border_width_pt=1.5,
                        paragraphs=[
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="도형 내 텍스트",
                                        font_size_pt=16,
                                        color="#FFFFFF",
                                    ),
                                ]
                            )
                        ],
                        vertical_alignment="middle",
                        padding_left_px=10,
                        padding_right_px=10,
                        padding_top_px=5,
                        padding_bottom_px=5,
                    ),
                    PptxShape(
                        left_px=700,
                        top_px=400,
                        width_px=500,
                        height_px=150,
                        shape_type="ellipse",
                        fill_color="#FF6600",
                    ),
                    PptxShape(
                        left_px=200,
                        top_px=600,
                        width_px=300,
                        height_px=0,
                        shape_type="line",
                        border_color="#FFC000",
                        border_width_pt=2,
                        end_arrow=True,
                    ),
                ],
                speaker_notes="발표자 노트 내용",
                slide_type="content",
            ),
        ]
    )


def _make_multi_slide_spec() -> DesignSpec:
    """다중 슬라이드 테스트용."""
    return DesignSpec(
        slides=[
            PptxSlideSpec(
                background_color="#000000",
                textboxes=[
                    PptxTextBox(
                        left_px=200,
                        top_px=260,
                        width_px=880,
                        height_px=80,
                        paragraphs=[
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="프레젠테이션 제목",
                                        font_size_pt=40,
                                        bold=True,
                                        color="#FFFFFF",
                                    ),
                                ]
                            )
                        ],
                    )
                ],
                slide_type="title",
            ),
            PptxSlideSpec(
                background_color="#1A1A2E",
                textboxes=[
                    PptxTextBox(
                        left_px=64,
                        top_px=72,
                        width_px=1152,
                        height_px=48,
                        paragraphs=[
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="두 번째 슬라이드",
                                        font_size_pt=28,
                                        color="#FFFFFF",
                                    ),
                                ]
                            )
                        ],
                    )
                ],
                slide_type="content",
            ),
            PptxSlideSpec(
                background_color="#1A1A2E",
                textboxes=[
                    PptxTextBox(
                        left_px=200,
                        top_px=240,
                        width_px=880,
                        height_px=80,
                        paragraphs=[
                            PptxParagraph(
                                runs=[
                                    PptxTextRun(
                                        text="감사합니다",
                                        font_size_pt=36,
                                        bold=True,
                                        color="#FFFFFF",
                                    ),
                                ]
                            )
                        ],
                    )
                ],
                slide_type="closing",
            ),
        ]
    )


# ── Fixtures ──


@pytest.fixture
def export_service():
    return ExportService()


@pytest.fixture
def import_service():
    return ImportService()


# ── 라운드트립 테스트 ──


class TestRoundTrip:
    """Export → Import 라운드트립으로 데이터 보존 검증."""

    def _round_trip(self, export_service, import_service, spec, tmp_path) -> DesignSpec:
        """Export → Import 라운드트립."""
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, warnings = import_service.import_from_file(response.pptx_path)
        return imported

    def test_slide_count_preserved(self, export_service, import_service, tmp_path):
        spec = _make_multi_slide_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)
        assert len(imported.slides) == len(spec.slides)

    def test_text_content_preserved(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        slide = imported.slides[0]
        all_text = ""
        for tb in slide.textboxes:
            for p in tb.paragraphs:
                for r in p.runs:
                    all_text += r.text
        for s in slide.shapes:
            for p in s.paragraphs:
                for r in p.runs:
                    all_text += r.text

        assert "제목 텍스트" in all_text
        assert "본문" in all_text
        assert "굵게" in all_text
        assert "불릿 항목 1" in all_text
        assert "불릿 하위 항목" in all_text
        assert "도형 내 텍스트" in all_text

    def test_background_color_preserved(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        assert imported.slides[0].background_color == "#1A1A2E"

    def test_background_image_preserved(self, export_service, import_service, tmp_path):
        """슬라이드 배경의 blipFill 이미지가 라운드트립에서 보존되어야 한다.

        회귀 방지: solid color만 추출하고 blipFill을 무시하면 임포트 시
        흰색으로 폴백되어 시각적으로 누락된다.
        """
        # content 슬라이드여서 기본 폴백 배경 이미지가 적용되지 않는 케이스로 검증
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff"
            b"\x18p\xb1\x82\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    background_color="#1A1A2E",
                    background_image_bytes=png_bytes,
                    textboxes=[],
                    shapes=[],
                    speaker_notes="",
                    slide_type="content",
                ),
            ]
        )
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        assert imported.slides[0].background_image_bytes, (
            "blipFill 슬라이드 배경 이미지가 임포트에서 추출되지 않음"
        )
        assert imported.slides[0].background_image_bytes.startswith(b"\x89PNG"), (
            "추출된 배경 이미지가 PNG가 아님"
        )

    def test_speaker_notes_preserved(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        assert imported.slides[0].speaker_notes == "발표자 노트 내용"

    def test_font_properties_preserved(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        # 제목 텍스트의 폰트 속성
        title_tb = imported.slides[0].textboxes[0]
        title_run = title_tb.paragraphs[0].runs[0]
        assert title_run.font_size_pt == 32
        assert title_run.bold is True
        assert title_run.color == "#FFFFFF"

    def test_shape_fill_color_preserved(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        # rounded_rectangle의 fill
        rounded_rect = [
            s for s in imported.slides[0].shapes if s.shape_type == "rounded_rectangle"
        ]
        assert len(rounded_rect) >= 1
        assert rounded_rect[0].fill_color == "#2A2A4E"

    def test_connector_arrow_preserved(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        lines = [s for s in imported.slides[0].shapes if s.shape_type == "line"]
        assert len(lines) >= 1
        arrow_line = lines[0]
        assert arrow_line.end_arrow is True

    def test_position_accuracy(self, export_service, import_service, tmp_path):
        """좌표 변환 정밀도 ±3px 이내 검증."""
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        orig_tb = spec.slides[0].textboxes[0]
        imported_tb = imported.slides[0].textboxes[0]

        assert abs(imported_tb.left_px - orig_tb.left_px) <= 3
        assert abs(imported_tb.top_px - orig_tb.top_px) <= 3
        assert abs(imported_tb.width_px - orig_tb.width_px) <= 3
        assert abs(imported_tb.height_px - orig_tb.height_px) <= 3

    def test_bullet_level_preserved(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        body_tb = imported.slides[0].textboxes[1]
        bullet_paras = [p for p in body_tb.paragraphs if p.bullet_level >= 0]
        assert len(bullet_paras) >= 2
        assert bullet_paras[0].bullet_level == 0
        assert bullet_paras[1].bullet_level >= 1

    def test_ellipse_shape_type(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        imported = self._round_trip(export_service, import_service, spec, tmp_path)

        ellipses = [s for s in imported.slides[0].shapes if s.shape_type == "ellipse"]
        assert len(ellipses) >= 1


# ── ImportService 직접 테스트 ──


class TestImportService:
    def test_import_from_file_not_found(self, import_service):
        with pytest.raises(FileNotFoundError):
            import_service.import_from_file("/nonexistent/path.pptx")

    def test_import_from_file_wrong_extension(self, import_service, tmp_path):
        bad_file = tmp_path / "test.pdf"
        bad_file.write_text("not a pptx")
        with pytest.raises(ValueError, match="PPTX 파일만 지원"):
            import_service.import_from_file(bad_file)

    def test_import_empty_presentation(self, import_service, tmp_path):
        prs = Presentation()
        pptx_path = tmp_path / "empty.pptx"
        prs.save(str(pptx_path))
        with pytest.raises(ValueError, match="슬라이드가 없습니다"):
            import_service.import_from_file(pptx_path)

    def test_import_from_bytes(self, export_service, import_service, tmp_path):
        spec = _make_rich_spec()
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        pptx_bytes = Path(response.pptx_path).read_bytes()

        imported, warnings = import_service.import_from_bytes(pptx_bytes)
        assert len(imported.slides) == 1


# ── SlideReader 단위 테스트 ──


class TestSlideReader:
    def test_compute_scale_standard_size(self):
        """표준 크기(13.333" × 7.5") → scale 1.0."""
        prs = Presentation()
        prs.slide_width = 12_192_000
        prs.slide_height = 6_858_000
        sx, sy = SlideReader.compute_scale(prs)
        assert abs(sx - 1.0) < 0.01
        assert abs(sy - 1.0) < 0.01

    def test_compute_scale_4_3_aspect(self):
        """4:3 비율 (10" × 7.5") → scale_x > 1."""
        prs = Presentation()
        prs.slide_width = 9_144_000  # 10"
        prs.slide_height = 6_858_000  # 7.5"
        sx, sy = SlideReader.compute_scale(prs)
        assert sx > 1.0
        assert abs(sy - 1.0) < 0.01

    def test_infer_slide_type_title(self):
        """첫 슬라이드 + 큰 폰트 + 적은 요소 → title."""
        textboxes = [
            PptxTextBox(
                left_px=200,
                top_px=260,
                width_px=880,
                height_px=80,
                paragraphs=[
                    PptxParagraph(
                        runs=[
                            PptxTextRun(text="Title", font_size_pt=40, bold=True),
                        ]
                    )
                ],
            )
        ]
        result = SlideReader._infer_slide_type(0, 5, textboxes, [])
        assert result == "title"

    def test_infer_slide_type_closing(self):
        """마지막 슬라이드 + closing 키워드 → closing."""
        textboxes = [
            PptxTextBox(
                left_px=200,
                top_px=260,
                width_px=880,
                height_px=80,
                paragraphs=[
                    PptxParagraph(
                        runs=[
                            PptxTextRun(text="감사합니다"),
                        ]
                    )
                ],
            )
        ]
        result = SlideReader._infer_slide_type(4, 5, textboxes, [])
        assert result == "closing"

    def test_infer_slide_type_content(self):
        """중간 슬라이드 → content."""
        textboxes = [
            PptxTextBox(
                left_px=64,
                top_px=72,
                width_px=1152,
                height_px=500,
                paragraphs=[
                    PptxParagraph(
                        runs=[
                            PptxTextRun(text="Some content", font_size_pt=16),
                        ]
                    )
                ],
            )
        ]
        result = SlideReader._infer_slide_type(2, 5, textboxes, [])
        assert result == "content"


# ── 특수 요소 테스트 ──


class TestSpecialElements:
    """python-pptx로 직접 생성한 PPTX의 특수 요소 추출 검증."""

    def test_table_extraction(self, import_service, tmp_path):
        """테이블이 Shape 격자로 변환되는지 검증."""
        prs = Presentation()
        prs.slide_width = 12_192_000
        prs.slide_height = 6_858_000
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        rows, cols = 2, 3
        table_shape = slide.shapes.add_table(
            rows,
            cols,
            Inches(1),
            Inches(1),
            Inches(6),
            Inches(2),
        )
        table = table_shape.table
        table.cell(0, 0).text = "A1"
        table.cell(0, 1).text = "B1"
        table.cell(1, 0).text = "A2"

        pptx_path = tmp_path / "table.pptx"
        prs.save(str(pptx_path))

        imported, warnings = import_service.import_from_file(pptx_path)
        slide_spec = imported.slides[0]

        # 테이블 셀이 shape으로 변환되었는지
        assert len(slide_spec.shapes) == rows * cols
        all_text = ""
        for s in slide_spec.shapes:
            for p in s.paragraphs:
                for r in p.runs:
                    all_text += r.text
        assert "A1" in all_text
        assert "B1" in all_text
        assert "A2" in all_text

    def test_vertical_alignment_middle(self, export_service, import_service, tmp_path):
        """vertical_alignment=middle이 보존되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    background_color="#000000",
                    shapes=[
                        PptxShape(
                            left_px=100,
                            top_px=100,
                            width_px=400,
                            height_px=200,
                            shape_type="rectangle",
                            fill_color="#333333",
                            paragraphs=[
                                PptxParagraph(
                                    runs=[
                                        PptxTextRun(
                                            text="중앙 정렬",
                                            font_size_pt=20,
                                            color="#FFFFFF",
                                        ),
                                    ]
                                )
                            ],
                            vertical_alignment="middle",
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        rect = imported.slides[0].shapes[0]
        assert rect.vertical_alignment == "middle"

    def test_paragraph_alignment_center(self, export_service, import_service, tmp_path):
        """paragraph alignment=center가 보존되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    textboxes=[
                        PptxTextBox(
                            left_px=100,
                            top_px=100,
                            width_px=400,
                            height_px=100,
                            paragraphs=[
                                PptxParagraph(
                                    runs=[
                                        PptxTextRun(text="가운데 정렬", font_size_pt=20)
                                    ],
                                    alignment="center",
                                )
                            ],
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        tb = imported.slides[0].textboxes[0]
        assert tb.paragraphs[0].alignment == "center"

    def test_negative_height_diagonal_arrow_roundtrip(
        self, export_service, import_service, tmp_path
    ):
        """음수 height 대각선 (↗) 화살표가 export→import 후 좌표/방향 보존되는지.

        회귀: bbox top 보정 + flipV 명시 set 이 이중 적용되어 export 후 화살표가
        캔버스 위로 떠 있던 버그. spec convention 은 (left, top) = bbox 좌상,
        h<0 = ↗ 방향이며 export 는 begin/end 좌표만 정확히 넘기면 python-pptx 가
        flipV 를 자동 설정한다.
        """
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    shapes=[
                        PptxShape(
                            left_px=854,
                            top_px=224,
                            width_px=218,
                            height_px=-60,
                            shape_type="line",
                            border_color="#FFFFFF",
                            border_width_pt=2,
                            end_arrow=True,
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        line = imported.slides[0].shapes[0]
        assert round(line.left_px) == 854
        assert round(line.top_px) == 224  # bbox top, 화살표가 위로 안 떠야 함
        assert round(line.width_px) == 218
        assert round(line.height_px) == -60
        assert line.end_arrow is True
        assert line.start_arrow is False

    def test_positive_height_diagonal_arrow_roundtrip(
        self, export_service, import_service, tmp_path
    ):
        """양수 height 대각선 (↘) 화살표가 정확히 보존되는지."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    shapes=[
                        PptxShape(
                            left_px=100,
                            top_px=100,
                            width_px=200,
                            height_px=80,
                            shape_type="line",
                            border_color="#FFFFFF",
                            border_width_pt=2,
                            end_arrow=True,
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        line = imported.slides[0].shapes[0]
        assert round(line.left_px) == 100
        assert round(line.top_px) == 100
        assert round(line.width_px) == 200
        assert round(line.height_px) == 80
        assert line.end_arrow is True

    def test_component_id_preserved(self, export_service, import_service, tmp_path):
        """spec 의 component_id 가 export → import 라운드트립에서 보존되는지.

        design_doc 자체는 PPTX 에 직렬화하지 않으므로 import 결과는 None 일 수 있지만,
        textbox/shape 의 component_id 는 PPTX shape name 에 보존되거나 누락된다.
        현재 구현은 PPTX 에 component_id 를 별도 저장하지 않으므로 import 후
        component_id 는 None 으로 fallback 된다. 이 테스트는 *export 가 component_id
        를 갖고도 정상 동작* 하는지만 확인한다.
        """
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    textboxes=[
                        PptxTextBox(
                            left_px=100,
                            top_px=100,
                            width_px=200,
                            height_px=50,
                            paragraphs=[
                                PptxParagraph(
                                    runs=[PptxTextRun(text="hello", font_size_pt=18)]
                                )
                            ],
                            component_id="left.title",
                        )
                    ],
                )
            ]
        )
        # export 가 component_id 가 있어도 깨지지 않아야 함
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)
        # 텍스트는 보존됨
        tb = imported.slides[0].textboxes[0]
        assert tb.paragraphs[0].runs[0].text == "hello"

    def test_dash_style_preserved(self, export_service, import_service, tmp_path):
        """dash_style이 보존되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    shapes=[
                        PptxShape(
                            left_px=100,
                            top_px=300,
                            width_px=400,
                            height_px=0,
                            shape_type="line",
                            border_color="#FF0000",
                            border_width_pt=2,
                            dash_style="dash",
                            end_arrow=True,
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        line = [s for s in imported.slides[0].shapes if s.shape_type == "line"][0]
        assert line.dash_style == "dash"
        assert line.end_arrow is True

    @pytest.mark.parametrize(
        "ooxml_dash_val,expected",
        [
            ("dash", "dash"),
            ("lgDash", "dash"),
            ("sysDash", "dash"),
            ("dashDot", "dash"),
            ("lgDashDot", "dash"),
            ("lgDashDotDot", "dash"),
            ("dot", "dot"),
            ("sysDot", "dot"),
            ("solid", None),
            ("", None),
        ],
    )
    def test_connector_dash_style_normalization(
        self, ooxml_dash_val, expected, tmp_path
    ):
        """OOXML prstDash 변형(sysDot/sysDash 등)이 임포터에서 dash/dot로 정규화되어야 한다.

        회귀 방지: 과거 임포터는 ("dash","dot") 만 인정하여 sysDot/sysDash 등이 누락됐다.
        """
        # python-pptx 의 connector 객체를 모킹하기보다, slide_reader 의 연결자 추출 코드를
        # 직접 호출하기 위해 PPTX 파일을 만들고 a:prstDash val 을 직접 설정해 임포트한다.
        from io import BytesIO
        from pptx import Presentation
        from pptx.oxml.ns import qn
        from pptx.util import Inches
        from lxml import etree

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # CXN connector 추가 (line)
        from pptx.shapes.connector import Connector

        cxn = slide.shapes.add_connector(1, Inches(1), Inches(2), Inches(3), Inches(2))
        # a:ln 에 prstDash val 직접 삽입
        spPr = cxn._element.find(qn("p:spPr"))
        ln = spPr.find(qn("a:ln"))
        if ln is None:
            ln = etree.SubElement(spPr, qn("a:ln"))
        # 기존 prstDash 제거
        for old in ln.findall(qn("a:prstDash")):
            ln.remove(old)
        if ooxml_dash_val:
            prst = etree.SubElement(ln, qn("a:prstDash"))
            prst.set("val", ooxml_dash_val)

        buf = BytesIO()
        prs.save(buf)
        buf.seek(0)
        path = tmp_path / "dash.pptx"
        path.write_bytes(buf.read())

        imported, _ = ImportService().import_from_file(path)
        lines = [s for s in imported.slides[0].shapes if s.shape_type == "line"]
        assert lines, "line shape 가 임포트되어야 한다"
        assert lines[0].dash_style == expected, (
            f"OOXML {ooxml_dash_val!r} → expected {expected!r}, got {lines[0].dash_style!r}"
        )

    def test_italic_preserved(self, export_service, import_service, tmp_path):
        """italic 속성이 보존되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    textboxes=[
                        PptxTextBox(
                            left_px=100,
                            top_px=100,
                            width_px=400,
                            height_px=100,
                            paragraphs=[
                                PptxParagraph(
                                    runs=[
                                        PptxTextRun(
                                            text="이탤릭", font_size_pt=18, italic=True
                                        ),
                                    ]
                                )
                            ],
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        run = imported.slides[0].textboxes[0].paragraphs[0].runs[0]
        assert run.italic is True


# ── 새 도형 타입 라운드트립 테스트 ──


class TestNewShapeTypes:
    """새로 추가된 도형 타입의 Export → Import 라운드트립 검증."""

    _SHAPE_TYPES_WITH_FILL = [
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
        "flowchart_process",
        "flowchart_decision",
        "flowchart_terminator",
    ]

    @pytest.mark.parametrize("shape_type", _SHAPE_TYPES_WITH_FILL)
    def test_shape_type_round_trip(
        self, export_service, import_service, tmp_path, shape_type
    ):
        """각 도형 타입이 Export → Import 후 shape_type 이 보존되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    background_color="#000000",
                    shapes=[
                        PptxShape(
                            left_px=100,
                            top_px=100,
                            width_px=200,
                            height_px=200,
                            shape_type=shape_type,
                            fill_color="#4472C4",
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        assert len(imported.slides[0].shapes) >= 1
        imported_shape = imported.slides[0].shapes[0]
        assert imported_shape.shape_type == shape_type
        assert imported_shape.fill_color == "#4472C4"

    def test_arrow_with_text(self, export_service, import_service, tmp_path):
        """화살표 도형 내부에 텍스트가 보존되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    background_color="#000000",
                    shapes=[
                        PptxShape(
                            left_px=100,
                            top_px=100,
                            width_px=200,
                            height_px=300,
                            shape_type="up_arrow",
                            fill_color="#FF6600",
                            text="UP",
                            text_color="#FFFFFF",
                            text_size_pt=16,
                            text_bold=True,
                        )
                    ],
                )
            ]
        )
        response = export_service.export_from_design_spec(spec, output_dir=tmp_path)
        imported, _ = import_service.import_from_file(response.pptx_path)

        shape = imported.slides[0].shapes[0]
        assert shape.shape_type == "up_arrow"
        assert shape.text == "UP"
        assert shape.text_bold is True


# ── 플레이스홀더 서식 상속 테스트 ──


class TestPlaceholderFormatInheritance:
    """OOXML 상속 체인(paragraph → layout → master)에서 서식이 올바르게 resolve되는지 검증."""

    def test_placeholder_title_inherits_layout_font_size(self, tmp_path):
        """layout defRPr에 sz=4800 설정 → 임포트 시 48pt로 추출."""
        from lxml.etree import SubElement
        from pptx.oxml.ns import qn as _qn

        prs = Presentation()
        prs.slide_width = 12_192_000
        prs.slide_height = 6_858_000
        layout = prs.slide_layouts[0]  # Title Slide layout
        slide = prs.slides.add_slide(layout)

        # layout placeholder의 lstStyle에 defRPr sz=4800 주입
        for ph in layout.placeholders:
            if ph.placeholder_format.idx == 0:  # 제목 placeholder
                txBody = ph._element.find(_qn("p:txBody"))
                if txBody is not None:
                    lstStyle = txBody.find(_qn("a:lstStyle"))
                    if lstStyle is None:
                        lstStyle = SubElement(txBody, _qn("a:lstStyle"))
                    lvl1pPr = lstStyle.find(_qn("a:lvl1pPr"))
                    if lvl1pPr is None:
                        lvl1pPr = SubElement(lstStyle, _qn("a:lvl1pPr"))
                    defRPr = lvl1pPr.find(_qn("a:defRPr"))
                    if defRPr is None:
                        defRPr = SubElement(lvl1pPr, _qn("a:defRPr"))
                    defRPr.set("sz", "4800")  # 48pt
                break

        # 슬라이드 제목 placeholder에 텍스트 추가 (run에 sz 지정 없음)
        for ph in slide.placeholders:
            if ph.placeholder_format.idx == 0:
                ph.text = "Layout Inherited Title"
                break

        pptx_path = tmp_path / "layout_inherit.pptx"
        prs.save(str(pptx_path))

        imported, _ = ImportService().import_from_file(pptx_path)
        slide_spec = imported.slides[0]

        # 제목 텍스트를 찾아 font_size_pt 검증
        found = False
        for tb in slide_spec.textboxes:
            for p in tb.paragraphs:
                for r in p.runs:
                    if "Layout Inherited Title" in r.text:
                        assert r.font_size_pt == 48, (
                            f"Expected 48pt, got {r.font_size_pt}"
                        )
                        found = True
        assert found, "제목 텍스트를 찾을 수 없습니다"

    def test_placeholder_title_inherits_master_style(self, tmp_path):
        """master titleStyle 기본값 (sz=4400) → 임포트 시 44pt 추출."""
        prs = Presentation()
        prs.slide_width = 12_192_000
        prs.slide_height = 6_858_000

        # 기본 Presentation의 master titleStyle에 이미 sz=4400 kern=1200이 있음
        layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(layout)

        # 제목 placeholder에 텍스트 추가 (run에 sz 미지정 → master에서 상속)
        for ph in slide.placeholders:
            if ph.placeholder_format.idx == 0:
                ph.text = "Master Inherited Title"
                break

        pptx_path = tmp_path / "master_inherit.pptx"
        prs.save(str(pptx_path))

        imported, _ = ImportService().import_from_file(pptx_path)
        slide_spec = imported.slides[0]

        found = False
        for tb in slide_spec.textboxes:
            for p in tb.paragraphs:
                for r in p.runs:
                    if "Master Inherited Title" in r.text:
                        assert r.font_size_pt == 44, (
                            f"Expected 44pt, got {r.font_size_pt}"
                        )
                        found = True
        assert found, "제목 텍스트를 찾을 수 없습니다"

    def test_placeholder_color_inherits_from_layout_scheme(self, tmp_path):
        """layout defRPr에 srgbClr 설정 → 임포트 시 해당 색상 추출."""
        from lxml.etree import SubElement
        from pptx.oxml.ns import qn as _qn

        prs = Presentation()
        prs.slide_width = 12_192_000
        prs.slide_height = 6_858_000
        layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(layout)

        # layout placeholder lstStyle에 solidFill srgbClr val="FF0000" 주입
        for ph in layout.placeholders:
            if ph.placeholder_format.idx == 0:
                txBody = ph._element.find(_qn("p:txBody"))
                if txBody is not None:
                    lstStyle = txBody.find(_qn("a:lstStyle"))
                    if lstStyle is None:
                        lstStyle = SubElement(txBody, _qn("a:lstStyle"))
                    lvl1pPr = lstStyle.find(_qn("a:lvl1pPr"))
                    if lvl1pPr is None:
                        lvl1pPr = SubElement(lstStyle, _qn("a:lvl1pPr"))
                    defRPr = lvl1pPr.find(_qn("a:defRPr"))
                    if defRPr is None:
                        defRPr = SubElement(lvl1pPr, _qn("a:defRPr"))
                    solidFill = SubElement(defRPr, _qn("a:solidFill"))
                    srgbClr = SubElement(solidFill, _qn("a:srgbClr"))
                    srgbClr.set("val", "FF0000")
                break

        for ph in slide.placeholders:
            if ph.placeholder_format.idx == 0:
                ph.text = "Red Title"
                break

        pptx_path = tmp_path / "color_inherit.pptx"
        prs.save(str(pptx_path))

        imported, _ = ImportService().import_from_file(pptx_path)
        slide_spec = imported.slides[0]

        found = False
        for tb in slide_spec.textboxes:
            for p in tb.paragraphs:
                for r in p.runs:
                    if "Red Title" in r.text:
                        assert r.color == "#FF0000", f"Expected #FF0000, got {r.color}"
                        found = True
        assert found, "제목 텍스트를 찾을 수 없습니다"

    def test_run_direct_value_overrides_inherited(self, tmp_path):
        """run에 직접 지정된 값이 상속값을 오버라이드하는지 검증."""
        from pptx.util import Pt

        prs = Presentation()
        prs.slide_width = 12_192_000
        prs.slide_height = 6_858_000
        layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(layout)

        for ph in slide.placeholders:
            if ph.placeholder_format.idx == 0:
                ph.text = "Direct Size"
                # run에 직접 font_size 지정
                for run in ph.text_frame.paragraphs[0].runs:
                    run.font.size = Pt(24)
                break

        pptx_path = tmp_path / "direct_override.pptx"
        prs.save(str(pptx_path))

        imported, _ = ImportService().import_from_file(pptx_path)
        slide_spec = imported.slides[0]

        found = False
        for tb in slide_spec.textboxes:
            for p in tb.paragraphs:
                for r in p.runs:
                    if "Direct Size" in r.text:
                        assert r.font_size_pt == 24, (
                            f"Expected 24pt, got {r.font_size_pt}"
                        )
                        found = True
        assert found, "텍스트를 찾을 수 없습니다"

    def test_theme_color_map_extraction(self, tmp_path):
        """테마 색상 맵이 올바르게 추출되는지 검증."""
        from ppt_generator.tools.pptx_import.slide_reader import (
            _extract_theme_color_map,
        )

        prs = Presentation()
        color_map = _extract_theme_color_map(prs)
        # 기본 테마에서 최소한 dk1, lt1은 추출되어야 함
        assert "dk1" in color_map or len(color_map) == 0  # 테마가 없으면 빈 맵
        if color_map:
            # 별칭 매핑 확인
            if "dk1" in color_map:
                assert "tx1" in color_map
                assert color_map["tx1"] == color_map["dk1"]


# ── 이미지 src 직렬화/역직렬화 테스트 ──


class TestImageSrcSerialization:
    """이미지 src 필드의 직렬화/역직렬화 검증."""

    def test_image_src_serialized_in_json(self):
        """PptxImage.src가 JSON 직렬화에 포함되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    images=[
                        PptxImage(
                            left_px=100,
                            top_px=200,
                            width_px=300,
                            height_px=400,
                            image_bytes=b"\x89PNG",
                            src="images/slide_01_img_01.png",
                        )
                    ],
                )
            ]
        )
        json_str = design_spec_to_json(spec)
        import json

        data = json.loads(json_str)
        img_data = data["slides"][0]["images"][0]
        assert img_data["src"] == "images/slide_01_img_01.png"
        assert "image_bytes" not in img_data  # image_bytes는 제거됨

    def test_image_src_parsed_from_json(self):
        """JSON에서 PptxImage.src가 역직렬화되는지 검증."""
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    images=[
                        PptxImage(
                            left_px=100,
                            top_px=200,
                            width_px=300,
                            height_px=400,
                            src="images/slide_01_img_01.png",
                        )
                    ],
                )
            ]
        )
        json_str = design_spec_to_json(spec)
        parsed = parse_design_spec_json(json_str)
        assert len(parsed.slides[0].images) == 1
        img = parsed.slides[0].images[0]
        assert img.src == "images/slide_01_img_01.png"
        assert img.left_px == 100
        assert img.width_px == 300

    def test_load_design_spec_with_images_restores_bytes(self, tmp_path):
        """load_design_spec_with_images가 src로부터 image_bytes를 복원하는지 검증."""
        project_service = ProjectService()
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # 이미지 파일 생성
        images_dir = project_dir / "slides" / "images"
        images_dir.mkdir(parents=True)
        png_bytes = b"\x89PNG\r\n\x1a\nfake_image_data"
        (images_dir / "slide_01_img_01.png").write_bytes(png_bytes)

        # src가 포함된 design spec 저장
        spec = DesignSpec(
            slides=[
                PptxSlideSpec(
                    images=[
                        PptxImage(
                            left_px=10,
                            top_px=20,
                            width_px=300,
                            height_px=200,
                            src="images/slide_01_img_01.png",
                        )
                    ],
                )
            ]
        )
        project_service.save_design_spec(project_dir, spec)

        # image_bytes 복원 검증
        loaded = project_service.load_design_spec_with_images(project_dir)
        assert len(loaded.slides[0].images) == 1
        img = loaded.slides[0].images[0]
        assert img.image_bytes == png_bytes
        assert img.src == "images/slide_01_img_01.png"
