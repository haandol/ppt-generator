import json
import logging
import time

from mcp.server.fastmcp import Context, FastMCP

from ppt_generator.interfaces import bg_image_utils
from ppt_generator.interfaces.spec_utils import (
    parse_design_spec_json,
)  # inline parameter용
from ppt_generator.interfaces.spec_utils.lint import lint_design_spec
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


def register_slides_tools(
    mcp: FastMCP, slides_service: SlidesService, project_service: ProjectService
) -> None:
    @mcp.tool()
    async def export_html(
        design_spec_json: str = "", project_id: str = "", ctx: Context | None = None
    ) -> str:
        """Generates per-slide HTML files and an iframe container based on the design spec.

        Operates in two modes:
        1. When design_spec_json is provided: Deterministically converts design spec to HTML (no LLM, fast and accurate)
        2. When only project_id is provided: Auto-loads design spec from project directory for HTML conversion (recommended)

        Each slide is generated as slides/slide_NN.html, and slides.html is the iframe container.

        Args:
            design_spec_json: Design spec JSON string
            project_id: Project ID (auto-generated if not specified). When provided alone, auto-loads the design spec

        Returns:
            JSON string containing session_id, slides_html_path, slide_count, project_id
        """
        if design_spec_json:
            design_spec = parse_design_spec_json(design_spec_json)
        elif project_id:
            _, proj_dir = project_service.resolve_project_dir(project_id)
            design_spec = project_service.load_design_spec(proj_dir)
        else:
            raise ValueError("Either design_spec_json or project_id must be provided.")

        project_id, project_dir = project_service.resolve_project_dir(project_id)

        # 배경 이미지 선택을 프로젝트 단위로 고정 — PPTX export 와 같은 시드를
        # 써서 미리보기(HTML)와 최종본(PPTX)의 title/closing 배경이 일치한다.
        bg_image_utils.set_project_seed(project_id)

        # image_path → slides/images/ 동기화
        design_spec = project_service.sync_image_paths(project_dir, design_spec)

        # 기존 이미지 파일이 있으면 경로 조회
        slide_image_srcs: list[list[str]] = []
        for idx, slide in enumerate(design_spec.slides):
            if slide.images:
                srcs = project_service.get_slide_image_srcs(
                    project_dir,
                    idx,
                    len(slide.images),
                )
                slide_image_srcs.append(srcs)
            else:
                slide_image_srcs.append([])

        # imported 프로젝트는 autofit 건너뛰기 (원본 크기 보존)
        metadata = project_service.load_metadata(project_dir)
        is_imported = "import" in metadata.steps_completed

        # design_summary에서 color_theme 로드
        design_summary = project_service.load_design_summary(project_dir)
        color_theme = (design_summary or {}).get("color_theme", "dark")
        bg_image_policy = project_service.load_bg_image_policy(project_dir)

        slide_count = len(design_spec.slides)
        if ctx is not None:
            await ctx.report_progress(0, 1, "HTML 내보내기 중...")
        logger.info("HTML export 시작 (slides=%d)", slide_count)
        t0 = time.monotonic()
        response = slides_service.generate_from_design_spec(
            design_spec,
            slide_image_srcs=slide_image_srcs,
            skip_autofit=is_imported,
            color_theme=color_theme,
            bg_image_policy=bg_image_policy,
        )
        project_service.save_slides_html(
            project_dir,
            response.session_id,
            response.slide_htmls,
            response.container_html,
        )
        project_service.update_step(project_dir, "slides")
        elapsed = time.monotonic() - t0
        logger.info("HTML export 완료 (%.1fs, slides=%d)", elapsed, slide_count)
        if ctx is not None:
            await ctx.report_progress(1, 1, "HTML 내보내기 완료")

        # export 시점 lint — 사용자가 design_spec JSON 을 직접 편집한 뒤
        # export_html 만 호출하는 경로에서도 위반이 드러나도록 한다.
        # 단계적 검증 (layout → section → cross → content) 으로 거시
        # 위반이 미시 노이즈에 가려지지 않게 한다.
        lint_result = lint_design_spec(
            list(design_spec.slides), stop_on_layer_error=True
        )

        result: dict = {
            "session_id": response.session_id,
            "slides_html_path": str(project_dir / "slides.html"),
            "slide_count": len(response.slide_htmls),
            "project_id": project_id,
        }
        if lint_result.has_violations:
            result["lint"] = lint_result.to_dict()
            result["lint_suggestion"] = (
                f"{lint_result.to_dict()['failed_slides']}개 슬라이드에서 "
                f"총 {lint_result.total_violations}건의 lint 위반이 발견되었습니다. "
                "위반 내용을 확인하고 수정 여부를 결정하세요."
            )

        return json.dumps(result, ensure_ascii=False)
