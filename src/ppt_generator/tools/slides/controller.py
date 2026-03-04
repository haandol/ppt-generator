import json

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.spec_utils import parse_design_spec_json  # inline parameter용
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService


def register_slides_tools(mcp: FastMCP, slides_service: SlidesService, project_service: ProjectService) -> None:
    @mcp.tool()
    def export_html(design_spec_json: str = "", project_id: str = "") -> str:
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
            raise ValueError(
                "Either design_spec_json or project_id must be provided."
            )

        project_id, project_dir = project_service.resolve_project_dir(project_id)

        # 기존 이미지 파일이 있으면 경로 조회
        slide_image_srcs: list[list[str]] = []
        for idx, slide in enumerate(design_spec.slides):
            if slide.images:
                srcs = project_service.get_slide_image_srcs(
                    project_dir, idx, len(slide.images),
                )
                slide_image_srcs.append(srcs)
            else:
                slide_image_srcs.append([])

        response = slides_service.generate_from_design_spec(
            design_spec, slide_image_srcs=slide_image_srcs,
        )
        project_service.save_slides_html(
            project_dir, response.session_id, response.slide_htmls, response.container_html,
        )
        project_service.update_step(project_dir, "slides")

        return json.dumps(
            {
                "session_id": response.session_id,
                "slides_html_path": str(project_dir / "slides.html"),
                "slide_count": len(response.slide_htmls),
                "project_id": project_id,
            },
            ensure_ascii=False,
        )
