"""PptxSlideSpec 파싱 유틸리티.

JSON dict/문자열 → PptxSlideSpec/DesignSpec 변환을 담당한다.
"""

from __future__ import annotations

import json

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxImage,
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)


def parse_slide_spec(data: dict) -> PptxSlideSpec:
    """JSON dict를 PptxSlideSpec dataclass로 변환."""
    textboxes: list[PptxTextBox] = []
    for tb in data.get("textboxes", []):
        paragraphs: list[PptxParagraph] = []
        for p in tb.get("paragraphs", []):
            runs: list[PptxTextRun] = []
            for r in p.get("runs", []):
                runs.append(PptxTextRun(
                    text=r.get("text", ""),
                    font_size_pt=r.get("font_size_pt"),
                    color=r.get("color"),
                    bold=r.get("bold", False),
                    italic=r.get("italic", False),
                    font_family=r.get("font_family"),
                ))
            paragraphs.append(PptxParagraph(
                runs=runs,
                bullet_level=p.get("bullet_level", -1),
                alignment=p.get("alignment"),
            ))
        textboxes.append(PptxTextBox(
            left_px=tb.get("left_px", 0),
            top_px=tb.get("top_px", 0),
            width_px=tb.get("width_px", 100),
            height_px=tb.get("height_px", 50),
            paragraphs=paragraphs,
            line_spacing_pt=tb.get("line_spacing_pt"),
            vertical_alignment=tb.get("vertical_alignment") or "top",
            padding_left_px=tb.get("padding_left_px"),
            padding_right_px=tb.get("padding_right_px"),
            padding_top_px=tb.get("padding_top_px"),
            padding_bottom_px=tb.get("padding_bottom_px"),
        ))

    shapes: list[PptxShape] = []
    for s in data.get("shapes", []):
        shape_paragraphs: list[PptxParagraph] = []
        for p in s.get("paragraphs", []):
            s_runs: list[PptxTextRun] = []
            for r in p.get("runs", []):
                s_runs.append(PptxTextRun(
                    text=r.get("text", ""),
                    font_size_pt=r.get("font_size_pt"),
                    color=r.get("color"),
                    bold=r.get("bold", False),
                    italic=r.get("italic", False),
                    font_family=r.get("font_family"),
                ))
            shape_paragraphs.append(PptxParagraph(
                runs=s_runs,
                bullet_level=p.get("bullet_level", -1),
                alignment=p.get("alignment"),
            ))
        shapes.append(PptxShape(
            left_px=s.get("left_px", 0),
            top_px=s.get("top_px", 0),
            width_px=s.get("width_px", 100),
            height_px=s.get("height_px", 50),
            shape_type=s.get("shape_type", "rectangle"),
            fill_color=s.get("fill_color"),
            border_color=s.get("border_color"),
            border_width_pt=s.get("border_width_pt"),
            corner_radius_px=s.get("corner_radius_px"),
            text=s.get("text"),
            text_color=s.get("text_color"),
            text_size_pt=s.get("text_size_pt"),
            text_bold=s.get("text_bold", False),
            paragraphs=shape_paragraphs,
            line_spacing_pt=s.get("line_spacing_pt"),
            padding_left_px=s.get("padding_left_px"),
            padding_right_px=s.get("padding_right_px"),
            padding_top_px=s.get("padding_top_px"),
            padding_bottom_px=s.get("padding_bottom_px"),
            vertical_alignment=s.get("vertical_alignment") or "top",
            end_arrow=s.get("end_arrow", False),
            start_arrow=s.get("start_arrow", False),
            dash_style=s.get("dash_style"),
            svg_path=s.get("svg_path"),
            autofit_mode=s.get("autofit_mode", "expand_height"),
        ))

    images: list[PptxImage] = [
        PptxImage(
            left_px=img.get("left_px", 0),
            top_px=img.get("top_px", 0),
            width_px=img.get("width_px", 0),
            height_px=img.get("height_px", 0),
            src=img.get("src", ""),
        )
        for img in data.get("images", [])
    ]

    return PptxSlideSpec(
        background_color=data.get("background_color"),
        textboxes=textboxes,
        shapes=shapes,
        images=images,
        speaker_notes=data.get("speaker_notes", ""),
        slide_type=data.get("slide_type", "content"),
    )


def parse_slide_spec_json(json_str: str) -> PptxSlideSpec:
    """JSON 문자열을 단일 PptxSlideSpec으로 역직렬화."""
    data = json.loads(json_str)
    return parse_slide_spec(data)


def parse_design_spec_json(json_str: str) -> DesignSpec:
    """JSON 문자열을 DesignSpec으로 역직렬화."""
    data = json.loads(json_str)
    slides: list[PptxSlideSpec] = []
    for slide_data in data.get("slides", []):
        slides.append(parse_slide_spec(slide_data))
    return DesignSpec(slides=slides)
