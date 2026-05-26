"""pptx controller 테스트: design_spec_json 및 project_id 기반 자동 로드 검증."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import (
    ExportPptxResponse,
)
from ppt_generator.interfaces.spec_utils import (
    design_spec_to_json,  # noqa: F401 — inline parameter 테스트용
)
from ppt_generator.tools.pptx.controller import register_pptx_tools
from ppt_generator.tools.project.service import ProjectService

from _helpers import make_design_spec as _make_design_spec


@pytest.fixture()
def project_service() -> ProjectService:
    return ProjectService()


@pytest.fixture()
def export_service() -> MagicMock:
    svc = MagicMock()
    svc.export_from_design_spec.return_value = ExportPptxResponse(
        pptx_path="/tmp/output.pptx"
    )
    return svc


@pytest.fixture()
def mcp_tools(export_service: MagicMock, project_service: ProjectService) -> dict:
    mcp = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator
    register_pptx_tools(mcp, export_service, project_service)
    tools["_export_service"] = export_service
    return tools


class TestExportPptxProjectId:
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

        result = json.loads(mcp_tools["export_pptx"](project_id="proj-1"))
        assert result["project_id"] == "proj-1"
        assert result["pptx_path"] == "/tmp/output.pptx"
        mcp_tools["_export_service"].export_from_design_spec.assert_called_once()

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
        with pytest.raises(ValueError, match="Either provide design_spec_json"):
            mcp_tools["export_pptx"](project_id="proj-2")

    def test_error_when_nothing_provided(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        with pytest.raises(ValueError, match="Either provide design_spec_json"):
            mcp_tools["export_pptx"]()
