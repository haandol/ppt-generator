import logging

from mcp.server.fastmcp import FastMCP

from ppt_generator.di.container import DIContainer
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.outline.controller import register_outline_tools
from ppt_generator.tools.pptx.controller import register_pptx_tools
from ppt_generator.tools.pptx_import.controller import register_pptx_import_tools
from ppt_generator.tools.project.controller import register_project_tools
from ppt_generator.tools.slides.controller import register_slides_tools
from ppt_generator.tools.visual_qa.controller import register_visual_qa_tools

logger = logging.getLogger(__name__)


def create_server() -> FastMCP:
    mcp = FastMCP(
        "ppt-generator",
        instructions=(
            "## LLM Offloading — prepare/ingest handshake\n"
            "This server does NOT call an LLM. Each generation step is split into a "
            "`prepare_*` tool (returns the system/user prompt + a `response_schema`) "
            "and an `ingest_*` tool (validates + post-processes + saves the JSON YOU, "
            "the client, generate). Workflow for a new deck:\n"
            "1. prepare_outline → generate outline JSON (matching response_schema) → ingest_outline.\n"
            "   Then show the outline to the user and get confirmation.\n"
            "2. prepare_design_doc_draft → generate DESIGN.md draft JSON → ingest_design_doc_draft "
            '(call ONCE; skip if it returns {"skip": true}).\n'
            "3. For EACH slide (parallelize): prepare_design_slide → generate spec JSON "
            "(matching response_schema) → ingest_design_slide.\n"
            "4. finalize_design_spec once, then export_html and share slides_html_path.\n"
            "## Rules\n"
            "- Always generate JSON that conforms to the `response_schema` returned by prepare_*.\n"
            '- **Adding a slide**: prepare_slide_edit(action="add") → generate → ingest_slide_edit.\n'
            '- **Updating a slide**: prepare_slide_edit(action="update") → generate → ingest_slide_edit.\n'
            "- **Narrow single-element edit**: prepare_modify_component → generate → ingest_modify_component "
            '(imported slides return stage="backfill" first: generate → ingest_backfill → retry).\n'
            "- **Moving/deleting**: move_slide / delete_slide are pure file ops (no generation).\n"
            "- **Review**: prepare_review → generate → ingest_review (report-only; regenerate via prepare_slide_edit).\n"
            "- **Visual QA** (opt-in, needs the `visual-qa` dependency group + Chromium): capture_slides → "
            "prepare_visual_qa_analysis → generate → ingest_visual_qa_analysis → (if issues) "
            "prepare_visual_qa_fix → generate → ingest_visual_qa_fix → finalize_visual_qa.\n"
            "- After any add/update/modify/finalize, call export_html and share slides_html_path.\n"
            "- Imported projects have no outline: pass title/content_summary inline to prepare_slide_edit.\n"
        ),
    )
    container = DIContainer()
    register_outline_tools(mcp, container.outline_service, container.project_service)
    register_design_tools(
        mcp,
        container.project_service,
        design_service=container.design_service,
        slides_service=container.slides_service,
        review_service=container.review_service,
    )
    register_pptx_tools(mcp, container.export_service, container.project_service)
    register_pptx_import_tools(
        mcp,
        container.import_service,
        container.project_service,
        container.slides_service,
    )
    register_slides_tools(mcp, container.slides_service, container.project_service)
    register_project_tools(mcp, container.project_service)
    register_visual_qa_tools(
        mcp,
        container.project_service,
        visual_qa_service=container.visual_qa_service,
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

        # 서버 전역 로그 (MCP stdio 통신 에러 등 진단용)
        server_log = os.path.join(log_dir, "_server.log")
        os.makedirs(log_dir, exist_ok=True)
        sfh = RotatingFileHandler(
            server_log,
            maxBytes=10 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        sfh.setLevel(logging.DEBUG)
        sfh.setFormatter(logging.Formatter(fmt))
        logging.getLogger().addHandler(sfh)
        # MCP/FastMCP 라이브러리 내부 로그도 캡처
        for lib_logger_name in ("mcp", "fastmcp"):
            lib_logger = logging.getLogger(lib_logger_name)
            lib_logger.setLevel(logging.DEBUG)
            lib_logger.addHandler(sfh)
    elif log_file:
        fh = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt))
        logging.getLogger().addHandler(fh)

    try:
        mcp = create_server()
        logger.info("MCP server starting (stdio transport)...")
        mcp.run(transport="stdio")
        logger.info("MCP server exited normally (mcp.run returned).")
    except KeyboardInterrupt:
        logger.info("MCP server interrupted (KeyboardInterrupt).")
    except BrokenPipeError:
        logger.warning("MCP server: client closed stdio pipe (BrokenPipeError).")
    except Exception:
        logger.exception("MCP server crashed unexpectedly")


if __name__ == "__main__":
    main()
