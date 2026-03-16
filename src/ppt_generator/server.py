import logging

from mcp.server.fastmcp import FastMCP

from ppt_generator.di.container import DIContainer
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.outline.controller import register_outline_tools
from ppt_generator.tools.pptx.controller import register_pptx_tools
from ppt_generator.tools.pptx_import.controller import register_pptx_import_tools
from ppt_generator.tools.project.controller import register_project_tools
from ppt_generator.tools.script.controller import register_script_tools
from ppt_generator.tools.slides.controller import register_slides_tools
from ppt_generator.tools.visual_qa.controller import register_visual_qa_tools

logger = logging.getLogger(__name__)


def create_server() -> FastMCP:
    mcp = FastMCP(
        "ppt-generator",
        instructions=(
            "## Required Workflow Rules\n"
            "- After calling generate_slides_design_spec or modify_design_spec, "
            "you **must** call export_html(project_id=...) to export HTML.\n"
            "- Share the slides_html_path returned by export_html with the user.\n"
            "- After design spec generation, suggest visual_qa(project_id=...) to the user "
            "for pixel-perfect quality check.\n"
            "- Only run visual_qa when the user agrees. It requires Playwright.\n"
            "- Use import_pptx to import an external PPTX file for editing.\n"
            "- Check the project's `source` field: "
            "\"imported\" projects have no outline/script. "
            "For imported projects, use modify_design_spec directly to add/update slides "
            "(pass title, content_summary, etc. inline). "
            "Or use generate_slides_design_spec with explicit outline_json.\n"
            "- **Adding slides**: Call modify_design_spec(action=\"add\") with "
            "title, content_summary, component_hint, etc. "
            "All file shifts (outline/script/design_spec/HTML) are handled automatically.\n"
            "- **Updating slides**: Call modify_design_spec(action=\"update\") with "
            "title/content_summary to update, or call save_outline_slide first.\n"
            "- **Moving slides**: Call move_slide(project_id, from_index, to_index). "
            "This is a pure file reorder — no LLM call. "
            "After move_slide, call export_html to refresh.\n"
        ),
    )
    container = DIContainer()
    register_script_tools(mcp, container.script_service, container.project_service)
    register_outline_tools(mcp, container.outline_service, container.project_service)
    register_design_tools(
        mcp, container.project_service,
        design_service_factory=container.create_design_service,
        slides_service=container.slides_service,
    )
    register_pptx_tools(mcp, container.export_service, container.project_service)
    register_pptx_import_tools(
        mcp, container.import_service, container.project_service, container.slides_service,
    )
    register_slides_tools(mcp, container.slides_service, container.project_service)
    register_project_tools(mcp, container.project_service)
    register_visual_qa_tools(
        mcp, container.project_service,
        visual_qa_service_factory=container.create_visual_qa_service,
        slides_service=container.slides_service,
    )
    return mcp


def main() -> None:
    fmt = "%(asctime)s %(name)s %(levelname)s %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt)

    # File logging (for debugging)
    # PPT_LOG_DIR: directory for per-project log files (e.g. /tmp/ppt-generator/)
    # PPT_LOG_FILE: single log file path (legacy, e.g. /tmp/ppt-generator.log)
    import os
    from logging.handlers import RotatingFileHandler

    log_dir = os.environ.get("PPT_LOG_DIR")
    log_file = os.environ.get("PPT_LOG_FILE")

    # PPT_LOG_DIR → 프로젝트별 동적 핸들러 (ProjectService에서 처리)
    if log_dir:
        import ppt_generator.tools.project.service as ps
        ps._log_dir = log_dir
        ps._log_fmt = fmt
    elif log_file:
        fh = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=2, encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt))
        logging.getLogger().addHandler(fh)
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
