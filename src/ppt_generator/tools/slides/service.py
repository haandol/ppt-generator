from __future__ import annotations

import logging
import uuid

from ppt_generator.interfaces.constants import (
    SLIDE_TEMPLATE_PATH,
    SLIDES_CONTAINER_TEMPLATE_PATH,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxSlideSpec,
    SlidesResponse,
)
from ppt_generator.interfaces import bg_image_utils
from ppt_generator.interfaces.spec_utils import validate_slide_spec
from ppt_generator.tools.slides.html_renderer import spec_to_html_section

logger = logging.getLogger(__name__)


class SlidesService:
    def __init__(self) -> None:
        self._sessions: dict[str, str] = {}

    def generate_from_design_spec(
        self,
        design_spec: DesignSpec,
        *,
        slide_image_srcs: list[list[str]] | None = None,
        skip_autofit: bool = False,
        color_theme: str = "dark",
    ) -> SlidesResponse:
        """DesignSpec(PptxSlideSpec 리스트)을 슬라이드별 HTML + iframe 컨테이너로 변환한다.

        LLM 호출 없이 PptxSlideSpec -> position:absolute HTML div로 변환.
        각 슬라이드는 완전한 HTML 문서로 생성되며, 컨테이너는 iframe으로 참조.

        Args:
            slide_image_srcs: 슬라이드별 이미지 상대경로 리스트. None이면 플레이스홀더.
            color_theme: 배경 이미지 선택에 사용할 테마 ("dark" 또는 "light")
        """
        if not design_spec.slides:
            raise ValueError("디자인 스펙에 슬라이드가 없습니다.")

        bg_image_utils.reset_cache()

        slide_htmls: list[str] = []
        for idx, raw_spec in enumerate(design_spec.slides):
            spec = validate_slide_spec(raw_spec, autofit=not skip_autofit)
            bg_b64: str | None = None
            if spec.slide_type in ("title", "closing"):
                bg_b64 = bg_image_utils.get_bg_image_base64(color_theme)
            img_srcs = slide_image_srcs[idx] if slide_image_srcs and idx < len(slide_image_srcs) else None
            slide_html = self._spec_to_html_document(
                idx, spec, bg_image_base64=bg_b64, image_srcs=img_srcs,
            )
            slide_htmls.append(slide_html)

        container_html = self._build_container_html(len(slide_htmls))

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = container_html

        logger.info(
            "Design Spec -> HTML 변환 완료: session_id=%s, 슬라이드 수=%d",
            session_id, len(design_spec.slides),
        )
        return SlidesResponse(
            session_id=session_id,
            slide_htmls=slide_htmls,
            container_html=container_html,
        )

    @staticmethod
    def render_single_slide_html(
        slide_index: int,
        spec: PptxSlideSpec,
        *,
        image_srcs: list[str] | None = None,
        skip_autofit: bool = False,
        color_theme: str = "dark",
    ) -> str:
        """단일 PptxSlideSpec을 완전한 HTML 문서로 변환한다 (외부 호출용).

        title/closing 슬라이드의 배경 이미지를 자동 처리한다.
        """
        bg_image_utils.reset_cache()
        validated = validate_slide_spec(spec, autofit=not skip_autofit)
        bg_b64: str | None = None
        if validated.slide_type in ("title", "closing"):
            bg_b64 = bg_image_utils.get_bg_image_base64(color_theme)
        return SlidesService._spec_to_html_document(
            slide_index, validated,
            bg_image_base64=bg_b64,
            image_srcs=image_srcs,
        )

    @staticmethod
    def _spec_to_html_document(
        slide_index: int,
        spec: PptxSlideSpec,
        *,
        bg_image_base64: str | None = None,
        image_srcs: list[str] | None = None,
    ) -> str:
        """PptxSlideSpec 하나를 완전한 HTML 문서로 변환."""
        section_html = spec_to_html_section(
            slide_index, spec,
            bg_image_base64=bg_image_base64,
            image_srcs=image_srcs,
        )
        template = SLIDE_TEMPLATE_PATH.read_text(encoding="utf-8")
        return template.replace("{slide_content}", section_html)

    @staticmethod
    def _build_container_html(slide_count: int) -> str:
        """iframe 컨테이너 HTML을 생성한다."""
        parts: list[str] = []
        for i in range(slide_count):
            filename = f"slide_{i + 1:02d}.html"
            parts.append(
                f'<div class="slide-wrapper">\n'
                f'    <div class="slide-number">{i + 1} / {slide_count}</div>\n'
                f'    <iframe src="slides/{filename}"></iframe>\n'
                f'</div>'
            )
        content = "\n".join(parts)
        template = SLIDES_CONTAINER_TEMPLATE_PATH.read_text(encoding="utf-8")
        return template.replace("{slides_content}", content)

    def get_session_html(self, session_id: str) -> str:
        html = self._sessions.get(session_id)
        if html is None:
            raise KeyError(f"세션을 찾을 수 없습니다: {session_id}")
        return html
