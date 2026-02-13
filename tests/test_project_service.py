import json
from pathlib import Path

import pytest

from ppt_generator.interfaces.schemas import ProjectMetadata
from ppt_generator.tools.project.service import ProjectService


@pytest.fixture()
def project_service() -> ProjectService:
    return ProjectService()


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "test_project"
    d.mkdir()
    # project.json을 미리 생성하여 update_step이 동작하도록 함
    meta = {"topic": "테스트 주제", "num_slides": 3, "steps_completed": {}}
    (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return d


SAMPLE_OUTLINE = json.dumps(
    {
        "slides": [
            {
                "title": "제목",
                "bullets": ["요점1"],
                "image_idea": "이미지",
                "layout_type": "title",
                "speaker_notes": "",
                "elements": [],
            }
        ]
    },
    ensure_ascii=False,
    indent=2,
)

SAMPLE_SCRIPT = json.dumps(
    {
        "slides": [
            {
                "title": "제목",
                "bullets": ["요점1"],
                "image_idea": "이미지",
                "layout_type": "title",
                "speaker_notes": "안녕하세요, 발표를 시작하겠습니다.",
                "elements": [],
            }
        ]
    },
    ensure_ascii=False,
    indent=2,
)

SAMPLE_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body><div class="slide">Hello</div></body>
</html>"""


class TestSaveAndLoadOutline:
    def test_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_outline(project_dir, SAMPLE_OUTLINE)
        loaded = project_service.load_outline(project_dir)
        assert json.loads(loaded) == json.loads(SAMPLE_OUTLINE)

    def test_file_created(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_outline(project_dir, SAMPLE_OUTLINE)
        assert (project_dir / "outline.json").exists()


class TestSaveAndLoadScript:
    def test_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_script(project_dir, SAMPLE_SCRIPT)
        loaded = project_service.load_script(project_dir)
        assert json.loads(loaded) == json.loads(SAMPLE_SCRIPT)


class TestSaveSlidesHtml:
    def test_files_created(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid", SAMPLE_HTML)
        assert (project_dir / "slides.html").exists()
        assert (project_dir / "slides_meta.json").exists()

    def test_html_content(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid-123", SAMPLE_HTML)
        html = (project_dir / "slides.html").read_text(encoding="utf-8")
        assert html == SAMPLE_HTML

    def test_meta_content(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid-123", SAMPLE_HTML)
        meta = json.loads((project_dir / "slides_meta.json").read_text(encoding="utf-8"))
        assert meta["session_id"] == "sid-123"


class TestSavePptxCopiesFile:
    def test_copies_file(self, project_service: ProjectService, project_dir: Path, tmp_path: Path) -> None:
        pptx_file = tmp_path / "output.pptx"
        pptx_file.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

        project_service.save_pptx(project_dir, str(pptx_file))

        dest = project_dir / "presentation.pptx"
        assert dest.exists()
        assert dest.read_bytes() == pptx_file.read_bytes()


class TestSaveMetadataAndUpdateStep:
    def test_save_and_load_metadata(self, project_service: ProjectService, project_dir: Path) -> None:
        meta = ProjectMetadata(topic="테스트", num_slides=5)
        project_service.save_metadata(project_dir, meta)

        loaded = project_service.load_metadata(project_dir)
        assert loaded.topic == "테스트"
        assert loaded.num_slides == 5

    def test_update_step(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.update_step(project_dir, "outline")

        loaded = project_service.load_metadata(project_dir)
        assert "outline" in loaded.steps_completed
        # ISO 타임스탬프 형식 확인
        assert "T" in loaded.steps_completed["outline"]


class TestResolveProjectDir:
    def test_generates_uuid_when_empty(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_service.resolve_project_dir("")
        assert project_id  # 빈 문자열이 아닌 UUID가 생성됨
        assert len(project_id) == 36  # UUID 형식 (8-4-4-4-12)
        assert project_dir == tmp_path / project_id
        assert project_dir.exists()

    def test_reuses_existing_id(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        existing_id = "my-existing-project"
        project_id, project_dir = project_service.resolve_project_dir(existing_id)
        assert project_id == existing_id
        assert project_dir == tmp_path / existing_id
        assert project_dir.exists()


class TestListProjects:
    def test_empty_home(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        empty_home = tmp_path / "empty_home"
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", empty_home)

        result = project_service.list_projects()
        assert result == []
        assert empty_home.exists()  # 디렉토리가 자동 생성됨

    def test_lists_existing_projects(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        # 프로젝트 2개 생성
        for name, topic in [("proj-a", "주제 A"), ("proj-b", "주제 B")]:
            d = tmp_path / name
            d.mkdir()
            meta = {"topic": topic, "num_slides": 5, "steps_completed": {"outline": "2025-01-01T00:00:00+00:00"}}
            (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        result = project_service.list_projects()
        assert len(result) == 2
        topics = {p["topic"] for p in result}
        assert topics == {"주제 A", "주제 B"}

    def test_skips_dirs_without_project_json(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        # project.json이 없는 디렉토리
        (tmp_path / "no-meta").mkdir()
        # project.json이 있는 디렉토리
        valid = tmp_path / "valid-proj"
        valid.mkdir()
        meta = {"topic": "유효한 프로젝트", "num_slides": 3, "steps_completed": {}}
        (valid / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        result = project_service.list_projects()
        assert len(result) == 1
        assert result[0]["topic"] == "유효한 프로젝트"

    def test_sorted_by_created_at_desc(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        import time
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        # 시간차를 두고 프로젝트 생성
        for name in ["older", "newer"]:
            d = tmp_path / name
            d.mkdir()
            meta = {"topic": name, "num_slides": 1, "steps_completed": {}}
            (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            time.sleep(0.1)

        result = project_service.list_projects()
        assert result[0]["topic"] == "newer"
        assert result[1]["topic"] == "older"


class TestLoadNonexistentRaises:
    def test_outline(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_outline(tmp_path / "empty")

    def test_script(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_script(tmp_path / "empty")

    def test_metadata(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_metadata(tmp_path / "empty")
