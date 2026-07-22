"""수정된 코드로 PPTX 를 임포트해 프로젝트+HTML 을 생성한다 (MCP 서버 우회).

import_pptx MCP tool 과 동일한 컨트롤러 로직을 venv 파이썬으로 직접 실행하므로,
MCP 서버 재시작 없이 최신 소스로 결과물을 만들 수 있다. 생성 후 capture_slides
(Playwright)로 스크린샷을 찍어 원본과 비교하는 루프에 사용한다.

사용법:
    uv run python scripts/rebuild_import.py "<원본.pptx>" <project_id>
"""

from __future__ import annotations

import logging
import sys
from dataclasses import replace

from ppt_generator.di.container import DIContainer
from ppt_generator.interfaces.schemas import DesignSpec, ProjectMetadata
from ppt_generator.interfaces.spec_utils.contrast_utils import (
    _hex_to_relative_luminance,
)
from ppt_generator.tools.design.design_doc_md import render_design_doc_md
from ppt_generator.tools.design.service import DesignService

logging.disable(logging.CRITICAL)


def rebuild(file_path: str, project_id: str) -> str:
    c = DIContainer()
    import_service = c.import_service
    project_service = c.project_service
    slides_service = c.slides_service

    project_id, project_dir = project_service.resolve_project_dir(project_id)
    design_spec, _ = import_service.import_from_file(file_path)
    project_service.save_metadata(
        project_dir,
        ProjectMetadata(
            topic="rebuild", num_slides=len(design_spec.slides), source="imported"
        ),
    )
    project_service.update_step(project_dir, "import")
    project_service.update_step(project_dir, "design_spec")

    slide_image_srcs = []
    updated = []
    for idx, slide in enumerate(design_spec.slides):
        srcs = project_service.save_slide_images(project_dir, idx, slide.images)
        slide_image_srcs.append(srcs)
        new_images = [replace(i, src=s) if s else i for i, s in zip(slide.images, srcs)]
        bg_src = project_service.save_slide_bg_image(
            project_dir, idx, slide.background_image_bytes
        )
        updated.append(
            replace(
                slide,
                images=new_images,
                background_image_src=bg_src,
                background_image_bytes=b"",
            )
        )
    design_spec = DesignSpec(slides=updated)
    project_service.save_design_spec(project_dir, design_spec)

    ref = next(
        (s for s in design_spec.slides if s.slide_type == "content"),
        design_spec.slides[1]
        if len(design_spec.slides) >= 2
        else design_spec.slides[0],
    )
    dsum = DesignService.extract_design_summary(ref)
    bg = dsum.get("background_color")
    dsum["color_theme"] = (
        "light" if bg and _hex_to_relative_luminance(bg) >= 0.5 else "dark"
    )
    project_service.save_design_summary(project_dir, dsum)
    project_service.save_design_doc_md(project_dir, render_design_doc_md(dsum))

    resp = slides_service.generate_from_design_spec(
        design_spec,
        slide_image_srcs=slide_image_srcs,
        skip_autofit=True,
        color_theme=dsum["color_theme"],
        bg_image_policy=project_service.load_bg_image_policy(project_dir),
    )
    project_service.save_slides_html(
        project_dir, resp.session_id, resp.slide_htmls, resp.container_html
    )
    project_service.update_step(project_dir, "slides")
    return str(project_dir)


if __name__ == "__main__":
    path = rebuild(sys.argv[1], sys.argv[2])
    print(path)
