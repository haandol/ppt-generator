"""slides controller 테스트: project_id 기반 자동 로드 검증."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
    SlidesResponse,
)
from ppt_generator.interfaces.spec_utils import design_spec_to_json
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.controller import register_slides_tools


def _make_design_spec() -> DesignSpec:
    return DesignSpec(slides=[
        PptxSlideSpec(
            background_color="#1a1a2e",
            textboxes=[
                PptxTextBox(
                    left_px=40, top_px=40, width_px=600, height_px=60,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="제목", font_size_pt=32)])],
                ),
            ],
        ),
    ])


@pytest.fixture()
def slides_service() -> MagicMock:
    svc = MagicMock()
    svc._sessions = {}
    svc.generate_from_design_spec.return_value = SlidesResponse(session_id="sess-1", html="<html></html>")
    svc.generate.return_value = SlidesResponse(session_id="sess-2", html="<html></html>")
    return svc


@pytest.fixture()
def project_service(slides_service: MagicMock) -> ProjectService:
    return ProjectService(slides_service=slides_service)


@pytest.fixture()
def mcp_tools(slides_service: MagicMock, project_service: ProjectService) -> dict:
    mcp = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func
        return decorator

    mcp.tool = tool_decorator
    register_slides_tools(mcp, slides_service, project_service)
    tools["_slides_service"] = slides_service
    return tools


class TestGenerateSlidesProjectId:
    """project_id만 제공 시 디자인 스펙 자동 로드 검증."""

    def test_auto_load_design_spec(self, mcp_tools: dict, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        # 프로젝트 디렉토리에 디자인 스펙 저장
        proj_dir = tmp_path / "proj-1"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        spec = _make_design_spec()
        project_service.save_design_spec(proj_dir, design_spec_to_json(spec))

        result = json.loads(mcp_tools["generate_slides"](project_id="proj-1"))
        assert result["session_id"] == "sess-1"
        assert result["project_id"] == "proj-1"
        mcp_tools["_slides_service"].generate_from_design_spec.assert_called_once()

    def test_fallback_to_outline_when_no_design_spec(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        proj_dir = tmp_path / "proj-2"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        # 디자인 스펙 없이 outline_json 함께 제공
        outline = json.dumps(
            {"slides": [{"title": "제목", "content_summary": "내용", "component_hint": "bullets", "speaker_notes": ""}]},
            ensure_ascii=False,
        )
        result = json.loads(mcp_tools["generate_slides"](project_id="proj-2", outline_json=outline))
        assert result["session_id"] == "sess-2"
        mcp_tools["_slides_service"].generate.assert_called_once()

    def test_error_when_no_design_spec_no_outline(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        proj_dir = tmp_path / "proj-3"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="디자인 스펙이 없고"):
            mcp_tools["generate_slides"](project_id="proj-3")

    def test_error_when_nothing_provided(self, mcp_tools: dict) -> None:
        with pytest.raises(ValueError, match="중 하나를 제공해야"):
            mcp_tools["generate_slides"]()
