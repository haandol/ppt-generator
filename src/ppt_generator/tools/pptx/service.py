from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from ppt_generator.interfaces.constants import (
    PPTX_BODY_FONT_SIZE_PT,
    PPTX_FONT_NAME,
    PPTX_TITLE_FONT_SIZE_PT,
)
from ppt_generator.interfaces.schemas import PptxRequest, PptxResponse, SlideElement, SlideOutline
from ppt_generator.templates.layout_mapping import find_blank_layout_index, get_layout_info

logger = logging.getLogger(__name__)


class PptxService:
    def __init__(self, template_path: Path) -> None:
        self._template_path = template_path

    def generate(self, request: PptxRequest) -> PptxResponse:
        if not request.slides:
            raise ValueError("슬라이드 목록이 비어있습니다.")

        if self._template_path.exists():
            prs = Presentation(str(self._template_path))
            self._remove_existing_slides(prs)
        else:
            logger.warning("템플릿 파일 없음: %s, 기본 프레젠테이션으로 폴백", self._template_path)
            prs = Presentation()

        for i, slide_outline in enumerate(request.slides):
            if slide_outline.elements:
                self._add_freeform_slide(prs, slide_outline, i, request.image_paths)
            else:
                self._add_placeholder_slide(prs, slide_outline, i, request.image_paths)

        output_path = Path(tempfile.mkdtemp(prefix="ppt_output_")) / "presentation.pptx"
        prs.save(str(output_path))
        logger.info("PPTX 생성 완료: %s", output_path)
        return PptxResponse(pptx_path=str(output_path))

    def _remove_existing_slides(self, prs: Presentation) -> None:
        sldIdLst = prs.part._element.find(qn("p:sldIdLst"))
        if sldIdLst is None:
            return
        for sldId in list(sldIdLst):
            rId = sldId.get(qn("r:id"))
            prs.part.drop_rel(rId)
            sldIdLst.remove(sldId)

    def _add_placeholder_slide(
        self,
        prs: Presentation,
        slide_outline: SlideOutline,
        slide_index: int,
        image_paths: dict[int, str],
    ) -> None:
        layout_info = get_layout_info(slide_outline.layout_type)
        try:
            slide_layout = prs.slide_layouts[layout_info.layout_index]
        except IndexError:
            logger.warning(
                "레이아웃 인덱스 %d 없음, 첫 번째 레이아웃 사용", layout_info.layout_index
            )
            slide_layout = prs.slide_layouts[0]

        slide = prs.slides.add_slide(slide_layout)

        self._set_title(slide, slide_outline.title, layout_info.title_ph)
        self._set_subtitle(slide, slide_outline.bullets, layout_info.subtitle_ph)
        self._set_body(slide, slide_outline.bullets, layout_info.body_ph)
        self._set_image(slide, slide_index, image_paths, layout_info.picture_ph, slide_outline.image_idea)
        self._set_speaker_notes(slide, slide_outline.speaker_notes)

    def _add_freeform_slide(
        self,
        prs: Presentation,
        slide_outline: SlideOutline,
        slide_index: int,
        image_paths: dict[int, str],
    ) -> None:
        blank_idx = find_blank_layout_index(prs)
        try:
            slide_layout = prs.slide_layouts[blank_idx]
        except IndexError:
            logger.warning("Blank 레이아웃 인덱스 %d 없음, 첫 번째 레이아웃 사용", blank_idx)
            slide_layout = prs.slide_layouts[0]

        slide = prs.slides.add_slide(slide_layout)
        self._populate_freeform(slide, slide_outline, slide_index, image_paths)
        self._set_speaker_notes(slide, slide_outline.speaker_notes)

    def _populate_freeform(
        self,
        slide,
        slide_outline: SlideOutline,
        slide_index: int,
        image_paths: dict[int, str],
    ) -> None:
        for element in slide_outline.elements:
            left = Inches(element.left)
            top = Inches(element.top)
            width = Inches(element.width)
            height = Inches(element.height)

            if element.type == "textbox":
                self._add_freeform_textbox(slide, left, top, width, height, element)
            elif element.type == "image":
                self._add_freeform_image(slide, left, top, width, height, slide_index, image_paths, element)
            elif element.type == "shape":
                self._add_freeform_shape(slide, left, top, width, height, element)
            else:
                logger.warning("알 수 없는 freeform 요소 타입: %s", element.type)

    def _add_freeform_textbox(self, slide, left, top, width, height, element: SlideElement) -> None:
        txbox = slide.shapes.add_textbox(left, top, width, height)
        tf = txbox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = element.content
        for run in p.runs:
            run.font.name = PPTX_FONT_NAME
            run.font.size = Pt(element.font_size_pt)
            run.font.bold = element.bold

    def _add_freeform_image(
        self, slide, left, top, width, height, slide_index: int, image_paths: dict[int, str], element: SlideElement
    ) -> None:
        image_path = image_paths.get(slide_index)
        if not image_path or not Path(image_path).exists():
            if image_path:
                logger.warning("Freeform 이미지 파일 누락: %s", image_path)
            return
        slide.shapes.add_picture(image_path, left, top, width, height)

    def _add_freeform_shape(self, slide, left, top, width, height, element: SlideElement) -> None:
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        tf = shape.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = element.content
        for run in p.runs:
            run.font.name = PPTX_FONT_NAME
            run.font.size = Pt(element.font_size_pt)
            run.font.bold = element.bold

    def _set_title(self, slide, title: str, ph_idx: int | None) -> None:
        if ph_idx is None or not title:
            return
        try:
            ph = slide.placeholders[ph_idx]
            ph.text = title
            for paragraph in ph.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = PPTX_FONT_NAME
                    run.font.size = Pt(PPTX_TITLE_FONT_SIZE_PT)
        except KeyError:
            logger.warning("제목 placeholder[%d] 없음", ph_idx)

    def _set_subtitle(self, slide, bullets: list[str], ph_idx: int | None) -> None:
        if ph_idx is None or not bullets:
            return
        try:
            ph = slide.placeholders[ph_idx]
            ph.text = " | ".join(bullets)
            for paragraph in ph.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.name = PPTX_FONT_NAME
        except KeyError:
            logger.warning("부제목 placeholder[%d] 없음", ph_idx)

    def _set_body(self, slide, bullets: list[str], ph_idx: int | None) -> None:
        if ph_idx is None or not bullets:
            return
        try:
            ph = slide.placeholders[ph_idx]
            tf = ph.text_frame
            tf.clear()
            for j, bullet in enumerate(bullets):
                if j == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.text = bullet
                p.level = 0
                for run in p.runs:
                    run.font.name = PPTX_FONT_NAME
                    run.font.size = Pt(PPTX_BODY_FONT_SIZE_PT)
        except KeyError:
            logger.warning("본문 placeholder[%d] 없음", ph_idx)

    def _set_image(
        self,
        slide,
        slide_index: int,
        image_paths: dict[int, str],
        ph_idx: int | None,
        alt_text: str,
    ) -> None:
        if ph_idx is None:
            return
        image_path = image_paths.get(slide_index)
        if not image_path or not Path(image_path).exists():
            if image_path:
                logger.warning("이미지 파일 누락: %s", image_path)
            return
        try:
            ph = slide.placeholders[ph_idx]
            ph.insert_picture(image_path)
            pic = ph._element
            nsmap = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
            cNvPr = pic.find(".//p:cNvPr", nsmap)
            if cNvPr is not None:
                cNvPr.set("descr", alt_text or "")
        except (KeyError, Exception):
            logger.warning("이미지 placeholder[%d] 삽입 실패 (슬라이드 %d)", ph_idx, slide_index)

    def _set_speaker_notes(self, slide, notes: str) -> None:
        if not notes:
            return
        notes_slide = slide.notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = notes
