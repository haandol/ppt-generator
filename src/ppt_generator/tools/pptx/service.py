from __future__ import annotations

import io
import logging
import re
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from ppt_generator.interfaces.constants import (
    EXPORT_PX_TO_INCHES_X,
    EXPORT_PX_TO_INCHES_Y,
    PPTX_FONT_NAME,
)
from ppt_generator.interfaces.schemas import ExportPptxRequest, ExportPptxResponse
from ppt_generator.templates.layout_mapping import find_blank_layout_index
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


class ExportService:
    def __init__(self, slides_service: SlidesService, template_path: Path) -> None:
        self._slides_service = slides_service
        self._template_path = template_path

    def export(self, request: ExportPptxRequest, output_dir: Path | None = None) -> ExportPptxResponse:
        html = self._slides_service.get_session_html(request.session_id)
        slide_divs = self._parse_slides(html)

        if not slide_divs:
            raise ValueError("슬라이드를 찾을 수 없습니다")

        if self._template_path.exists():
            prs = Presentation(str(self._template_path))
            self._remove_existing_slides(prs)
        else:
            logger.warning("템플릿 파일 없음: %s, 기본 프레젠테이션으로 폴백", self._template_path)
            prs = Presentation()

        for div in slide_divs:
            blank_idx = find_blank_layout_index(prs)
            try:
                slide_layout = prs.slide_layouts[blank_idx]
            except IndexError:
                slide_layout = prs.slide_layouts[0]

            slide = prs.slides.add_slide(slide_layout)

            bg_color = self._extract_background(div)
            if bg_color:
                self._set_slide_background(slide, bg_color)

            self._extract_elements(slide, div)

            notes = div.get("data-speaker-notes", "")
            if notes:
                self._set_speaker_notes(slide, notes)

        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="ppt_export_"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "presentation.pptx"
        prs.save(str(output_path))
        logger.info("PPTX 내보내기 완료: %s", output_path)
        return ExportPptxResponse(pptx_path=str(output_path))

    # --- HTML 파싱 ---

    def _parse_slides(self, html: str) -> list[Tag]:
        soup = BeautifulSoup(html, "html.parser")
        # body 안의 section 태그들을 슬라이드로 파싱
        body = soup.find("body")
        if body:
            return body.find_all("section", recursive=False)
        # 폴백: 전체에서 section 태그 검색
        return soup.find_all("section")

    def _parse_inline_style(self, style_str: str | None) -> dict[str, str]:
        if not style_str:
            return {}
        result: dict[str, str] = {}
        for part in style_str.split(";"):
            part = part.strip()
            if ":" not in part:
                continue
            key, _, value = part.partition(":")
            result[key.strip().lower()] = value.strip()
        return result

    def _px_to_inches(self, value: str, axis: str) -> float | None:
        match = re.match(r"(-?\d+(?:\.\d+)?)\s*px", value.strip())
        if not match:
            if re.match(r"-?\d+(?:\.\d+)?$", value.strip()):
                px = float(value.strip())
            else:
                logger.warning("px이 아닌 단위 무시: %s", value)
                return None
        else:
            px = float(match.group(1))
        factor = EXPORT_PX_TO_INCHES_X if axis == "x" else EXPORT_PX_TO_INCHES_Y
        return px * factor

    # --- 슬라이드 기본 설정 ---

    def _remove_existing_slides(self, prs: Presentation) -> None:
        sldIdLst = prs.part._element.find(qn("p:sldIdLst"))
        if sldIdLst is None:
            return
        for sldId in list(sldIdLst):
            rId = sldId.get(qn("r:id"))
            prs.part.drop_rel(rId)
            sldIdLst.remove(sldId)

    def _set_slide_background(self, slide, color: str) -> None:
        rgb = self._parse_color(color)
        if rgb is None:
            return
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = rgb

    def _set_speaker_notes(self, slide, notes: str) -> None:
        if not notes:
            return
        notes_slide = slide.notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = notes

    # --- 배경 추출 ---

    def _extract_background(self, div: Tag) -> str | None:
        # data-wrapper div에서 먼저 배경색 추출 시도
        wrapper = div.find("div", attrs={"data-wrapper": "true"})
        if wrapper:
            wrapper_style = self._parse_inline_style(wrapper.get("style", ""))
            bg = wrapper_style.get("background-color") or wrapper_style.get("background")
            if bg:
                color_match = re.search(r"#[0-9a-fA-F]{3,8}", bg)
                if color_match:
                    return color_match.group(0)
                rgb_match = re.search(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", bg)
                if rgb_match:
                    return bg
                return bg

        # 폴백: section 자체의 style에서 추출
        style = self._parse_inline_style(div.get("style", ""))
        bg = style.get("background-color") or style.get("background")
        if not bg:
            return None
        # gradient 등 복합 배경에서 첫 번째 색상 추출 시도
        color_match = re.search(r"#[0-9a-fA-F]{3,8}", bg)
        if color_match:
            return color_match.group(0)
        rgb_match = re.search(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", bg)
        if rgb_match:
            return bg
        return bg

    # --- 요소 추출 ---

    def _extract_elements(self, slide, section: Tag) -> None:
        wrapper = section.find("div", attrs={"data-wrapper": "true"})
        if wrapper:
            self._extract_region_elements(slide, wrapper)
            return
        # 레거시: data-wrapper가 없는 기존 HTML
        self._extract_legacy_elements(slide, section)

    def _extract_legacy_elements(self, slide, section: Tag) -> None:
        for child in section.children:
            if not isinstance(child, Tag):
                continue
            style = self._parse_inline_style(child.get("style", ""))

            if child.name == "img":
                self._add_picture(slide, child, style)
            elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span", "ul", "ol"):
                if child.get_text(strip=True):
                    self._add_textbox(slide, child, style)
            else:
                text = child.get_text(strip=True)
                if text:
                    self._add_textbox(slide, child, style)

    def _extract_region_elements(self, slide, wrapper: Tag) -> None:
        """data-region div를 순회하며, region 좌표를 사용하여 PPTX 요소 배치."""
        for region_div in wrapper.find_all("div", attrs={"data-region": True}, recursive=False):
            region_style = self._parse_inline_style(region_div.get("style", ""))
            left, top, width, height = self._get_position_and_size(region_style)
            region_name = region_div["data-region"]
            is_title = region_name in ("title", "subtitle")

            # region 내부에서 img와 텍스트 요소를 추출
            has_img = False
            for child in region_div.descendants:
                if not isinstance(child, Tag):
                    continue
                if child.name == "img":
                    self._add_picture(slide, child, region_style)
                    has_img = True

            if not has_img:
                text = region_div.get_text(strip=True)
                if text:
                    self._add_textbox_at(slide, region_div, left, top, width, height, is_title=is_title)

    def _get_position_and_size(self, style: dict[str, str]) -> tuple[float, float, float, float]:
        left = self._px_to_inches(style.get("left", "0"), "x") or 0.0
        top = self._px_to_inches(style.get("top", "0"), "y") or 0.0
        width = self._px_to_inches(style.get("width", "72"), "x") or 1.0
        height = self._px_to_inches(style.get("height", "72"), "y") or 1.0
        return left, top, width, height

    def _add_textbox(self, slide, element: Tag, style: dict[str, str]) -> None:
        left, top, width, height = self._get_position_and_size(style)
        txbox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txbox.text_frame
        tf.word_wrap = True

        # 텍스트 추출 및 서식 적용
        font_size = self._extract_font_size(style)
        is_bold = self._is_bold(element, style)
        color = self._extract_color(style)

        # 단락별로 텍스트 추출
        text = element.get_text(separator="\n", strip=True)
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = line.strip()
            for run in p.runs:
                run.font.name = PPTX_FONT_NAME
                if font_size:
                    run.font.size = Pt(font_size)
                run.font.bold = is_bold
                if color:
                    run.font.color.rgb = color

    def _add_textbox_at(
        self, slide, element: Tag,
        left: float, top: float, width: float, height: float,
        is_title: bool = False,
    ) -> None:
        """region 좌표를 직접 사용하여 텍스트박스를 배치."""
        txbox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txbox.text_frame
        tf.word_wrap = True

        style = self._parse_inline_style(element.get("style", ""))
        font_size = self._extract_font_size(style)
        color = self._extract_color(style)

        text = element.get_text(separator="\n", strip=True)
        lines = text.split("\n")

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = line.strip()
            for run in p.runs:
                run.font.name = PPTX_FONT_NAME
                if font_size:
                    run.font.size = Pt(font_size)
                run.font.bold = is_title
                if color:
                    run.font.color.rgb = color

    def _add_picture(self, slide, element: Tag, style: dict[str, str]) -> None:
        src = element.get("src", "")
        if not src:
            logger.warning("이미지 소스가 비어있음")
            return

        image_stream = self._load_image(src)
        if image_stream is None:
            return

        left, top, width, height = self._get_position_and_size(style)

        try:
            pic = slide.shapes.add_picture(image_stream, Inches(left), Inches(top), Inches(width), Inches(height))
            # alt-text 설정
            alt_text = element.get("alt", "")
            if alt_text:
                nvPicPr = pic._element.find(qn("p:nvPicPr"))
                if nvPicPr is not None:
                    cNvPr = nvPicPr.find(qn("p:cNvPr"))
                    if cNvPr is not None:
                        cNvPr.set("descr", alt_text)
        except Exception:
            logger.warning("이미지 삽입 실패", exc_info=True)

    def _add_shape(self, slide, element: Tag, style: dict[str, str]) -> None:
        left, top, width, height = self._get_position_and_size(style)
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
        )
        text = element.get_text(strip=True)
        if text:
            tf = shape.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = text
            for run in p.runs:
                run.font.name = PPTX_FONT_NAME

    # --- 스타일 추출 유틸리티 ---

    def _extract_font_size(self, style: dict[str, str]) -> int | None:
        fs = style.get("font-size", "")
        match = re.match(r"(\d+(?:\.\d+)?)\s*px", fs)
        if match:
            # CSS px ≈ PPTX pt (72dpi 기준 1:1)
            return int(float(match.group(1)))
        match = re.match(r"(\d+(?:\.\d+)?)\s*pt", fs)
        if match:
            return int(float(match.group(1)))
        return None

    def _is_bold(self, element: Tag, style: dict[str, str]) -> bool:
        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return True
        if element.find(("strong", "b")):
            return True
        fw = style.get("font-weight", "")
        if fw in ("bold", "bolder") or (fw.isdigit() and int(fw) >= 700):
            return True
        return False

    def _extract_color(self, style: dict[str, str]) -> RGBColor | None:
        color_str = style.get("color", "")
        return self._parse_color(color_str)

    def _parse_color(self, color_str: str) -> RGBColor | None:
        if not color_str:
            return None
        # #RRGGBB or #RGB
        hex_match = re.match(r"#([0-9a-fA-F]{6})", color_str)
        if hex_match:
            hex_val = hex_match.group(1)
            return RGBColor(int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16))
        short_hex = re.match(r"#([0-9a-fA-F]{3})(?:\s|;|$)", color_str)
        if short_hex:
            h = short_hex.group(1)
            return RGBColor(int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
        # rgb(r, g, b)
        rgb_match = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color_str)
        if rgb_match:
            return RGBColor(int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3)))
        return None

    def _load_image(self, src: str) -> io.BytesIO | None:
        if src.startswith("file://"):
            file_path = Path(src[7:])  # file:// 제거
            if not file_path.exists():
                logger.warning("이미지 파일 없음: %s", file_path)
                return None
            try:
                return io.BytesIO(file_path.read_bytes())
            except Exception:
                logger.warning("이미지 파일 읽기 실패: %s", file_path, exc_info=True)
                return None
        logger.warning("지원하지 않는 이미지 소스: %s", src[:50])
        return None
