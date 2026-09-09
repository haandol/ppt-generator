"""실제 stdio MCP 연결로 준비·수신·QA·내보내기 계약을 검사한다.

클라이언트 생성 JSON은 고정 fixture이며 모델의 생성 품질을 평가하는 테스트는 아니다.
서버 프로젝트와 PPTX/HTML은 임시 디렉토리에만 만들고 실행 후 제거한다.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pptx import Presentation

from design.test_context_preservation import _payload
from design.test_release_regressions import draft, outline


def test_real_stdio_generation_qa_and_exports(tmp_path: Path) -> None:
    """문맥을 왕복하고 오래된 분석을 거부한 뒤 두 출력이 생성되는지 확인한다."""

    async def exercise(home: Path) -> None:
        bootstrap = (
            "import sys; from pathlib import Path; "
            "import ppt_generator.tools.project.service as p; "
            "p.PPT_GENERATOR_HOME = Path(sys.argv[1]); "
            "from ppt_generator.server import main; main()"
        )
        params = StdioServerParameters(
            command=sys.executable, args=["-c", bootstrap, str(home)]
        )
        with (tmp_path / "server.log").open("w") as log:
            async with stdio_client(params, errlog=log) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()

                    async def call(name: str, **args) -> dict:
                        """실제 도구 오류를 성공으로 취급하지 않고 JSON 응답을 읽는다."""
                        result = await session.call_tool(name, args)
                        assert not result.isError, result.content
                        return json.loads(
                            "".join(
                                item.text
                                for item in result.content
                                if item.type == "text"
                            )
                        )

                    prepared = await call(
                        "prepare_outline", topic="Contract smoke", num_slides=4
                    )
                    pid = prepared["project_id"]
                    await call(
                        "ingest_outline",
                        project_id=pid,
                        outline_json=json.dumps(outline()),
                    )
                    await call("prepare_design_doc_draft", project_id=pid)
                    intent = draft()
                    intent["theme"]["background_image"] = "none"
                    await call(
                        "ingest_design_doc_draft",
                        project_id=pid,
                        draft_json=json.dumps(intent),
                    )
                    for index in range(1, 5):
                        task = await call(
                            "prepare_design_slide", project_id=pid, slide_index=index
                        )
                        spec = _payload()
                        if task["slide_type"] != "content":
                            textbox = dict(spec["textboxes"][0])
                            textbox.pop("grid_cell", None)
                            textbox["component_id"] = (
                                "title.main"
                                if task["slide_type"] == "title"
                                else "closing.message"
                            )
                            spec = {"textboxes": [textbox]}
                        await call(
                            "ingest_design_slide",
                            project_id=pid,
                            slide_index=index,
                            spec_json=json.dumps(spec),
                            generation_context=task["generation_context"],
                        )
                    finished = await call("finalize_design_spec", project_id=pid)
                    assert finished["slide_count"] == 4

                    screenshot = tmp_path / "fixture.png"
                    screenshot.write_bytes(
                        base64.b64decode(
                            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2dzsAAAAASUVORK5CYII="
                        )
                    )
                    task = await call(
                        "prepare_visual_qa_analysis",
                        project_id=pid,
                        slide_index=3,
                        screenshot_path=str(screenshot),
                    )
                    analysis_json = json.dumps(
                        {
                            "has_issues": True,
                            "overall_quality": "needs_improvement",
                            "issues": [
                                {
                                    "issue_type": "misalignment",
                                    "severity": "medium",
                                    "element_type": "textbox",
                                    "element_index": 0,
                                    "description": "Fixture: align the statement",
                                    "suggested_fix": "Move to x=96",
                                }
                            ],
                        }
                    )
                    analyzed = await call(
                        "ingest_visual_qa_analysis",
                        project_id=pid,
                        slide_index=3,
                        analysis_json=analysis_json,
                        prepared_context=task["prepared_context"],
                    )
                    fix = await call(
                        "prepare_visual_qa_fix",
                        project_id=pid,
                        slide_index=3,
                        analysis_context=analyzed["analysis_context"],
                    )
                    fixed = await call(
                        "ingest_visual_qa_fix",
                        project_id=pid,
                        slide_index=3,
                        fix_context=fix["fix_context"],
                        fix_json=json.dumps(
                            {
                                "operations": [
                                    {
                                        "element_type": "textbox",
                                        "element_index": 0,
                                        "field": "left_px",
                                        "value": 96,
                                    }
                                ]
                            }
                        ),
                    )
                    assert fixed["status"] == "fixed"
                    stale = await session.call_tool(
                        "ingest_visual_qa_analysis",
                        {
                            "project_id": pid,
                            "slide_index": 3,
                            "analysis_json": analysis_json,
                            "prepared_context": task["prepared_context"],
                        },
                    )
                    assert stale.isError
                    assert "Stale" in str(stale.content)
                    html = await call("export_html", project_id=pid)
                    pptx = await call("export_pptx", project_id=pid)
                    assert Path(html["slides_html_path"]).is_file()
                    assert len(Presentation(pptx["pptx_path"]).slides) == 4

    with tempfile.TemporaryDirectory(dir=tmp_path) as directory:
        asyncio.run(exercise(Path(directory)))
