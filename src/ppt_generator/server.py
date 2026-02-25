import logging

from mcp.server.fastmcp import FastMCP

from ppt_generator.di.container import DIContainer
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.outline.controller import register_outline_tools
from ppt_generator.tools.pptx.controller import register_pptx_tools
from ppt_generator.tools.project.controller import register_project_tools
from ppt_generator.tools.script.controller import register_script_tools
from ppt_generator.tools.slides.controller import register_slides_tools

logger = logging.getLogger(__name__)


def create_server() -> FastMCP:
    mcp = FastMCP(
        "ppt-generator",
        instructions=(
            "## 필수 워크플로우 규칙\n"
            "- generate_slides_design_spec 또는 modify_design_spec 호출 후에는 "
            "**반드시** export_html(project_id=...)를 호출하여 HTML을 내보내세요.\n"
            "- export_html가 반환하는 slides_html_path를 사용자에게 안내하세요.\n"
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
    register_slides_tools(mcp, container.slides_service, container.project_service)
    register_project_tools(mcp, container.project_service)
    return mcp


def main() -> None:
    fmt = "%(asctime)s %(name)s %(levelname)s %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt)

    # 파일 로그 (디버깅용) — 환경변수 PPT_LOG_FILE 로 경로 지정
    import os

    log_file = os.environ.get("PPT_LOG_FILE")
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt))
        logging.getLogger().addHandler(fh)
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
