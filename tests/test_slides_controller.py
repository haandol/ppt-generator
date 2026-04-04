"""slides controller 테스트: design_spec_json 및 project_id 기반 검증."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import (
    SlidesResponse,
)
from ppt_generator.interfaces.spec_utils import (
    design_spec_to_json,  # noqa: F401 — inline parameter 테스트용
)
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.controller import register_slides_tools

from conftest import make_design_spec as _make_design_spec


@pytest.fixture()
def slides_service() -> MagicMock:
    svc = MagicMock()
    svc._sessions = {}
    svc.generate_from_design_spec.return_value = SlidesResponse(
        session_id="sess-1",
        slide_htmls=["<html>slide1</html>"],
        container_html="<html>container</html>",
    )
    return svc


@pytest.fixture()
def project_service() -> ProjectService:
    return ProjectService()


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


class TestExportHtmlProjectId:
    """project_id만 제공 시 디자인 스펙 자동 로드 검증."""

    def test_auto_load_design_spec(
        self,
        mcp_tools: dict,
        project_service: ProjectService,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        # 프로젝트 디렉토리에 디자인 스펙 저장
        proj_dir = tmp_path / "proj-1"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps(
                {"topic": "", "num_slides": 0, "steps_completed": {}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        spec = _make_design_spec(1)
        project_service.save_design_spec(proj_dir, spec)

        result = json.loads(mcp_tools["export_html"](project_id="proj-1"))
        assert result["session_id"] == "sess-1"
        assert result["project_id"] == "proj-1"
        assert result["slide_count"] == 1
        mcp_tools["_slides_service"].generate_from_design_spec.assert_called_once()

    def test_slides_dir_created(
        self,
        mcp_tools: dict,
        project_service: ProjectService,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        proj_dir = tmp_path / "proj-3"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps(
                {"topic": "", "num_slides": 0, "steps_completed": {}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        spec = _make_design_spec(1)
        project_service.save_design_spec(proj_dir, spec)

        mcp_tools["export_html"](project_id="proj-3")

        # slides/ 디렉토리와 개별 슬라이드 HTML 확인
        slides_dir = proj_dir / "slides"
        assert slides_dir.exists()
        assert (slides_dir / "slide_01.html").exists()
        # 컨테이너 HTML 확인
        assert (proj_dir / "slides.html").exists()

    def test_error_when_no_design_spec(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        proj_dir = tmp_path / "proj-2"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps(
                {"topic": "", "num_slides": 0, "steps_completed": {}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with pytest.raises(FileNotFoundError):
            mcp_tools["export_html"](project_id="proj-2")

    def test_error_when_nothing_provided(self, mcp_tools: dict) -> None:
        with pytest.raises(ValueError, match="Either design_spec_json or project_id"):
            mcp_tools["export_html"]()
