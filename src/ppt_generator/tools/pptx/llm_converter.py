"""LLM을 활용한 HTML→PPTX 변환 파이프라인."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from bs4 import BeautifulSoup, Tag

from ppt_generator.interfaces.constants import (
    BEDROCK_REGION,
    PPTX_CONVERT_MAX_TOKENS,
    PPTX_CONVERT_MODEL_ID,
    PPTX_CONVERT_SYSTEM_PROMPT,
    PPTX_CONVERT_USER_PROMPT_TEMPLATE,
    PPTX_CONVERT_USER_PROMPT_WITH_IMAGE_TEMPLATE,
    SLIDES_HEIGHT_PX,
    SLIDES_WIDTH_PX,
)
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils import (
    parse_slide_spec,
    validate_slide_spec,
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



# parse_slide_spec와 validate_slide_spec은 spec_utils.py에서 import
# (하위 호환: 이 모듈에서 직접 import하는 기존 코드를 위해 re-export)
