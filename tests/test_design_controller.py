"""design controller 테스트: modify_design_spec, generate_design_spec 반환값 검증."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    DesignSpecRequest,
    DesignSpecResponse,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import design_spec_to_json  # noqa: F401 — 하위 호환 확인용
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.project.service import ProjectService


def _make_slide_spec(title: str = "테스트") -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=[
            PptxTextBox(
                left_px=40, top_px=40, width_px=600, height_px=60,
                paragraphs=[
                    PptxParagraph(runs=[PptxTextRun(text=title, font_size_pt=32, bold=True)]),
                ],
            ),
        ],
        shapes=[],
        images=[],
        speaker_notes="",
    )


def _make_design_spec(n: int = 3) -> DesignSpec:
    return DesignSpec(slides=[_make_slide_spec(f"슬라이드 {i+1}") for i in range(n)])


SAMPLE_OUTLINE_JSON = json.dumps(
    {"slides": [{"title": "새 슬라이드", "content_summary": "내용", "component_hint": "bullets", "speaker_notes": ""}]},
    ensure_ascii=False,
)


@pytest.fixture()
def project_service() -> ProjectService:
    return ProjectService()


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "test_project"
    d.mkdir()
    meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
    (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return d


@pytest.fixture()
def project_with_design_spec(project_service: ProjectService, project_dir: Path) -> tuple[str, Path]:
    spec = _make_design_spec(3)
    project_service.save_design_spec(project_dir, spec)
    return project_dir.name, project_dir


@pytest.fixture()
def mcp_tools(project_service: ProjectService) -> dict:
    """MCP 도구를 등록하고 도구 함수들을 반환한다."""
    mcp = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func
        return decorator

    mcp.tool = tool_decorator

    design_service = MagicMock()
    design_service.generate.return_value = DesignSpecResponse(design_spec=_make_design_spec(3))
    design_service.generate_single_slide.return_value = _make_slide_spec("새로 생성됨")
    design_service._extract_design_summary.return_value = "어두운 배경, 밝은 텍스트"

    register_design_tools(mcp, design_service, project_service)
    tools["_design_service"] = design_service
    tools["_project_service"] = project_service
    return tools


class TestGenerateDesignSpecReturn:
    """generate_design_spec 반환값에 design_spec_json이 없어야 한다."""

    def test_no_inline_json_in_return(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        # project.json이 있어야 update_step이 동작
        proj_dir = tmp_path / "test-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )

        result = json.loads(mcp_tools["generate_design_spec"](
            outline_json=SAMPLE_OUTLINE_JSON,
            project_id="test-proj",
        ))
        assert "design_spec_json" not in result
        assert "design_spec_dir" in result
        assert "slide_count" in result
        assert "project_id" in result


class TestModifyDesignSpec:
    """modify_design_spec 도구 테스트."""

    def test_add_slide_at_end(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        # tmp_path 아래에 프로젝트 디렉토리 심볼릭 링크 또는 복사
        # resolve_project_dir가 PPT_GENERATOR_HOME / project_id 를 반환하므로 monkeypatch
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="add",
            slide_index=-1,
            outline_json=SAMPLE_OUTLINE_JSON,
        ))
        assert result["slide_count"] == 4
        assert result["project_id"] == project_id

    def test_add_slide_at_index(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="add",
            slide_index=1,
            outline_json=SAMPLE_OUTLINE_JSON,
        ))
        assert result["slide_count"] == 4

    def test_update_slide(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="update",
            slide_index=0,
            outline_json=SAMPLE_OUTLINE_JSON,
        ))
        assert result["slide_count"] == 3  # 슬라이드 수 변경 없음

    def test_delete_slide(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="delete",
            slide_index=1,
        ))
        assert result["slide_count"] == 2

    def test_invalid_action_raises(self, mcp_tools: dict) -> None:
        with pytest.raises(ValueError, match="action은"):
            mcp_tools["modify_design_spec"](
                project_id="any",
                action="invalid",
            )

    def test_delete_invalid_index_raises(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        with pytest.raises(ValueError, match="유효하지 않은 slide_index"):
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=99,
            )

    def test_add_without_outline_raises(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        with pytest.raises(ValueError, match="outline_json이 필수"):
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
            )


class TestGenerateSlideDesignSpec:
    """generate_slide_design_spec 도구 테스트."""

    def _setup_project(self, tmp_path: Path, monkeypatch) -> str:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        proj_dir = tmp_path / "slide-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return "slide-proj"

    def test_first_slide_creates_design_summary(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(mcp_tools["generate_slide_design_spec"](
            outline_json=SAMPLE_OUTLINE_JSON,
            slide_index=0,
            total_slides=5,
            project_id=project_id,
        ))

        assert result["slide_index"] == 0
        assert result["total_slides"] == 5
        assert result["slide_count"] == 1
        assert result["project_id"] == project_id
        assert result["slide_file"] == "slide_01.json"

        # design_summary.txt가 생성되었는지 확인
        summary_path = tmp_path / project_id / "design_spec" / "design_summary.txt"
        assert summary_path.exists()

    def test_subsequent_slide_loads_design_summary(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        # 첫 슬라이드 생성
        mcp_tools["generate_slide_design_spec"](
            outline_json=SAMPLE_OUTLINE_JSON,
            slide_index=0,
            total_slides=3,
            project_id=project_id,
        )

        # 두 번째 슬라이드 생성
        result = json.loads(mcp_tools["generate_slide_design_spec"](
            outline_json=SAMPLE_OUTLINE_JSON,
            slide_index=1,
            total_slides=3,
            project_id=project_id,
        ))

        assert result["slide_index"] == 1
        assert result["slide_count"] == 2
        assert result["slide_file"] == "slide_02.json"

        # design_service.generate_single_slide가 design_summary와 함께 호출되었는지 확인
        design_service = mcp_tools["_design_service"]
        last_call = design_service.generate_single_slide.call_args
        assert last_call.kwargs.get("design_summary") or last_call[1].get("design_summary") or (len(last_call[0]) > 1 and last_call[0][1])

    def test_return_structure(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(mcp_tools["generate_slide_design_spec"](
            outline_json=SAMPLE_OUTLINE_JSON,
            slide_index=0,
            total_slides=10,
            project_id=project_id,
        ))

        assert "design_spec_dir" in result
        assert "slide_file" in result
        assert "slide_index" in result
        assert "slide_count" in result
        assert "total_slides" in result
        assert "project_id" in result

    def test_auto_generates_project_id(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        result = json.loads(mcp_tools["generate_slide_design_spec"](
            outline_json=SAMPLE_OUTLINE_JSON,
            slide_index=0,
            total_slides=1,
        ))

        assert result["project_id"]
        assert len(result["project_id"]) == 36  # UUID
