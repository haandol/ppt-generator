"""슬라이드 add / update / delete 도구 테스트 (오프로딩 후).

오프로딩 리팩터 이후 슬라이드 단위 변경은 다음으로 나뉜다:
- delete → delete_slide (LLM 불필요, 단일 도구)
- add/update → prepare_slide_edit (outline 갱신·파일 shift) + ingest_slide_edit
  (mock ingest_slide 가 (spec, overflow) 를 반환하므로 spec_json 내용은 무의미 —
  서버의 파일/저장/동기화 오케스트레이션만 검증한다).
HTML 동기화 동작은 TestModifyDesignSpecHtmlSync 에서 별도 검증.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from _helpers import make_design_spec


class TestModifyDesignSpec:
    """add / update / delete 슬라이드 단위 변경."""

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
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=-1,
            title="새 슬라이드",
            content_summary="내용",
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id=project_id,
                action="add",
                slide_index=-1,
                spec_json="{}",
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
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=2,
            title="새 슬라이드",
            content_summary="내용",
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id=project_id,
                action="add",
                slide_index=2,
                spec_json="{}",
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
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

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

        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="update",
            slide_index=1,
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id=project_id,
                action="update",
                slide_index=1,
                spec_json="{}",
            )
        )
        assert result["slide_count"] == 3

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
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

    def test_invalid_action_raises(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """prepare_slide_edit 는 add/update 이외의 action 에 ValueError."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        with pytest.raises(ValueError, match="action must be 'add' or 'update'"):
            mcp_tools["prepare_slide_edit"](
                project_id=project_id,
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
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        with pytest.raises(ValueError, match="Invalid slide_index"):
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=99,
            )

    def test_add_without_title_raises(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """title/content_summary 없이 add 호출 시 ValueError."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "no-outline-proj"
        project_dir.mkdir()
        meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        spec = make_design_spec(3)
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
            mcp_tools["prepare_slide_edit"](
                project_id="no-outline-proj",
                action="add",
            )

    def test_add_on_imported_project(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """imported 프로젝트는 인라인 파라미터로 add 가능."""
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

        spec = make_design_spec(3)
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

        mcp_tools["prepare_slide_edit"](
            project_id="imported-proj",
            action="add",
            slide_index=-1,
            title="새 슬라이드",
            content_summary="개별 파일로 저장",
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id="imported-proj",
                action="add",
                slide_index=-1,
                spec_json="{}",
            )
        )
        assert result["slide_count"] == 4

        outline_dir = project_dir / "outline"
        assert outline_dir.exists()
        files = sorted(outline_dir.glob("slide_*.json"))
        assert len(files) >= 1

    def test_update_with_save_outline_slide(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """save_outline_slide 로 개별 파일 저장 후 update 성공 (generated 프로젝트)."""
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

        spec = make_design_spec(3)
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

        mcp_tools["prepare_slide_edit"](
            project_id="generated-proj2",
            action="update",
            slide_index=2,
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id="generated-proj2",
                action="update",
                slide_index=2,
                spec_json="{}",
            )
        )
        assert result["slide_count"] == 3

    def test_add_creates_outline_file(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        project_service = mcp_tools["_project_service"]
        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=2,
            title="새 슬라이드",
            content_summary="내용",
        )
        mcp_tools["ingest_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=2,
            spec_json="{}",
        )

        outline_data = json.loads(project_service.load_outline(dest))
        assert len(outline_data["slides"]) == 4
        assert outline_data["slides"][1]["title"] == "새 슬라이드"
        for i, s in enumerate(outline_data["slides"]):
            assert s["slide_index"] == i

    def test_update_reads_outline_from_file(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

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

        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="update",
            slide_index=1,
        )
        mcp_tools["ingest_slide_edit"](
            project_id=project_id,
            action="update",
            slide_index=1,
            spec_json="{}",
        )

        outline_data = json.loads(project_service.load_outline(dest))
        assert len(outline_data["slides"]) == 3
        assert outline_data["slides"][0]["title"] == "새 슬라이드"

    def test_delete_syncs_outline_jsonl(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        mcp_tools["delete_slide"](
            project_id=project_id,
            slide_index=2,
        )

        project_service = mcp_tools["_project_service"]
        outline_data = json.loads(project_service.load_outline(dest))
        assert len(outline_data["slides"]) == 2
        for i, s in enumerate(outline_data["slides"]):
            assert s["slide_index"] == i

    def test_no_outline_file_with_placeholder_succeeds(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
        """outline 이 없어도 sync 가 placeholder 를 생성하므로 update 가 성공."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_service = mcp_tools["_project_service"]
        project_dir = tmp_path / "no-outline-proj"
        project_dir.mkdir()
        meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )

        spec = make_design_spec(3)
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

        mcp_tools["prepare_slide_edit"](
            project_id="no-outline-proj",
            action="update",
            slide_index=1,
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id="no-outline-proj",
                action="update",
                slide_index=1,
                spec_json="{}",
            )
        )
        assert result["slide_count"] == 3

    def test_imported_project_update_without_title_raises(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
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

        spec = make_design_spec(3)
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
            mcp_tools["prepare_slide_edit"](
                project_id="imported-proj",
                action="update",
                slide_index=1,
            )

    def test_imported_project_update_with_title_succeeds(
        self, mcp_tools: dict, monkeypatch, tmp_path: Path
    ) -> None:
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

        spec = make_design_spec(3)
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

        mcp_tools["prepare_slide_edit"](
            project_id="imported-proj2",
            action="update",
            slide_index=1,
            title="수정된 제목",
            content_summary="수정된 내용",
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id="imported-proj2",
                action="update",
                slide_index=1,
                spec_json="{}",
            )
        )
        assert result["slide_count"] == 3


