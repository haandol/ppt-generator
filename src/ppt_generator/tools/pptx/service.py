from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass
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
    PPTX_BULLET_CHAR_L0,
    PPTX_BULLET_INDENT_EMU_L0,
    PPTX_BULLET_INDENT_EMU_L1,
    PPTX_BULLET_MARGIN_EMU_L0,
    PPTX_BULLET_MARGIN_EMU_L1,
    PPTX_FONT_NAME,
    REM_TO_PX,
)
from ppt_generator.interfaces.schemas import ExportPptxRequest, ExportPptxResponse
from ppt_generator.templates.layout_mapping import find_blank_layout_index
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


@dataclass
class _RichTextFragment:
    """HTML 요소에서 추출한 서식 정보를 담는 내부 데이터 구조."""

    text: str
    font_size: int | None = None
    color: str | None = None
    bold: bool = False
    italic: bool = False
    bullet_level: int = -1  # -1 = 불릿 아님, 0 = 1단계, 1 = 2단계
    paragraph_break: bool = False  # True이면 이 fragment 앞에서 새 paragraph 시작


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

            if child.name in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span", "ul", "ol"):
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

            # 이미지 체크 (기존 유지)
            img = region_div.find("img")
            if img and not region_div.get_text(strip=True):
                continue  # 이미지 전용 region은 건너뜀

            text = region_div.get_text(strip=True)
            if not text:
                continue

            # flex 레이아웃 감지
            if self._extract_flex_columns(slide, region_div, left, top, width, height):
                continue

            # 기본 경로: 리치 텍스트 파이프라인
            is_title = region_name in ("title", "subtitle")
            fragments = self._walk_region_content(region_div, parent_style={}, bullet_level=-1, is_title_region=is_title)
            if fragments:
                self._build_textbox_from_fragments(slide, fragments, left, top, width, height)

    # --- 리치 텍스트 파이프라인 ---

    def _walk_region_content(
        self,
        element: Tag,
        parent_style: dict[str, str | None],
        bullet_level: int = -1,
        is_title_region: bool = False,
    ) -> list[_RichTextFragment]:
        """Region div 내부의 자식 요소를 재귀적으로 순회하며 _RichTextFragment 리스트를 생성."""
        fragments: list[_RichTextFragment] = []

        for child in element.children:
            if isinstance(child, str):
                # NavigableString (텍스트 노드)
                text = child.strip()
                if text:
                    fragments.append(_RichTextFragment(
                        text=text,
                        font_size=self._resolve_int(parent_style.get("font_size")),
                        color=parent_style.get("color"),
                        bold=parent_style.get("bold") is True or is_title_region,
                        italic=parent_style.get("italic") is True,
                        bullet_level=bullet_level,
                    ))
                continue

            if not isinstance(child, Tag):
                continue

            tag = child.name
            inline_style = self._parse_inline_style(child.get("style", ""))

            # 현재 요소의 스타일 결정 (자식 명시 > 부모 상속)
            current_style = self._merge_styles(parent_style, inline_style, tag)

            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                heading_text = child.get_text(strip=True)
                if heading_text:
                    fs = self._extract_font_size(inline_style)
                    fragments.append(_RichTextFragment(
                        text=heading_text,
                        font_size=fs or self._resolve_int(current_style.get("font_size")),
                        color=current_style.get("color"),
                        bold=True,
                        italic=current_style.get("italic") is True,
                        bullet_level=bullet_level,
                        paragraph_break=True,
                    ))
            elif tag == "p":
                sub = self._walk_region_content(child, current_style, bullet_level, is_title_region)
                if sub:
                    sub[0] = _RichTextFragment(
                        text=sub[0].text,
                        font_size=sub[0].font_size,
                        color=sub[0].color,
                        bold=sub[0].bold,
                        italic=sub[0].italic,
                        bullet_level=sub[0].bullet_level,
                        paragraph_break=True,
                    )
                    fragments.extend(sub)
            elif tag in ("ul", "ol"):
                next_level = max(bullet_level + 1, 0)
                for li in child.find_all("li", recursive=False):
                    li_style = self._parse_inline_style(li.get("style", ""))
                    li_merged = self._merge_styles(current_style, li_style, "li")
                    li_sub = self._walk_region_content(li, li_merged, next_level, is_title_region)
                    if li_sub:
                        li_sub[0] = _RichTextFragment(
                            text=li_sub[0].text,
                            font_size=li_sub[0].font_size,
                            color=li_sub[0].color,
                            bold=li_sub[0].bold,
                            italic=li_sub[0].italic,
                            bullet_level=next_level,
                            paragraph_break=True,
                        )
                        fragments.extend(li_sub)
                    else:
                        li_text = li.get_text(strip=True)
                        if li_text:
                            fragments.append(_RichTextFragment(
                                text=li_text,
                                font_size=self._resolve_int(li_merged.get("font_size")),
                                color=li_merged.get("color"),
                                bold=li_merged.get("bold") is True,
                                italic=li_merged.get("italic") is True,
                                bullet_level=next_level,
                                paragraph_break=True,
                            ))
            elif tag in ("strong", "b"):
                sub = self._walk_region_content(child, {**current_style, "bold": True}, bullet_level, is_title_region)
                fragments.extend(sub)
                if not sub:
                    text = child.get_text(strip=True)
                    if text:
                        fragments.append(_RichTextFragment(
                            text=text,
                            font_size=self._resolve_int(current_style.get("font_size")),
                            color=current_style.get("color"),
                            bold=True,
                            italic=current_style.get("italic") is True,
                            bullet_level=bullet_level,
                        ))
            elif tag in ("em", "i"):
                sub = self._walk_region_content(child, {**current_style, "italic": True}, bullet_level, is_title_region)
                fragments.extend(sub)
                if not sub:
                    text = child.get_text(strip=True)
                    if text:
                        fragments.append(_RichTextFragment(
                            text=text,
                            font_size=self._resolve_int(current_style.get("font_size")),
                            color=current_style.get("color"),
                            bold=current_style.get("bold") is True,
                            italic=True,
                            bullet_level=bullet_level,
                        ))
            elif tag in ("div", "span", "li"):
                sub = self._walk_region_content(child, current_style, bullet_level, is_title_region)
                fragments.extend(sub)
            else:
                # 기타 요소: 텍스트만 추출
                text = child.get_text(strip=True)
                if text:
                    fragments.append(_RichTextFragment(
                        text=text,
                        font_size=self._resolve_int(current_style.get("font_size")),
                        color=current_style.get("color"),
                        bold=current_style.get("bold") is True or is_title_region,
                        italic=current_style.get("italic") is True,
                        bullet_level=bullet_level,
                    ))

        return fragments

    def _merge_styles(
        self, parent: dict[str, str | None], inline: dict[str, str], tag: str
    ) -> dict[str, str | None]:
        """부모 style을 자식에 전파하되, 자식의 명시적 style이 우선."""
        merged: dict[str, str | None] = dict(parent)

        fs = self._extract_font_size(inline)
        if fs is not None:
            merged["font_size"] = fs

        color_str = inline.get("color", "")
        if color_str:
            merged["color"] = color_str

        fw = inline.get("font-weight", "")
        if fw in ("bold", "bolder") or (fw.isdigit() and int(fw) >= 700):
            merged["bold"] = True
        elif tag in ("strong", "b"):
            merged["bold"] = True

        fs_style = inline.get("font-style", "")
        if fs_style == "italic":
            merged["italic"] = True
        elif tag in ("em", "i"):
            merged["italic"] = True

        return merged

    @staticmethod
    def _resolve_int(value) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _build_textbox_from_fragments(
        self, slide, fragments: list[_RichTextFragment],
        left: float, top: float, width: float, height: float,
    ) -> None:
        """_RichTextFragment 리스트를 python-pptx 텍스트박스로 변환."""
        txbox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = txbox.text_frame
        tf.word_wrap = True

        current_para = tf.paragraphs[0]
        is_first_para = True

        for frag in fragments:
            if not frag.text:
                continue

            if frag.paragraph_break and not is_first_para:
                current_para = tf.add_paragraph()

            run = current_para.add_run()
            run.text = frag.text
            run.font.name = PPTX_FONT_NAME
            if frag.font_size:
                run.font.size = Pt(frag.font_size)
            run.font.bold = frag.bold
            run.font.italic = frag.italic
            if frag.color:
                rgb = self._parse_color(frag.color)
                if rgb:
                    run.font.color.rgb = rgb

            # 불릿 설정
            if frag.bullet_level >= 0 and frag.paragraph_break:
                self._apply_bullet(current_para, frag.bullet_level)

            if frag.paragraph_break:
                is_first_para = False

    def _apply_bullet(self, paragraph, level: int) -> None:
        """paragraph에 불릿 마커와 들여쓰기를 XML로 설정."""
        pPr = paragraph._p.get_or_add_pPr()

        if level == 0:
            margin = PPTX_BULLET_MARGIN_EMU_L0
            indent = PPTX_BULLET_INDENT_EMU_L0
        else:
            margin = PPTX_BULLET_MARGIN_EMU_L1
            indent = PPTX_BULLET_INDENT_EMU_L1

        pPr.set("marL", str(margin))
        pPr.set("indent", str(indent))

        buNone = pPr.find(qn("a:buNone"))
        if buNone is not None:
            pPr.remove(buNone)

        buChar = pPr.find(qn("a:buChar"))
        if buChar is None:
            buChar = pPr.makeelement(qn("a:buChar"), {})
            pPr.append(buChar)
        buChar.set("char", PPTX_BULLET_CHAR_L0)

    def _extract_flex_columns(
        self, slide, region_div: Tag,
        left: float, top: float, width: float, height: float,
    ) -> bool:
        """flex 컨테이너가 있으면 자식을 개별 텍스트박스로 분할 배치. 처리했으면 True 반환."""
        # region_div 직계 자식 중 display:flex인 div를 찾는다
        flex_container = None
        for child in region_div.children:
            if not isinstance(child, Tag):
                continue
            child_style = self._parse_inline_style(child.get("style", ""))
            display = child_style.get("display", "")
            if "flex" in display and child.name == "div":
                flex_container = child
                break

        if flex_container is None:
            return False

        flex_style = self._parse_inline_style(flex_container.get("style", ""))
        # flex 자식 수 파악
        flex_children = [c for c in flex_container.children if isinstance(c, Tag)]
        if len(flex_children) < 2:
            return False

        # gap 추출 (px 값)
        gap_str = flex_style.get("gap", "0")
        gap_match = re.match(r"(\d+(?:\.\d+)?)\s*px", gap_str)
        gap_px = float(gap_match.group(1)) if gap_match else 0
        gap_inches = gap_px * EXPORT_PX_TO_INCHES_X

        n = len(flex_children)
        total_gap = gap_inches * (n - 1)
        col_width = (width - total_gap) / n

        for i, col_child in enumerate(flex_children):
            col_left = left + i * (col_width + gap_inches)
            fragments = self._walk_region_content(col_child, parent_style={}, bullet_level=-1)
            if fragments:
                self._build_textbox_from_fragments(slide, fragments, col_left, top, col_width, height)

        return True

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
        match = re.match(r"(\d+(?:\.\d+)?)\s*rem", fs)
        if match:
            return int(float(match.group(1)) * REM_TO_PX)
        match = re.match(r"(\d+(?:\.\d+)?)\s*em", fs)
        if match:
            return int(float(match.group(1)) * REM_TO_PX)
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

