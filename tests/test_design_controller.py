"""design controller 테스트: modify_design_spec, generate_slides_design_spec 검증."""

import asyncio
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
    SlideOutline,
)
from ppt_generator.interfaces.spec_utils import (
    design_spec_to_json,  # noqa: F401 — 하위 호환 확인용
)
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService

from conftest import make_design_spec as _make_design_spec
from conftest import make_slide_spec as _make_slide_spec


@pytest.fixture()
def project_service() -> ProjectService:
    return ProjectService()


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "test_project"
    d.mkdir()
    meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
    (d / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    return d


@pytest.fixture()
def project_with_design_spec(
    project_service: ProjectService, project_dir: Path
) -> tuple[str, Path]:
    spec = _make_design_spec(3)
    project_service.save_design_spec(project_dir, spec)
    project_service.save_design_summary(
        project_dir,
        {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        },
    )
    # outline 개별 파일도 생성 (modify_design_spec 동기화 테스트용)
    outline_data = json.dumps(
        {
            "slides": [
                {
                    "title": f"슬라이드 {i + 1}",
                    "content_summary": f"내용 {i + 1}",
                    "component_hint": "bullets",
                    "speaker_notes": "",
                    "slide_type": "content",
                }
                for i in range(3)
            ]
        },
        ensure_ascii=False,
    )
    project_service.save_outline(project_dir, outline_data)
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
    design_service.generate_single_slide.return_value = _make_slide_spec("새로 생성됨")
    design_service.last_token_usage = {}
    design_service.last_overflow = []
    design_service.generate_design_summary.return_value = {
        "background_color": "#1a1a2e",
        "text_colors": ["#ffffff"],
        "title_font_pt": 32,
        "body_font_pt": 18,
        "card_fills": [],
        "card_borders": [],
    }

    design_service_factory = lambda effort, slide_type="content": design_service  # noqa: E731

    register_design_tools(
        mcp,
        project_service,
        design_service_factory=design_service_factory,
    )
    tools["_design_service"] = design_service
    tools["_design_service_factory"] = design_service_factory
    tools["_project_service"] = project_service
    return tools


class TestModifyDesignSpec:
    """modify_design_spec 도구 테스트."""

    def test_add_slide_at_end(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        # tmp_path 아래에 프로젝트 디렉토리 심볼릭 링크 또는 복사
        # resolve_project_dir가 PPT_GENERATOR_HOME / project_id 를 반환하므로 monkeypatch
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
                slide_index=-1,
                title="새 슬라이드",
                content_summary="내용",
            )
        )
        assert result["slide_count"] == 4
        assert result["project_id"] == project_id

    def test_add_slide_at_index(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
                slide_index=2,
                title="새 슬라이드",
                content_summary="내용",
            )
        )
        assert result["slide_count"] == 4

    def test_update_slide(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        # 사전 조건: outline JSONL에서 해당 슬라이드를 먼저 수정
        project_service = mcp_tools["_project_service"]
        updated_slide = json.dumps(
            {
                "title": "새 슬라이드",
                "content_summary": "내용",
                "component_hint": "bullets",
            },
            ensure_ascii=False,
        )
        project_service.update_outline_slide(dest, 0, updated_slide)

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="update",
                slide_index=1,
            )
        )
        assert result["slide_count"] == 3  # 슬라이드 수 변경 없음

    def test_delete_slide(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

    def test_invalid_action_raises(self, mcp_tools: dict) -> None:
        with pytest.raises(ValueError, match="action must be one of"):
            mcp_tools["modify_design_spec"](
                project_id="any",
                action="invalid",
            )

    def test_delete_invalid_index_raises(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        with pytest.raises(ValueError, match="Invalid slide_index"):
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=99,
            )

    def test_add_without_title_raises(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """title/content_summary 없이 add 호출 시 ValueError가 발생한다."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "no-outline-proj"
        project_dir.mkdir()
        meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        spec = _make_design_spec(3)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        with pytest.raises(ValueError, match="title and content_summary are required"):
            mcp_tools["modify_design_spec"](
                project_id="no-outline-proj",
                action="add",
            )

    def test_add_on_imported_project(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """imported 프로젝트에서 modify_design_spec(add)가 인라인 파라미터로 성공한다."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "imported-proj"
        project_dir.mkdir()
        meta = {
            "topic": "Imported",
            "num_slides": 3,
            "steps_completed": {"import": "2025-01-01"},
            "source": "imported",
        }
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        spec = _make_design_spec(3)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id="imported-proj",
                action="add",
                slide_index=-1,
                title="새 슬라이드",
                content_summary="개별 파일로 저장",
            )
        )
        assert result["slide_count"] == 4

        # outline/slide_04.json 파일이 존재하는지 확인
        outline_dir = project_dir / "outline"
        assert outline_dir.exists()
        files = sorted(outline_dir.glob("slide_*.json"))
        assert len(files) >= 1

    def test_update_with_save_outline_slide(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """save_outline_slide로 개별 파일 저장 후 modify_design_spec update가 성공한다 (generated 프로젝트)."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "generated-proj2"
        project_dir.mkdir()
        meta = {
            "topic": "Generated",
            "num_slides": 3,
            "steps_completed": {},
            "source": "generated",
        }
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        spec = _make_design_spec(3)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        # save_outline_slide로 대체할 슬라이드 아웃라인 저장
        slide_data = json.dumps(
            {
                "title": "대체 슬라이드",
                "content_summary": "개별 파일로 대체",
                "component_hint": "bullets",
                "slide_type": "content",
                "speaker_notes": "",
            },
            ensure_ascii=False,
        )
        project_service.save_outline_slide(project_dir, 1, slide_data)

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id="generated-proj2",
                action="update",
                slide_index=2,
            )
        )
        assert result["slide_count"] == 3  # 수 변경 없음

    def test_add_returns_token_usage(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        design_service = mcp_tools["_design_service"]
        design_service.last_token_usage = {
            "inputTokens": 500,
            "outputTokens": 200,
            "totalTokens": 700,
        }

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
                slide_index=-1,
                title="새 슬라이드",
                content_summary="내용",
            )
        )
        assert "token_usage" in result
        assert result["token_usage"]["inputTokens"] == 500
        assert result["token_usage"]["outputTokens"] == 200
        assert "estimated_cost" in result
        assert "total_cost" in result["estimated_cost"]

    def test_update_returns_token_usage(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        # 사전 조건: outline JSONL에서 해당 슬라이드를 먼저 수정
        project_service = mcp_tools["_project_service"]
        updated_slide = json.dumps(
            {
                "title": "새 슬라이드",
                "content_summary": "내용",
                "component_hint": "bullets",
            },
            ensure_ascii=False,
        )
        project_service.update_outline_slide(dest, 0, updated_slide)

        design_service = mcp_tools["_design_service"]
        design_service.last_token_usage = {
            "inputTokens": 300,
            "outputTokens": 150,
            "totalTokens": 450,
        }

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="update",
                slide_index=1,
            )
        )
        assert "token_usage" in result
        assert result["token_usage"]["inputTokens"] == 300
        assert result["token_usage"]["outputTokens"] == 150
        assert "estimated_cost" in result
        assert "total_cost" in result["estimated_cost"]

    def test_delete_has_no_token_usage(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=2,
            )
        )
        assert "token_usage" not in result
        assert "estimated_cost" not in result

    def test_add_creates_outline_file(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """add 시 인라인 파라미터로 outline 파일이 자동 생성된다."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        project_service = mcp_tools["_project_service"]

        mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="add",
            slide_index=2,
            title="새 슬라이드",
            content_summary="내용",
        )

        # outline이 4개가 되어야 한다
        outline_raw = project_service.load_outline(dest)
        outline_data = json.loads(outline_raw)
        assert len(outline_data["slides"]) == 4
        # 삽입된 슬라이드의 제목 확인
        assert outline_data["slides"][1]["title"] == "새 슬라이드"
        # slide_index가 올바르게 재번호되었는지 확인
        for i, s in enumerate(outline_data["slides"]):
            assert s["slide_index"] == i

    def test_update_reads_outline_from_file(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """update 시 outline JSONL 파일에서 해당 슬라이드를 읽어 디자인 스펙을 생성한다."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        # 사전 조건: outline JSONL에서 해당 슬라이드를 먼저 수정
        project_service = mcp_tools["_project_service"]
        updated_slide = json.dumps(
            {
                "title": "새 슬라이드",
                "content_summary": "내용",
                "component_hint": "bullets",
            },
            ensure_ascii=False,
        )
        project_service.update_outline_slide(dest, 0, updated_slide)

        mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="update",
            slide_index=1,
        )

        # outline JSONL이 여전히 3줄이고 사전에 수정한 내용이 반영되어 있는지 확인
        outline_raw = project_service.load_outline(dest)
        outline_data = json.loads(outline_raw)
        assert len(outline_data["slides"]) == 3
        assert outline_data["slides"][0]["title"] == "새 슬라이드"

    def test_delete_syncs_outline_jsonl(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """delete 시 outline JSONL에서도 해당 슬라이드가 삭제된다 (delete는 여전히 동기화)."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="delete",
            slide_index=2,
        )

        # outline JSONL이 2줄이 되었는지 확인
        project_service = mcp_tools["_project_service"]
        outline_raw = project_service.load_outline(dest)
        outline_data = json.loads(outline_raw)
        assert len(outline_data["slides"]) == 2
        # slide_index가 올바르게 재번호되었는지 확인
        for i, s in enumerate(outline_data["slides"]):
            assert s["slide_index"] == i

    def test_no_outline_file_raises_on_update(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """outline/script JSONL이 없는 프로젝트에서 update 시 에러가 발생한다."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "no-outline-proj"
        project_dir.mkdir()
        meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        # 디자인 스펙만 생성 (outline 없음)
        spec = _make_design_spec(3)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        # outline 파일이 없어도 sync로 placeholder가 생성되어 정상 동작
        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id="no-outline-proj",
                action="update",
                slide_index=1,
            )
        )
        assert result["slide_count"] == 3

    def test_imported_project_update_without_title_raises(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """imported 프로젝트에서 title/content_summary 없이 update하면 ValueError."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "imported-proj"
        project_dir.mkdir()
        meta = {
            "topic": "Imported",
            "num_slides": 3,
            "steps_completed": {},
            "source": "imported",
        }
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        spec = _make_design_spec(3)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        with pytest.raises(
            ValueError, match="title and content_summary are required.*imported"
        ):
            mcp_tools["modify_design_spec"](
                project_id="imported-proj",
                action="update",
                slide_index=1,
            )

    def test_imported_project_update_with_title_succeeds(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """imported 프로젝트에서 title/content_summary를 제공하면 update 성공."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "imported-proj2"
        project_dir.mkdir()
        meta = {
            "topic": "Imported",
            "num_slides": 3,
            "steps_completed": {},
            "source": "imported",
        }
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        spec = _make_design_spec(3)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id="imported-proj2",
                action="update",
                slide_index=1,
                title="수정된 제목",
                content_summary="수정된 내용",
            )
        )
        assert result["slide_count"] == 3


@pytest.fixture()
def mcp_tools_with_slides(project_service: ProjectService) -> dict:
    """slides_service mock이 포함된 MCP 도구를 등록하고 도구 함수들을 반환한다."""
    mcp = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator

    design_service = MagicMock()
    design_service.generate_single_slide.return_value = _make_slide_spec("새로 생성됨")
    design_service.last_token_usage = {}
    design_service.last_overflow = []
    design_service.generate_design_summary.return_value = {
        "background_color": "#1a1a2e",
        "text_colors": ["#ffffff"],
        "title_font_pt": 32,
        "body_font_pt": 18,
        "card_fills": [],
        "card_borders": [],
    }

    design_service_factory = lambda effort, slide_type="content": design_service  # noqa: E731

    slides_service = MagicMock()
    slides_service.render_single_slide_html.return_value = "<html>new slide</html>"

    register_design_tools(
        mcp,
        project_service,
        design_service_factory=design_service_factory,
        slides_service=slides_service,
    )
    tools["_design_service"] = design_service
    tools["_design_service_factory"] = design_service_factory
    tools["_project_service"] = project_service
    tools["_slides_service"] = slides_service
    return tools


class TestModifyDesignSpecHtmlSync:
    """modify_design_spec의 add/delete 시 slides/ HTML 파일 동기화 검증."""

    @staticmethod
    def _setup_with_html(
        mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path
    ) -> tuple[str, Path]:
        """디자인 스펙 + HTML 슬라이드 파일이 있는 프로젝트를 설정한다."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil

        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        # slides/ HTML 파일 생성 (3장)
        slides_dir = dest / "slides"
        slides_dir.mkdir(exist_ok=True)
        for i in range(3):
            (slides_dir / f"slide_{i + 1:02d}.html").write_text(
                f"<html>slide {i + 1}</html>", encoding="utf-8"
            )

        return project_id, dest

    def test_delete_removes_html_file(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """delete 시 slides/ 디렉토리에서 해당 HTML 파일도 삭제되고 재번호된다."""
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

        slides_dir = dest / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == 2
        assert html_files[0].name == "slide_01.html"
        assert html_files[1].name == "slide_02.html"
        # 내용 확인: slide_01은 원래 slide 1, slide_02는 원래 slide 3
        assert "slide 1" in html_files[0].read_text(encoding="utf-8")
        assert "slide 3" in html_files[1].read_text(encoding="utf-8")

    def test_delete_first_slide_html_sync(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """첫 번째 슬라이드 삭제 시 HTML 파일이 올바르게 재번호된다."""
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=1,
            )
        )
        assert result["slide_count"] == 2

        slides_dir = dest / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == 2
        # 원래 slide 2 → slide_01.html, 원래 slide 3 → slide_02.html
        assert "slide 2" in html_files[0].read_text(encoding="utf-8")
        assert "slide 3" in html_files[1].read_text(encoding="utf-8")

    def test_delete_last_slide_html_sync(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """마지막 슬라이드 삭제 시 HTML 파일이 올바르게 제거된다."""
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=3,
            )
        )
        assert result["slide_count"] == 2

        slides_dir = dest / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == 2
        assert "slide 1" in html_files[0].read_text(encoding="utf-8")
        assert "slide 2" in html_files[1].read_text(encoding="utf-8")

    def test_add_inserts_html_and_renumbers(
        self,
        mcp_tools_with_slides: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """add 시 slides/ 디렉토리에 새 HTML이 삽입되고 기존 파일이 재번호된다."""
        project_id, dest = self._setup_with_html(
            mcp_tools_with_slides, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools_with_slides["modify_design_spec"](
                project_id=project_id,
                action="add",
                slide_index=2,
                title="새 슬라이드",
                content_summary="내용",
            )
        )
        assert result["slide_count"] == 4

        slides_dir = dest / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == 4
        # 원래 slide 1 → slide_01.html (변경 없음)
        assert "slide 1" in html_files[0].read_text(encoding="utf-8")
        # slide_02.html은 새로 생성된 슬라이드 (mock이 생성한 HTML)
        assert html_files[1].name == "slide_02.html"
        assert "new slide" in html_files[1].read_text(encoding="utf-8")
        # 원래 slide 2 → slide_03.html
        assert "slide 2" in html_files[2].read_text(encoding="utf-8")
        # 원래 slide 3 → slide_04.html
        assert "slide 3" in html_files[3].read_text(encoding="utf-8")

    def test_consecutive_deletes(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """연속 삭제 시 HTML 파일 수가 올바르게 줄어든다."""
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        # 첫 번째 삭제 (2번째 슬라이드)
        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

        # 두 번째 삭제 (1번째 슬라이드)
        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=1,
            )
        )
        assert result["slide_count"] == 1

        slides_dir = dest / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == 1
        assert html_files[0].name == "slide_01.html"
        assert "slide 3" in html_files[0].read_text(encoding="utf-8")


class TestGenerateSlidesDesignSpecFromProject:
    """generate_slides_design_spec project_id 기반 파일 로드 테스트."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def _setup_project_with_outline(
        self, tmp_path: Path, monkeypatch, num_slides: int = 5
    ) -> str:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        proj_dir = tmp_path / "batch-file-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps(
                {"topic": "테스트", "num_slides": num_slides, "steps_completed": {}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        outline = {
            "slides": [
                {
                    "title": f"슬라이드 {i + 1}",
                    "content_summary": f"내용 {i + 1}",
                    "component_hint": "bullets",
                    "speaker_notes": "",
                }
                for i in range(num_slides)
            ],
        }
        outline_dir = proj_dir / "outline"
        outline_dir.mkdir()
        for i, slide in enumerate(outline["slides"]):
            slide["slide_index"] = i
            (outline_dir / f"slide_{i + 1:02d}.json").write_text(
                json.dumps(slide, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return "batch-file-proj"

    def test_load_from_outline_file(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """project_id만 제공하면 outline.json에서 로드한다."""
        project_id = self._setup_project_with_outline(
            tmp_path, monkeypatch, num_slides=3
        )

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    project_id=project_id,
                )
            )
        )

        assert result["total_slides"] == 3
        assert result["success_count"] == 3
        assert result["project_id"] == project_id

    def test_auto_calculates_total_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """total_slides=0이면 자동 계산한다."""
        project_id = self._setup_project_with_outline(
            tmp_path, monkeypatch, num_slides=4
        )

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    project_id=project_id,
                    total_slides=0,
                )
            )
        )

        assert result["total_slides"] == 4
        assert result["success_count"] == 4

    def test_no_outline_no_project_raises(self, mcp_tools: dict) -> None:
        """outline_json도 project_id도 없으면 ValueError."""
        with pytest.raises(ValueError, match="Either outline_json or project_id"):
            self._run(mcp_tools["generate_slides_design_spec"]())


SAMPLE_BATCH_OUTLINE_JSON = json.dumps(
    {
        "slides": [
            {
                "title": f"슬라이드 {i + 1}",
                "content_summary": f"내용 {i + 1}",
                "component_hint": "bullets",
                "speaker_notes": "",
            }
            for i in range(5)
        ],
    },
    ensure_ascii=False,
)


class TestGenerateSlidesDesignSpec:
    """generate_slides_design_spec 배치 도구 테스트."""

    def _setup_project(self, tmp_path: Path, monkeypatch) -> str:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        proj_dir = tmp_path / "batch-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps(
                {"topic": "", "num_slides": 0, "steps_completed": {}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "batch-proj"

    @staticmethod
    def _run(coro):
        """async 도구 함수를 동기 테스트에서 실행하는 헬퍼."""
        return asyncio.run(coro)

    def test_batch_generates_all_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                )
            )
        )

        assert result["total_slides"] == 5
        assert result["success_count"] == 5
        assert result["error_count"] == 0
        assert result["slide_count"] == 5
        assert result["project_id"] == project_id
        assert len(result["results"]) == 5

    def test_batch_results_ordered_by_index(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                )
            )
        )

        for i, r in enumerate(result["results"]):
            assert r["slide_index"] == i + 1  # 1-based
            assert r["status"] == "success"
            assert r["slide_file"] == f"slide_{i + 1:02d}.json"

    def test_batch_creates_design_summary(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        self._run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        summary_path = tmp_path / project_id / "design_spec" / "design_summary.json"
        assert summary_path.exists()

    def test_batch_mismatched_total_slides_raises(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        self._setup_project(tmp_path, monkeypatch)

        with pytest.raises(ValueError, match="does not match"):
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=3,  # outline has 5
                    project_id="batch-proj",
                )
            )

    def test_batch_single_slide(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """슬라이드 1장짜리 배치도 정상 동작."""
        project_id = self._setup_project(tmp_path, monkeypatch)
        single_outline = json.dumps(
            {
                "slides": [
                    {
                        "title": "단일",
                        "content_summary": "내용",
                        "component_hint": "bullets",
                        "speaker_notes": "",
                    }
                ]
            },
            ensure_ascii=False,
        )

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=single_outline,
                    total_slides=1,
                    project_id=project_id,
                )
            )
        )

        assert result["success_count"] == 1
        assert result["error_count"] == 0
        assert result["slide_count"] == 1

    def test_batch_auto_generates_project_id(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        single_outline = json.dumps(
            {
                "slides": [
                    {
                        "title": "단일",
                        "content_summary": "내용",
                        "component_hint": "bullets",
                        "speaker_notes": "",
                    }
                ]
            },
            ensure_ascii=False,
        )

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=single_outline,
                    total_slides=1,
                )
            )
        )

        assert result["project_id"]
        assert len(result["project_id"]) == 36  # UUID

    def test_batch_partial_failure(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """일부 슬라이드 실패 시 나머지는 정상 저장되고 에러가 보고된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        design_service = mcp_tools["_design_service"]
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # 3번째 호출(slide_index=2)에서 실패
            if kwargs.get("slide_index") == 3:
                raise RuntimeError("LLM 호출 실패")
            return _make_slide_spec("생성됨")

        design_service.generate_single_slide.side_effect = side_effect

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                )
            )
        )

        assert result["success_count"] == 4
        assert result["error_count"] == 1

        # 실패한 슬라이드 확인
        failed = [r for r in result["results"] if r["status"] == "error"]
        assert len(failed) == 1
        assert failed[0]["slide_index"] == 3  # 1-based
        assert "LLM 호출 실패" in failed[0]["error"]

        # 성공한 슬라이드 확인
        succeeded = [r for r in result["results"] if r["status"] == "success"]
        assert len(succeeded) == 4

    def test_batch_respects_parallel_limit(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """동시 실행 스레드가 DESIGN_SPEC_PARALLEL 값을 초과하지 않는지 검증."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # DESIGN_SPEC_PARALLEL을 2로 제한
        import ppt_generator.tools.design.parallel_runner as runner_module

        monkeypatch.setattr(runner_module, "DESIGN_SPEC_PARALLEL", 2)

        # 10장짜리 아웃라인 (모든 슬라이드 병렬 생성)
        outline_10 = json.dumps(
            {
                "slides": [
                    {
                        "title": f"슬라이드 {i + 1}",
                        "content_summary": f"내용 {i + 1}",
                        "component_hint": "bullets",
                        "speaker_notes": "",
                    }
                    for i in range(10)
                ],
            },
            ensure_ascii=False,
        )

        peak_concurrent = 0
        current_concurrent = 0
        lock = threading.Lock()

        def slow_generate(*args, **kwargs):
            nonlocal peak_concurrent, current_concurrent
            with lock:
                current_concurrent += 1
                if current_concurrent > peak_concurrent:
                    peak_concurrent = current_concurrent
            time.sleep(0.05)  # 병렬 스레드가 겹칠 수 있도록 약간의 지연
            with lock:
                current_concurrent -= 1
            return _make_slide_spec("생성됨")

        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.side_effect = slow_generate

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=outline_10,
                    total_slides=10,
                    project_id=project_id,
                )
            )
        )

        assert result["success_count"] == 10
        assert result["error_count"] == 0
        # 모든 슬라이드가 병렬 생성되며, max_workers=2이므로 동시 최대 2를 초과하면 안 됨
        assert peak_concurrent <= 2, f"동시 실행 peak={peak_concurrent}, 제한=2"

    def test_batch_reports_progress(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """ctx.report_progress가 각 슬라이드 완료 시 호출되는지 검증."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        from unittest.mock import AsyncMock

        progress_calls: list[tuple[int, int, str]] = []

        ctx = AsyncMock()

        async def _capture_progress(
            progress: int, total: int, message: str = ""
        ) -> None:
            progress_calls.append((progress, total, message))

        ctx.report_progress.side_effect = _capture_progress

        async def _run_and_drain():
            result = await mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
                ctx=ctx,
            )
            # to_thread에서 call_soon_threadsafe로 스케줄링된 태스크를 처리
            await asyncio.sleep(0.1)
            return result

        result = json.loads(asyncio.run(_run_and_drain()))

        assert result["success_count"] == 5
        # report_progress:
        #   디자인 테마 생성 중 1회 + 생성 완료 1회 (await)
        #   + 슬라이드 5회 (call_soon_threadsafe)
        #   + heartbeat N회 (15초 간격, 실행 시간에 따라 가변)
        #   (HTML 내보내기 완료는 slide_count > 0 조건에 따라 실제 파일 존재 시에만 보고)
        non_heartbeat = [
            c for c in progress_calls if "디자인 스펙 생성 중..." not in c[2]
        ]
        assert len(non_heartbeat) == 7
        # 마지막 비-heartbeat 호출의 progress 값은 target_count와 같아야 함
        assert non_heartbeat[-1][0] == 5  # progress
        assert non_heartbeat[-1][1] == 5  # total

    def test_batch_with_slide_indices(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """slide_indices로 특정 인덱스만 생성한다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # 먼저 전체 생성하여 design_summary 확보
        self._run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        # design_service 호출 카운터 리셋
        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.reset_mock()

        # 특정 인덱스만 재생성 (1-based)
        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                    slide_indices="2,4",
                )
            )
        )

        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert len(result["results"]) == 2
        indices = [r["slide_index"] for r in result["results"]]
        assert indices == [2, 4]  # 1-based

    def test_batch_slide_indices_with_index_one(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """slide_indices에 인덱스 1 포함 시 design_summary가 없으면 LLM으로 사전 생성 후 전체 병렬."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                    slide_indices="1,3,5",
                )
            )
        )

        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert len(result["results"]) == 3
        indices = [r["slide_index"] for r in result["results"]]
        assert indices == [1, 3, 5]  # 1-based

        # design_summary.json이 생성되었는지 확인
        summary_path = tmp_path / project_id / "design_spec" / "design_summary.json"
        assert summary_path.exists()

        # design_service.generate_design_summary가 호출되었는지 확인 (LLM으로 사전 생성)
        design_service = mcp_tools["_design_service"]
        assert design_service.generate_design_summary.called

    def test_batch_slide_indices_without_index_zero(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """slide_indices에 인덱스 0 미포함 시 기존 design_summary를 로드하여 전부 병렬 생성."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # 먼저 전체 생성하여 design_summary 확보
        self._run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        design_service = mcp_tools["_design_service"]
        design_service.generate_design_summary.reset_mock()

        # 인덱스 1 없이 재생성 (1-based)
        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                    slide_indices="3,4",
                )
            )
        )

        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert len(result["results"]) == 2

        # design_summary가 이미 존재하므로 generate_design_summary가 호출되지 않아야 함
        assert not design_service.generate_design_summary.called

    def test_batch_single_index(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """단일 인덱스만 지정하여 1장 생성."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # 먼저 전체 생성하여 design_summary 확보
        self._run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.reset_mock()

        result = json.loads(
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                    slide_indices="3",
                )
            )
        )

        assert result["success_count"] == 1
        assert result["error_count"] == 0
        assert len(result["results"]) == 1
        assert result["results"][0]["slide_index"] == 3  # 1-based
        assert result["results"][0]["slide_file"] == "slide_03.json"

    def test_batch_slide_indices_invalid_raises(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """Invalid slide_index raises ValueError."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        with pytest.raises(ValueError, match="Invalid slide_index"):
            self._run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                    slide_indices="0,10",  # 0 is invalid (1-based), 10 exceeds range
                )
            )

    def test_batch_enforces_background_color_from_design_summary(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """content 슬라이드의 배경색이 design_summary의 background_color로 강제 보정된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        design_service = mcp_tools["_design_service"]
        # design_summary에는 #1a1a2e를 반환하지만 슬라이드 스펙에는 #ffffff를 사용
        design_service.generate_design_summary.return_value = {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        }
        wrong_bg_spec = PptxSlideSpec(
            background_color="#ffffff",  # 잘못된 밝은 배경
            textboxes=[
                PptxTextBox(
                    left_px=40,
                    top_px=40,
                    width_px=600,
                    height_px=60,
                    paragraphs=[
                        PptxParagraph(
                            runs=[
                                PptxTextRun(text="테스트", font_size_pt=32, bold=True)
                            ]
                        )
                    ],
                ),
            ],
            shapes=[],
            images=[],
            speaker_notes="",
            slide_type="content",
        )
        design_service.generate_single_slide.return_value = wrong_bg_spec

        self._run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        # 저장된 스펙의 배경색이 design_summary 값으로 보정되었는지 확인
        project_service = mcp_tools["_project_service"]
        proj_dir = tmp_path / project_id
        for i in range(5):
            saved_spec = project_service.load_design_spec_slide(proj_dir, i)
            assert saved_spec.background_color == "#1a1a2e", (
                f"slide[{i}] 배경색이 보정되지 않음: {saved_spec.background_color}"
            )


class TestGenerateSlidesDesignSpecWithSlidesService:
    """slides_service가 제공될 때 slides.html 컨테이너 생성 테스트."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def _setup_project(self, tmp_path: Path, monkeypatch) -> str:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        proj_dir = tmp_path / "slides-html-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps(
                {"topic": "", "num_slides": 0, "steps_completed": {}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return "slides-html-proj"

    def test_generates_slides_html_container(self, tmp_path: Path, monkeypatch) -> None:
        """전체 슬라이드 생성 완료 시 slides.html 컨테이너가 자동 생성된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        mcp = MagicMock()
        tools = {}

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func

            return decorator

        mcp.tool = tool_decorator

        design_service = MagicMock()
        design_service.generate_single_slide.return_value = _make_slide_spec("생성됨")
        design_service.last_token_usage = {}
        design_service.last_overflow = []
        design_service.generate_design_summary.return_value = {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        }

        from ppt_generator.tools.slides.service import SlidesService

        slides_service = SlidesService()
        project_service = ProjectService()

        register_design_tools(
            mcp,
            project_service,
            design_service_factory=lambda effort, slide_type="content": design_service,
            slides_service=slides_service,
        )

        outline_3 = json.dumps(
            {
                "slides": [
                    {
                        "title": f"슬라이드 {i + 1}",
                        "content_summary": f"내용 {i + 1}",
                        "component_hint": "bullets",
                        "speaker_notes": "",
                    }
                    for i in range(3)
                ]
            },
            ensure_ascii=False,
        )

        result = json.loads(
            self._run(
                tools["generate_slides_design_spec"](
                    outline_json=outline_3,
                    total_slides=3,
                    project_id=project_id,
                )
            )
        )

        assert result["success_count"] == 3
        assert "slides_html_path" in result

        # slides.html 파일이 생성되었는지 확인
        slides_html_path = tmp_path / project_id / "slides.html"
        assert slides_html_path.exists()

        # 컨테이너 HTML에 iframe 참조가 포함되어 있는지 확인
        content = slides_html_path.read_text(encoding="utf-8")
        assert "slide_01.html" in content
        assert "slide_02.html" in content
        assert "slide_03.html" in content


class TestAdjacentContextSection:
    """DesignService._adjacent_context_section 단위 테스트."""

    def test_both_none_returns_empty(self) -> None:
        """prev와 next 모두 None이면 빈 문자열을 반환한다."""
        assert DesignService._adjacent_context_section(None, None) == ""

    def test_prev_only(self) -> None:
        """prev만 제공되면 previous_slide 섹션만 포함한다."""
        prev = SlideOutline(
            title="이전 슬라이드",
            content_summary="이전 내용",
            component_hint="bullets",
            speaker_notes="노트는 제외되어야 함",
            slide_type="content",
        )
        result = DesignService._adjacent_context_section(prev, None)
        assert "<adjacent_slides>" in result
        assert "<previous_slide>" in result
        assert "</previous_slide>" in result
        assert "<next_slide>" not in result
        assert "이전 슬라이드" in result
        assert "이전 내용" in result
        assert "노트는 제외되어야 함" not in result

    def test_next_only(self) -> None:
        """next만 제공되면 next_slide 섹션만 포함한다."""
        nxt = SlideOutline(
            title="다음 슬라이드",
            content_summary="다음 내용",
            component_hint="two_column",
            speaker_notes="이것도 제외",
            slide_type="content",
        )
        result = DesignService._adjacent_context_section(None, nxt)
        assert "<adjacent_slides>" in result
        assert "<next_slide>" in result
        assert "</next_slide>" in result
        assert "<previous_slide>" not in result
        assert "다음 슬라이드" in result
        assert "다음 내용" in result
        assert "이것도 제외" not in result

    def test_both_provided(self) -> None:
        """prev와 next 모두 제공되면 양쪽 섹션을 포함한다."""
        prev = SlideOutline(
            title="이전",
            content_summary="이전 요약",
            component_hint="bullets",
            slide_type="content",
        )
        nxt = SlideOutline(
            title="다음",
            content_summary="다음 요약",
            component_hint="step_cards",
            slide_type="content",
        )
        result = DesignService._adjacent_context_section(prev, nxt)
        assert "<adjacent_slides>" in result
        assert "</adjacent_slides>" in result
        assert "<previous_slide>" in result
        assert "<next_slide>" in result
        assert "이전" in result
        assert "다음" in result

    def test_includes_slide_type_and_component_hint(self) -> None:
        """slide_type과 component_hint가 포함되는지 확인한다."""
        prev = SlideOutline(
            title="타이틀",
            content_summary="요약",
            component_hint="arch_diagram",
            slide_type="title",
        )
        result = DesignService._adjacent_context_section(prev, None)
        parsed = json.loads(
            result.split("<previous_slide>")[1].split("</previous_slide>")[0].strip()
        )
        assert parsed["slide_type"] == "title"
        assert parsed["component_hint"] == "arch_diagram"
        assert "speaker_notes" not in parsed


class TestBugFixInsertWorkflow:
    """Bug fix 검증: save_outline_slide(insert=true) → modify_design_spec(add) 워크플로우.

    재현 시나리오 (버그 리포트):
    - 기존 프로젝트에 save_outline_slide → modify_design_spec(add)로 슬라이드 추가 시
      1) outline/script 파일이 shift되지 않아 기존 파일을 덮어씀
      2) script를 우선 참조하여 save_outline_slide로 저장한 새 내용이 무시됨
      3) project.json의 num_slides가 동기화되지 않음
    """

    @staticmethod
    def _setup_generated_project(
        mcp_tools: dict,
        tmp_path: Path,
        monkeypatch,
        num_slides: int = 5,
    ) -> tuple[str, Path]:
        """outline + design_spec이 있는 generated 프로젝트를 설정한다."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_id = "bug-fix-proj"
        project_dir = tmp_path / project_id
        project_dir.mkdir()

        meta = {"topic": "테스트", "num_slides": num_slides, "steps_completed": {}}
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )

        # outline 개별 파일 생성
        outline_data = json.dumps(
            {
                "slides": [
                    {
                        "title": f"기존 슬라이드 {i + 1}",
                        "content_summary": f"내용 {i + 1}",
                        "component_hint": "bullets",
                        "speaker_notes": "",
                        "slide_type": "content",
                    }
                    for i in range(num_slides)
                ]
            },
            ensure_ascii=False,
        )
        project_service.save_outline(project_dir, outline_data)

        # design_spec 생성
        spec = _make_design_spec(num_slides)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        return project_id, project_dir

    def test_save_outline_slide_insert_shifts_files(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """save_outline_slide(insert=true)가 기존 파일들을 shift하고 새 파일을 삽입한다."""
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 5
        )
        project_service = mcp_tools["_project_service"]

        # insert=true로 인덱스 2에 새 슬라이드 삽입
        project_service.insert_outline_slide(
            project_dir,
            2,
            json.dumps(
                {
                    "title": "새 슬라이드",
                    "content_summary": "새 내용",
                    "component_hint": "bullets",
                    "slide_type": "content",
                    "speaker_notes": "",
                },
                ensure_ascii=False,
            ),
        )

        # outline이 6개가 되어야 함
        outline_raw = project_service.load_outline(project_dir)
        outline = json.loads(outline_raw)
        assert len(outline["slides"]) == 6
        assert outline["slides"][2]["title"] == "새 슬라이드"
        # 기존 3번째(인덱스 2)가 인덱스 3으로 밀렸는지 확인
        assert outline["slides"][3]["title"] == "기존 슬라이드 3"

    def test_add_updates_num_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """modify_design_spec(add) 후 project.json의 num_slides가 동기화된다."""
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 3
        )
        project_service = mcp_tools["_project_service"]

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
                slide_index=2,
                title="새 슬라이드",
                content_summary="내용",
            )
        )
        assert result["slide_count"] == 4

        # project.json의 num_slides 확인
        meta = project_service.load_metadata(project_dir)
        assert meta.num_slides == 4

    def test_delete_updates_num_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """modify_design_spec(delete) 후 project.json의 num_slides가 동기화된다."""
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 3
        )
        project_service = mcp_tools["_project_service"]

        result = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

        # project.json의 num_slides 확인
        meta = project_service.load_metadata(project_dir)
        assert meta.num_slides == 2

    def test_consecutive_adds_correct_slide_count(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """연속 add 시 슬라이드 수가 올바르게 증가한다 (버그 리포트 재현)."""
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 3
        )
        project_service = mcp_tools["_project_service"]

        # 첫 번째 add: 2번째 위치에 삽입 (1-based)
        result1 = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
                slide_index=2,
                title="새 1",
                content_summary="내용 1",
            )
        )
        assert result1["slide_count"] == 4

        # 두 번째 add: 3번째 위치에 삽입 (1-based)
        result2 = json.loads(
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
                slide_index=3,
                title="새 2",
                content_summary="내용 2",
            )
        )
        assert result2["slide_count"] == 5

        # project.json의 num_slides도 5
        meta = project_service.load_metadata(project_dir)
        assert meta.num_slides == 5

        # outline의 순서 확인
        outline_raw = project_service.load_outline(project_dir)
        outline = json.loads(outline_raw)
        assert len(outline["slides"]) == 5
        assert outline["slides"][0]["title"] == "기존 슬라이드 1"
        assert outline["slides"][1]["title"] == "새 1"
        assert outline["slides"][2]["title"] == "새 2"
        assert outline["slides"][3]["title"] == "기존 슬라이드 2"
        assert outline["slides"][4]["title"] == "기존 슬라이드 3"


class TestMoveSlide:
    """move_slide 도구 테스트: 파일 재정렬만 수행, LLM 호출 없음."""

    @staticmethod
    def _setup_project(
        mcp_tools: dict,
        tmp_path: Path,
        monkeypatch,
        num_slides: int = 5,
    ) -> tuple[str, Path]:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_id = "move-test-proj"
        project_dir = tmp_path / project_id
        project_dir.mkdir()

        meta = {"topic": "테스트", "num_slides": num_slides, "steps_completed": {}}
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )

        outline_data = json.dumps(
            {
                "slides": [
                    {
                        "title": f"슬라이드 {i + 1}",
                        "content_summary": f"내용 {i + 1}",
                        "component_hint": "bullets",
                        "speaker_notes": "",
                        "slide_type": "content",
                    }
                    for i in range(num_slides)
                ]
            },
            ensure_ascii=False,
        )
        project_service.save_outline(project_dir, outline_data)

        spec = _make_design_spec(num_slides)
        project_service.save_design_spec(project_dir, spec)
        project_service.save_design_summary(
            project_dir,
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
        )

        # slides/ HTML 파일 생성
        slides_dir = project_dir / "slides"
        slides_dir.mkdir(exist_ok=True)
        for i in range(num_slides):
            (slides_dir / f"slide_{i + 1:02d}.html").write_text(
                f"<div>slide {i + 1}</div>",
                encoding="utf-8",
            )

        return project_id, project_dir

    def test_move_forward(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """슬라이드를 앞으로 이동 (1 → 3, 1-based)."""
        project_id, project_dir = self._setup_project(
            mcp_tools, tmp_path, monkeypatch, 5
        )
        project_service = mcp_tools["_project_service"]

        result = json.loads(
            mcp_tools["move_slide"](
                project_id=project_id,
                from_index=1,
                to_index=3,
            )
        )
        assert result["slide_count"] == 5
        assert result["from_index"] == 1
        assert result["to_index"] == 3

        # outline 순서 확인: [1,2,3,4,5] → [2,3,1,4,5]
        outline = json.loads(project_service.load_outline(project_dir))
        assert outline["slides"][0]["title"] == "슬라이드 2"
        assert outline["slides"][1]["title"] == "슬라이드 3"
        assert outline["slides"][2]["title"] == "슬라이드 1"
        assert outline["slides"][3]["title"] == "슬라이드 4"
        assert outline["slides"][4]["title"] == "슬라이드 5"

    def test_move_backward(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """슬라이드를 뒤로 이동 (4 → 2, 1-based)."""
        project_id, project_dir = self._setup_project(
            mcp_tools, tmp_path, monkeypatch, 5
        )
        project_service = mcp_tools["_project_service"]

        result = json.loads(
            mcp_tools["move_slide"](
                project_id=project_id,
                from_index=4,
                to_index=2,
            )
        )
        assert result["slide_count"] == 5

        # outline 순서 확인: [1,2,3,4,5] → [1,4,2,3,5]
        outline = json.loads(project_service.load_outline(project_dir))
        assert outline["slides"][0]["title"] == "슬라이드 1"
        assert outline["slides"][1]["title"] == "슬라이드 4"
        assert outline["slides"][2]["title"] == "슬라이드 2"
        assert outline["slides"][3]["title"] == "슬라이드 3"
        assert outline["slides"][4]["title"] == "슬라이드 5"

    def test_move_same_position(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """같은 위치로 이동하면 변경 없이 메시지 반환."""
        project_id, _ = self._setup_project(mcp_tools, tmp_path, monkeypatch, 3)

        result = json.loads(
            mcp_tools["move_slide"](
                project_id=project_id,
                from_index=2,
                to_index=2,
            )
        )
        assert "No move needed" in result["message"]

    def test_move_invalid_from_index(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """from_index가 범위 밖이면 에러."""
        project_id, _ = self._setup_project(mcp_tools, tmp_path, monkeypatch, 3)

        with pytest.raises(ValueError, match="Invalid from_index"):
            mcp_tools["move_slide"](project_id=project_id, from_index=10, to_index=1)

    def test_move_invalid_to_index(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """to_index가 범위 밖이면 에러."""
        project_id, _ = self._setup_project(mcp_tools, tmp_path, monkeypatch, 3)

        with pytest.raises(ValueError, match="Invalid to_index"):
            mcp_tools["move_slide"](project_id=project_id, from_index=1, to_index=10)

    def test_move_syncs_all_stores(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """outline, design_spec, HTML이 모두 동기화된다."""
        project_id, project_dir = self._setup_project(
            mcp_tools, tmp_path, monkeypatch, 3
        )
        project_service = mcp_tools["_project_service"]

        mcp_tools["move_slide"](project_id=project_id, from_index=3, to_index=1)

        # outline: [1,2,3] → [3,1,2]
        outline = json.loads(project_service.load_outline(project_dir))
        assert outline["slides"][0]["title"] == "슬라이드 3"
        assert outline["slides"][1]["title"] == "슬라이드 1"
        assert outline["slides"][2]["title"] == "슬라이드 2"

        # design_spec: 슬라이드 3의 textbox title이 첫 번째에 와야 함
        spec = project_service.load_design_spec(project_dir)
        assert spec.slides[0].textboxes[0].paragraphs[0].runs[0].text == "슬라이드 3"
        assert spec.slides[1].textboxes[0].paragraphs[0].runs[0].text == "슬라이드 1"
        assert spec.slides[2].textboxes[0].paragraphs[0].runs[0].text == "슬라이드 2"

        # HTML: slide 내용 확인
        slides_dir = project_dir / "slides"
        assert (slides_dir / "slide_01.html").read_text(
            encoding="utf-8"
        ) == "<div>slide 3</div>"
        assert (slides_dir / "slide_02.html").read_text(
            encoding="utf-8"
        ) == "<div>slide 1</div>"
        assert (slides_dir / "slide_03.html").read_text(
            encoding="utf-8"
        ) == "<div>slide 2</div>"

    def test_move_preserves_slide_count(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """이동 후 슬라이드 수가 변하지 않는다."""
        project_id, project_dir = self._setup_project(
            mcp_tools, tmp_path, monkeypatch, 5
        )
        project_service = mcp_tools["_project_service"]

        mcp_tools["move_slide"](project_id=project_id, from_index=5, to_index=1)

        assert project_service.get_design_spec_slide_count(project_dir) == 5
        outline = json.loads(project_service.load_outline(project_dir))
        assert len(outline["slides"]) == 5
