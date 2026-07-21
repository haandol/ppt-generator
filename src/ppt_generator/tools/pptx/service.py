"""PPTX 내보내기 서비스 — 디자인 스펙 기반 파이프라인.

DesignSpec(PptxSlideSpec 리스트)을 편집 가능한 PPTX 파일로 변환한다.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from pptx import Presentation

from ppt_generator.interfaces import bg_image_utils
from ppt_generator.interfaces.constants import (
    PPTX_SLIDE_HEIGHT_EMU,
    PPTX_SLIDE_WIDTH_EMU,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    ExportPptxResponse,
)
from ppt_generator.interfaces.spec_utils import clean_slide_spec
from ppt_generator.tools.pptx.slide_builder import SlideBuilder

logger = logging.getLogger(__name__)


class ExportService:
    def __init__(self) -> None:
        self._builder = SlideBuilder()

    def export_from_design_spec(
        self,
        design_spec: DesignSpec,
        output_dir: Path | None = None,
        *,
        skip_autofit: bool = False,
        color_theme: str = "dark",
        bg_image_policy: str = "gradient",
    ) -> ExportPptxResponse:
        """DesignSpec → PPTX 직접 변환.

        DesignSpec.slides를 순회하여 SlideBuilder.build_slide_from_spec()으로 직접 생성.

        bg_image_policy 가 "none" 이면 title/closing 기본 배경 이미지 자동 폴백을
        생략한다 (명시 배경은 그대로 우선). DESIGN.md 에서 파생.
        """
        if not design_spec.slides:
            raise ValueError("디자인 스펙에 슬라이드가 없습니다.")

        bg_image_utils.reset_cache()

        prs = Presentation()
        prs.slide_width = PPTX_SLIDE_WIDTH_EMU
        prs.slide_height = PPTX_SLIDE_HEIGHT_EMU
        blank_layout = prs.slide_layouts[6]

        for idx, raw_spec in enumerate(design_spec.slides):
            try:
                spec = clean_slide_spec(raw_spec)
                slide = prs.slides.add_slide(blank_layout)
                self._builder.remove_placeholders(slide)

                if spec.background_color:
                    self._builder.set_slide_background(slide, spec.background_color)

                # 슬라이드별 배경 이미지가 명시되어 있으면 우선 적용 (임포트 라운드트립 보존).
                # 명시가 없을 때만 title/closing 기본 배경 이미지로 폴백한다.
                if spec.background_image_bytes:
                    self._builder.set_slide_background_image(
                        slide, spec.background_image_bytes
                    )
                elif (
                    spec.slide_type in ("title", "closing")
                    and bg_image_policy != "none"
                ):
                    bg_bytes = bg_image_utils.get_bg_image_bytes(color_theme)
                    if bg_bytes:
                        self._builder.set_slide_background_image(slide, bg_bytes)

                self._builder.build_slide_from_spec(slide, spec)
                if not self._builder.has_explicit_z_index(spec):
                    self._builder.ensure_textboxes_on_top(slide)

                if spec.speaker_notes:
                    self._builder.set_speaker_notes(slide, spec.speaker_notes)
            except Exception:
                logger.error(
                    "PPTX export failed at slide[%d/%d] | slide_type=%r "
                    "textboxes=%d shapes=%d images=%d",
                    idx + 1,
                    len(design_spec.slides),
                    raw_spec.slide_type,
                    len(raw_spec.textboxes),
                    len(raw_spec.shapes),
                    len(raw_spec.images),
                    exc_info=True,
                )
                raise

        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="ppt_export_"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "presentation.pptx"
        prs.save(str(output_path))
        logger.info("PPTX 내보내기 완료 (Design Spec): %s", output_path)
        return ExportPptxResponse(pptx_path=str(output_path))
