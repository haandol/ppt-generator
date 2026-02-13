"""LLM을 활용한 HTML→PPTX 변환 파이프라인."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace

import boto3
from bs4 import BeautifulSoup, Tag

from ppt_generator.interfaces.constants import (
    BEDROCK_REGION,
    PPTX_CONVERT_MAX_TOKENS,
    PPTX_CONVERT_MODEL_ID,
    PPTX_CONVERT_SYSTEM_PROMPT,
    PPTX_CONVERT_USER_PROMPT_TEMPLATE,
    PPTX_CONVERT_USER_PROMPT_WITH_IMAGE_TEMPLATE,
    PPTX_VALIDATE_FONT_MAX_PT,
    PPTX_VALIDATE_FONT_MIN_PT,
    PPTX_VALIDATE_LINE_HEIGHT_FACTOR,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
)
from ppt_generator.interfaces.schemas import (
    PptxParagraph,
    PptxShape,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.pptx.html_parser import (
    build_single_slide_html,
    extract_head_html,
)

try:
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)


def capture_slide_screenshots(html: str, num_slides: int) -> dict[int, bytes]:
    """Playwright로 각 <section>을 개별 로드하여 1280x720 PNG로 캡처."""
    if not _PLAYWRIGHT_AVAILABLE:
        return {}

    head_html = extract_head_html(html)
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("body")
    sections = (body.find_all("section", recursive=False) if body
                else soup.find_all("section"))

    if not sections:
        return {}

    screenshots: dict[int, bytes] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": SLIDES_WIDTH_PX, "height": SLIDES_HEIGHT_PX},
            )
            for idx, section in enumerate(sections):
                try:
                    slide_html = build_single_slide_html(head_html, section)
                    page.set_content(slide_html, wait_until="load")
                    section_el = page.query_selector("section")
                    if section_el:
                        screenshots[idx] = section_el.screenshot(type="png")
                except Exception:
                    logger.warning(
                        "슬라이드 %d 스크린샷 캡처 실패, 해당 슬라이드는 텍스트만으로 변환", idx,
                    )
            browser.close()
    except Exception:
        logger.warning("Playwright 브라우저 실행 실패, 스크린샷 없이 변환 진행")
        return {}

    logger.info("스크린샷 캡처 완료: %d/%d 슬라이드", len(screenshots), num_slides)
    return screenshots


def convert_all_sections_with_llm(
    sections: list[Tag], screenshots: dict[int, bytes] | None = None,
) -> dict[int, PptxSlideSpec | None]:
    """모든 section을 ThreadPoolExecutor로 병렬 LLM 변환."""
    results: dict[int, PptxSlideSpec | None] = {}
    if screenshots is None:
        screenshots = {}

    def _convert(idx: int, section: Tag) -> tuple[int, PptxSlideSpec | None]:
        try:
            screenshot = screenshots.get(idx)
            spec = convert_section_with_llm(section, screenshot=screenshot)
            return idx, spec
        except Exception:
            logger.exception("LLM 변환 실패 (슬라이드 %d), 룰 기반 폴백", idx)
            return idx, None

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_convert, i, s): i for i, s in enumerate(sections)}
        for future in as_completed(futures):
            idx, spec = future.result()
            results[idx] = spec

    return results


def convert_section_with_llm(
    section: Tag, screenshot: bytes | None = None,
) -> PptxSlideSpec:
    """단일 section HTML을 Bedrock Converse API로 LLM에 보내 PptxSlideSpec을 반환."""
    section_html = str(section)

    if screenshot:
        user_prompt = PPTX_CONVERT_USER_PROMPT_WITH_IMAGE_TEMPLATE.format(
            section_html=section_html,
        )
        content_blocks: list[dict] = [
            {"image": {"format": "png", "source": {"bytes": screenshot}}},
            {"text": user_prompt},
        ]
    else:
        user_prompt = PPTX_CONVERT_USER_PROMPT_TEMPLATE.format(section_html=section_html)
        content_blocks = [{"text": user_prompt}]

    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    response = client.converse(
        modelId=PPTX_CONVERT_MODEL_ID,
        system=[{"text": PPTX_CONVERT_SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": content_blocks}],
        inferenceConfig={"maxTokens": PPTX_CONVERT_MAX_TOKENS, "temperature": 0.2},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    json_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    json_text = re.sub(r"\s*```$", "", json_text.strip())
    data = json.loads(json_text)
    spec = parse_slide_spec(data)
    return validate_slide_spec(spec)


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
        ))

    return PptxSlideSpec(
        background_color=data.get("background_color"),
        textboxes=textboxes,
        shapes=shapes,
        images=[],
    )


def validate_slide_spec(spec: PptxSlideSpec) -> PptxSlideSpec:
    """LLM 출력 PptxSlideSpec을 검증하고 보정한다."""
    canvas_w = SLIDES_WIDTH_PX
    canvas_h = SLIDES_HEIGHT_PX
    font_min = PPTX_VALIDATE_FONT_MIN_PT
    font_max = PPTX_VALIDATE_FONT_MAX_PT
    lh_factor = PPTX_VALIDATE_LINE_HEIGHT_FACTOR

    def _clamp_font(pt: int | None) -> int | None:
        if pt is None:
            return None
        return max(font_min, min(font_max, pt))

    def _clip_rect(left: float, top: float, width: float, height: float) -> tuple[float, float, float, float]:
        left = max(0, min(left, canvas_w - 10))
        top = max(0, min(top, canvas_h - 10))
        width = max(10, min(width, canvas_w - left))
        height = max(10, min(height, canvas_h - top))
        return left, top, width, height

    validated_textboxes: list[PptxTextBox] = []
    for tb in spec.textboxes:
        has_text = any(
            run.text.strip()
            for para in tb.paragraphs
            for run in para.runs
        )
        if not has_text:
            continue

        new_paragraphs: list[PptxParagraph] = []
        max_font_in_tb = font_min
        num_lines = 0
        for para in tb.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                clamped_size = _clamp_font(run.font_size_pt)
                new_runs.append(replace(run, font_size_pt=clamped_size))
                if clamped_size and clamped_size > max_font_in_tb:
                    max_font_in_tb = clamped_size
            new_paragraphs.append(replace(para, runs=new_runs))
            num_lines += 1

        left, top, width, height = _clip_rect(tb.left_px, tb.top_px, tb.width_px, tb.height_px)

        min_required_height = num_lines * max_font_in_tb * lh_factor
        if height < min_required_height:
            height = min(min_required_height, canvas_h - top)

        validated_textboxes.append(PptxTextBox(
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            paragraphs=new_paragraphs,
            line_spacing_pt=tb.line_spacing_pt,
            vertical_alignment=tb.vertical_alignment,
        ))

    validated_shapes: list[PptxShape] = []
    for s in spec.shapes:
        left, top, width, height = _clip_rect(s.left_px, s.top_px, s.width_px, s.height_px)
        clamped_text_size = _clamp_font(s.text_size_pt)

        # paragraphs 내부 폰트 클램핑
        new_shape_paragraphs: list[PptxParagraph] = []
        shape_max_font = font_min
        shape_num_lines = 0
        for para in s.paragraphs:
            new_runs: list[PptxTextRun] = []
            for run in para.runs:
                clamped = _clamp_font(run.font_size_pt)
                new_runs.append(replace(run, font_size_pt=clamped))
                if clamped and clamped > shape_max_font:
                    shape_max_font = clamped
            new_shape_paragraphs.append(replace(para, runs=new_runs))
            shape_num_lines += 1

        if s.text and clamped_text_size:
            line_count = s.text.count("\n") + 1
            min_h = line_count * clamped_text_size * lh_factor
            if height < min_h:
                height = min(min_h, canvas_h - top)

        if new_shape_paragraphs and shape_num_lines > 0:
            min_h = shape_num_lines * shape_max_font * lh_factor
            if height < min_h:
                height = min(min_h, canvas_h - top)

        validated_shapes.append(replace(
            s,
            left_px=left,
            top_px=top,
            width_px=width,
            height_px=height,
            text_size_pt=clamped_text_size,
            paragraphs=new_shape_paragraphs,
        ))

    return PptxSlideSpec(
        background_color=spec.background_color,
        textboxes=validated_textboxes,
        shapes=validated_shapes,
        images=spec.images,
    )
