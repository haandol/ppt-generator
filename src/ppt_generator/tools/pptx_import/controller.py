"""PPTX 임포트 MCP tool 등록."""

import json
from dataclasses import replace

from mcp.server.fastmcp import FastMCP

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxSlideSpec,
    ProjectMetadata,
)
from ppt_generator.interfaces.spec_utils.contrast_utils import (
    _hex_to_relative_luminance,
)
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.pptx_import.service import ImportService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService


def run_import_pptx(
    file_path: str,
    project_id: str,
    import_service: ImportService,
    project_service: ProjectService,
    slides_service: SlidesService,
) -> dict:
    """PPTX 임포트 → 프로젝트 저장 → HTML 생성의 전체 흐름 (MCP 래퍼와 분리).

    MCP tool 클로저와 검증/테스트가 동일 코드 경로를 재사용하도록 모듈 레벨로 분리했다.

    Returns:
        {project_id, num_slides, slides_html_path, warnings?} dict.
    """
    project_id, project_dir = project_service.resolve_project_dir(project_id)

    design_spec, warnings = import_service.import_from_file(file_path)

    # 메타데이터 저장
    metadata = ProjectMetadata(
        topic=f"Imported from {file_path.split('/')[-1] if '/' in file_path else file_path}",
        num_slides=len(design_spec.slides),
        source="imported",
    )
    project_service.save_metadata(project_dir, metadata)
    project_service.update_step(project_dir, "import")
    project_service.update_step(project_dir, "design_spec")

    # 이미지 파일 저장 (image_bytes → PNG) 및 src 설정
    slide_image_srcs: list[list[str]] = []
    updated_slides: list[PptxSlideSpec] = []
    for idx, slide in enumerate(design_spec.slides):
        srcs = project_service.save_slide_images(project_dir, idx, slide.images)
        slide_image_srcs.append(srcs)
        # 각 이미지에 src 경로 설정
        new_images = [
            replace(img, src=src) if src else img
            for img, src in zip(slide.images, srcs)
        ]
        # 배경 이미지 저장
        bg_src = project_service.save_slide_bg_image(
            project_dir, idx, slide.background_image_bytes
        )
        updated_slides.append(
            replace(
                slide,
                images=new_images,
                background_image_src=bg_src,
                background_image_bytes=b"",
            )
        )
    design_spec = DesignSpec(slides=updated_slides)
    # src가 포함된 design_spec 재저장
    project_service.save_design_spec(project_dir, design_spec)

    # 기존 슬라이드에서 design_summary 추출 (테마 일관성 유지용)
    ref_slide = next(
        (s for s in design_spec.slides if s.slide_type == "content"),
        design_spec.slides[1]
        if len(design_spec.slides) >= 2
        else design_spec.slides[0],
    )
    design_summary = DesignService.extract_design_summary(ref_slide)
    bg_color = design_summary.get("background_color")
    design_summary["color_theme"] = (
        "light" if bg_color and _hex_to_relative_luminance(bg_color) >= 0.5 else "dark"
    )
    project_service.save_design_summary(project_dir, design_summary)

    # DESIGN.md 초안 자동 생성 — imported 프로젝트도 디자인 의도를
    # 사람이 편집할 수 있게 한다.
    from ppt_generator.tools.design.design_doc_md import render_design_doc_md

    project_service.save_design_doc_md(
        project_dir, render_design_doc_md(design_summary)
    )

    # HTML 미리보기 자동 생성
    response = slides_service.generate_from_design_spec(
        design_spec,
        slide_image_srcs=slide_image_srcs,
        skip_autofit=True,
        color_theme=design_summary["color_theme"],
        bg_image_policy=project_service.load_bg_image_policy(project_dir),
    )
    project_service.save_slides_html(
        project_dir,
        response.session_id,
        response.slide_htmls,
        response.container_html,
    )
    project_service.update_step(project_dir, "slides")

    result = {
        "project_id": project_id,
        "num_slides": len(design_spec.slides),
        "slides_html_path": str(project_dir / "slides.html"),
    }
    if warnings:
        result["warnings"] = warnings

    return result


def register_pptx_import_tools(
    mcp: FastMCP,
    import_service: ImportService,
    project_service: ProjectService,
    slides_service: SlidesService,
) -> None:
    @mcp.tool()
    def import_pptx(file_path: str, project_id: str = "") -> str:
        """Imports an external PPTX file and converts it to a design spec for editing.

        Reads the PPTX file, extracts all design elements (shapes, textboxes, images,
        backgrounds, speaker notes), and creates a new project with the design spec.
        HTML preview is automatically generated.

        After import, you can use prepare_slide_edit / ingest_slide_edit,
        prepare_modify_component / ingest_modify_component, export_html, export_pptx,
        and the visual QA tools on the imported project.

        Args:
            file_path: Absolute path to the PPTX file to import
            project_id: Project ID (auto-generated if not specified)

        Returns:
            JSON string containing project_id, num_slides, slides_html_path, and warnings
        """
        result = run_import_pptx(
            file_path,
            project_id,
            import_service,
            project_service,
            slides_service,
        )
        return json.dumps(result, ensure_ascii=False)