class TestModifyDesignSpecHtmlSync:
    """add/delete 시 slides/ HTML 파일 동기화."""

    @staticmethod
    def _setup_with_html(
        mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path
    ) -> tuple[str, Path]:
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

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
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

        html_files = sorted((dest / "slides").glob("slide_*.html"))
        assert len(html_files) == 2
        assert html_files[0].name == "slide_01.html"
        assert html_files[1].name == "slide_02.html"
        assert "slide 1" in html_files[0].read_text(encoding="utf-8")
        assert "slide 3" in html_files[1].read_text(encoding="utf-8")

    def test_delete_first_slide_html_sync(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=1,
            )
        )
        assert result["slide_count"] == 2

        html_files = sorted((dest / "slides").glob("slide_*.html"))
        assert len(html_files) == 2
        assert "slide 2" in html_files[0].read_text(encoding="utf-8")
        assert "slide 3" in html_files[1].read_text(encoding="utf-8")

    def test_delete_last_slide_html_sync(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=3,
            )
        )
        assert result["slide_count"] == 2

        html_files = sorted((dest / "slides").glob("slide_*.html"))
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
        project_id, dest = self._setup_with_html(
            mcp_tools_with_slides, project_with_design_spec, monkeypatch, tmp_path
        )

        mcp_tools_with_slides["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=2,
            title="새 슬라이드",
            content_summary="내용",
        )
        result = json.loads(
            mcp_tools_with_slides["ingest_slide_edit"](
                project_id=project_id,
                action="add",
                slide_index=2,
                spec_json="{}",
            )
        )
        assert result["slide_count"] == 4

        html_files = sorted((dest / "slides").glob("slide_*.html"))
        assert len(html_files) == 4
        assert "slide 1" in html_files[0].read_text(encoding="utf-8")
        assert html_files[1].name == "slide_02.html"
        assert "new slide" in html_files[1].read_text(encoding="utf-8")
        assert "slide 2" in html_files[2].read_text(encoding="utf-8")
        assert "slide 3" in html_files[3].read_text(encoding="utf-8")

    def test_consecutive_deletes(
        self,
        mcp_tools: dict,
        project_with_design_spec: tuple,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        project_id, dest = self._setup_with_html(
            mcp_tools, project_with_design_spec, monkeypatch, tmp_path
        )

        result = json.loads(
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

        result = json.loads(
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=1,
            )
        )
        assert result["slide_count"] == 1

        html_files = sorted((dest / "slides").glob("slide_*.html"))
        assert len(html_files) == 1
        assert html_files[0].name == "slide_01.html"
        assert "slide 3" in html_files[0].read_text(encoding="utf-8")


class TestBugFixInsertWorkflow:
    """save_outline_slide(insert) → prepare_slide_edit(add) 워크플로우 회귀 검증."""

    @staticmethod
    def _setup_generated_project(
        mcp_tools: dict,
        tmp_path: Path,
        monkeypatch,
        num_slides: int = 5,
    ) -> tuple[str, Path]:
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

        spec = make_design_spec(num_slides)
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
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 5
        )
        project_service = mcp_tools["_project_service"]

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

        outline = json.loads(project_service.load_outline(project_dir))
        assert len(outline["slides"]) == 6
        assert outline["slides"][2]["title"] == "새 슬라이드"
        assert outline["slides"][3]["title"] == "기존 슬라이드 3"

    def test_add_updates_num_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 3
        )
        project_service = mcp_tools["_project_service"]

        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=2,
            title="새 슬라이드",
            content_summary="내용",
        )
        result = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id=project_id,
                action="add",
                slide_index=2,
                spec_json="{}",
            )
        )
        assert result["slide_count"] == 4

        meta = project_service.load_metadata(project_dir)
        assert meta.num_slides == 4

    def test_delete_updates_num_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 3
        )
        project_service = mcp_tools["_project_service"]

        result = json.loads(
            mcp_tools["delete_slide"](
                project_id=project_id,
                slide_index=2,
            )
        )
        assert result["slide_count"] == 2

        meta = project_service.load_metadata(project_dir)
        assert meta.num_slides == 2

    def test_consecutive_adds_correct_slide_count(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, project_dir = self._setup_generated_project(
            mcp_tools, tmp_path, monkeypatch, 3
        )
        project_service = mcp_tools["_project_service"]

        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=2,
            title="새 1",
            content_summary="내용 1",
        )
        result1 = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id=project_id,
                action="add",
                slide_index=2,
                spec_json="{}",
            )
        )
        assert result1["slide_count"] == 4

        mcp_tools["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=3,
            title="새 2",
            content_summary="내용 2",
        )
        result2 = json.loads(
            mcp_tools["ingest_slide_edit"](
                project_id=project_id,
                action="add",
                slide_index=3,
                spec_json="{}",
            )
        )
        assert result2["slide_count"] == 5

        meta = project_service.load_metadata(project_dir)
        assert meta.num_slides == 5

        outline = json.loads(project_service.load_outline(project_dir))
        assert len(outline["slides"]) == 5
        assert outline["slides"][0]["title"] == "기존 슬라이드 1"
        assert outline["slides"][1]["title"] == "새 1"
        assert outline["slides"][2]["title"] == "새 2"
        assert outline["slides"][3]["title"] == "기존 슬라이드 2"
        assert outline["slides"][4]["title"] == "기존 슬라이드 3"
