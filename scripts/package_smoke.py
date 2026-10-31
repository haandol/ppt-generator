"""소스 체크아웃 대신 실제 wheel에서 프롬프트·MCP·두 렌더러를 검사한다."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import zipfile
from pathlib import Path


def extract_wheel(wheel: Path, directory: Path) -> Path:
    """정규화한 출력 경계 안으로만 wheel 파일을 추출한다."""
    root = directory.resolve()
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            target = (root / name).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"Invalid wheel member: {name}")
        archive.extractall(root)
    return root


def smoke(wheel: Path) -> None:
    """독립 디렉토리에 wheel을 풀어 패키지 누락과 소스 경로 의존을 검사한다."""
    with tempfile.TemporaryDirectory(prefix="ppt-package-") as directory:
        root = extract_wheel(wheel, Path(directory))
        sys.path.insert(0, str(root))
        import ppt_generator
        from ppt_generator.interfaces.schemas import DesignSpec, SlideOutline
        from ppt_generator.server import create_server
        from ppt_generator.tools.design.service import DesignService
        from ppt_generator.tools.pptx.service import ExportService
        from ppt_generator.tools.slides.service import SlidesService

        assert Path(ppt_generator.__file__).is_relative_to(root)
        tools = asyncio.run(create_server().list_tools())
        assert {"prepare_outline", "ingest_outline", "export_html", "export_pptx"} <= {
            tool.name for tool in tools
        }
        design = DesignService()
        task = design.prepare_slide(
            SlideOutline(title="Package", content_summary="Smoke", slide_type="title")
        )
        assert task["response_schema"] and task["system_prompt"] and task["user_prompt"]
        spec, _ = design.ingest_slide(
            {
                "textboxes": [
                    {
                        "component_id": "title.main",
                        "left_px": 64,
                        "top_px": 200,
                        "width_px": 1000,
                        "height_px": 120,
                        "paragraphs": [
                            {"runs": [{"text": "Package smoke", "font_size_pt": 32}]}
                        ],
                    }
                ]
            },
            slide_type="title",
        )
        deck = DesignSpec([spec])
        html = SlidesService().generate_from_design_spec(deck, bg_image_policy="none")
        assert "Package smoke" in html.slide_htmls[0]
        pptx = ExportService().export_from_design_spec(
            deck, root / "export", bg_image_policy="none"
        )
        assert Path(pptx.pptx_path).is_file()
        print(f"Wheel smoke passed: {len(tools)} MCP tools; prompts, HTML, PPTX")


if __name__ == "__main__":
    smoke(Path(sys.argv[1]).resolve())
