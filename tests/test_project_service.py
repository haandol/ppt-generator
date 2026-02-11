import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import ProjectMetadata
from ppt_generator.tools.project.service import ProjectService


@pytest.fixture()
def slides_service() -> MagicMock:
    svc = MagicMock()
    svc._sessions = {}
    return svc


@pytest.fixture()
def project_service(slides_service: MagicMock) -> ProjectService:
    return ProjectService(slides_service=slides_service)


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


class TestSaveImagesCopiesFiles:
    def test_copies_files(self, project_service: ProjectService, project_dir: Path, tmp_path: Path) -> None:
        # 임시 이미지 파일 생성
        img_dir = tmp_path / "temp_images"
        img_dir.mkdir()
        img_file = img_dir / "image_0.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        images_json = json.dumps(
            {"images": [{"slide_index": 0, "image_path": str(img_file)}]},
            ensure_ascii=False,
        )

        project_service.save_images(project_dir, images_json)

        # 이미지 파일이 project_dir/images/에 복사됨
        copied = project_dir / "images" / "slide_0.png"
        assert copied.exists()
        assert copied.read_bytes() == img_file.read_bytes()


class TestSaveImagesRemapsPaths:
    def test_remapped_paths(self, project_service: ProjectService, project_dir: Path, tmp_path: Path) -> None:
        img_dir = tmp_path / "temp_images"
        img_dir.mkdir()
        img_file = img_dir / "image_1.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        images_json = json.dumps(
            {"images": [{"slide_index": 1, "image_path": str(img_file)}]},
            ensure_ascii=False,
        )

        project_service.save_images(project_dir, images_json)

        # images.json의 경로가 프로젝트 디렉토리 경로로 리매핑됨
        loaded = json.loads(project_service.load_images(project_dir))
        assert len(loaded["images"]) == 1
        remapped_path = loaded["images"][0]["image_path"]
        assert str(project_dir / "images") in remapped_path

    def test_missing_source_skipped(self, project_service: ProjectService, project_dir: Path) -> None:
        images_json = json.dumps(
            {"images": [{"slide_index": 0, "image_path": "/nonexistent/path.png"}]},
            ensure_ascii=False,
        )
        project_service.save_images(project_dir, images_json)
        loaded = json.loads(project_service.load_images(project_dir))
        assert len(loaded["images"]) == 0


class TestSaveAndLoadSlidesHtml:
    def test_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        session_id = "test-session-123"
        project_service.save_slides_html(project_dir, session_id, SAMPLE_HTML)

        loaded_sid, loaded_html = project_service.load_slides_html(project_dir)
        assert loaded_sid == session_id
        assert loaded_html == SAMPLE_HTML

    def test_files_created(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid", SAMPLE_HTML)
        assert (project_dir / "slides.html").exists()
        assert (project_dir / "slides_meta.json").exists()


class TestLoadSlidesRestoresSession:
    def test_session_restored(self, project_service: ProjectService, slides_service: MagicMock, project_dir: Path) -> None:
        session_id = "restore-test-456"
        project_service.save_slides_html(project_dir, session_id, SAMPLE_HTML)

        project_service.load_slides_html(project_dir)
        assert slides_service._sessions[session_id] == SAMPLE_HTML


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


class TestLoadNonexistentRaises:
    def test_outline(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_outline(tmp_path / "empty")

    def test_script(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_script(tmp_path / "empty")

    def test_images(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_images(tmp_path / "empty")

    def test_slides_html(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_slides_html(tmp_path / "empty")

    def test_metadata(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_metadata(tmp_path / "empty")
