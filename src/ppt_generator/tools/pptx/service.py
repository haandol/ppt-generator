"""PPTX 내보내기 서비스 — 오케스트레이션 레이어.

HTML 슬라이드를 편집 가능한 PPTX 파일로 변환하는 파이프라인을 조합한다.
실제 구현은 html_parser, slide_builder, llm_converter 모듈에 위임.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from pptx import Presentation

from ppt_generator.interfaces.constants import (
    PPTX_SLIDE_HEIGHT_EMU,
    PPTX_SLIDE_WIDTH_EMU,
)
from ppt_generator.interfaces.schemas import (
    ExportPptxRequest,
    ExportPptxResponse,
    PptxSlideSpec,
)
from ppt_generator.tools.pptx.html_parser import extract_background, parse_slides
from ppt_generator.tools.pptx.llm_converter import (
    _PLAYWRIGHT_AVAILABLE,
    capture_slide_screenshots,
    convert_all_sections_with_llm,
)
from ppt_generator.tools.pptx.slide_builder import SlideBuilder
from ppt_generator.tools.pptx.style_utils import scale_font_size
from ppt_generator.tools.slides.css_inliner import inline_css_classes
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


class ExportService:
    def __init__(
        self,
        slides_service: SlidesService,
        use_llm_convert: bool = True,
    ) -> None:
        self._slides_service = slides_service
        self._use_llm_convert = use_llm_convert
        self._builder = SlideBuilder()

    def export(self, request: ExportPptxRequest, output_dir: Path | None = None) -> ExportPptxResponse:
        html = self._slides_service.get_session_html(request.session_id)
        html = inline_css_classes(html)
        slide_divs = parse_slides(html)

        if not slide_divs:
            raise ValueError("슬라이드를 찾을 수 없습니다")

        prs = Presentation()
        prs.slide_width = PPTX_SLIDE_WIDTH_EMU
        prs.slide_height = PPTX_SLIDE_HEIGHT_EMU

        # Playwright 스크린샷 캡처
        screenshots: dict[int, bytes] = {}
        if self._use_llm_convert and _PLAYWRIGHT_AVAILABLE:
            screenshots = capture_slide_screenshots(html, len(slide_divs))

        # LLM 변환: 모든 section을 병렬로 변환
        llm_specs: dict[int, PptxSlideSpec | None] = {}
        if self._use_llm_convert:
            llm_specs = convert_all_sections_with_llm(slide_divs, screenshots)

        blank_layout = prs.slide_layouts[6]

        for idx, div in enumerate(slide_divs):
            slide = prs.slides.add_slide(blank_layout)
            self._builder.remove_placeholders(slide)

            spec = llm_specs.get(idx)
            if spec is not None:
                if spec.background_color:
                    self._builder.set_slide_background(slide, spec.background_color)
                self._builder.build_slide_from_spec(slide, spec)
            else:
                bg_color = extract_background(div)
                if bg_color:
                    self._builder.set_slide_background(slide, bg_color)
                self._builder.extract_elements(slide, div)

            self._builder.ensure_textboxes_on_top(slide)

            notes = div.get("data-speaker-notes", "")
            if notes:
                self._builder.set_speaker_notes(slide, notes)

        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="ppt_export_"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "presentation.pptx"
        prs.save(str(output_path))
        logger.info("PPTX 내보내기 완료: %s", output_path)
        return ExportPptxResponse(pptx_path=str(output_path))

    # 하위 호환 유지: 테스트에서 직접 호출하는 static method들
    _scale_font_size = staticmethod(scale_font_size)

    @staticmethod
    def _extract_head_html(html: str) -> str:
        from ppt_generator.tools.pptx.html_parser import extract_head_html
        return extract_head_html(html)

    @staticmethod
    def _build_single_slide_html(head_html: str, section) -> str:
        from ppt_generator.tools.pptx.html_parser import build_single_slide_html
        return build_single_slide_html(head_html, section)

    def _capture_slide_screenshots(self, html: str, num_slides: int) -> dict[int, bytes]:
        return capture_slide_screenshots(html, num_slides)

    def _convert_section_with_llm(self, section, screenshot: bytes | None = None):
        from ppt_generator.tools.pptx.llm_converter import convert_section_with_llm
        return convert_section_with_llm(section, screenshot=screenshot)
