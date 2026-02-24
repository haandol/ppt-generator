import json
from pathlib import Path

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    ProjectMetadata,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
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

    def test_saves_as_jsonl(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_script(project_dir, SAMPLE_SCRIPT)
        assert (project_dir / "script.jsonl").exists()
        assert not (project_dir / "script.json").exists()
        lines = (project_dir / "script.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1  # SAMPLE_SCRIPT has 1 slide
        slide = json.loads(lines[0])
        assert slide["title"] == "제목"

    def test_legacy_json_fallback(self, project_service: ProjectService, project_dir: Path) -> None:
        """script.jsonl이 없고 script.json이 있으면 fallback으로 읽는다."""
        (project_dir / "script.json").write_text(SAMPLE_SCRIPT, encoding="utf-8")
        loaded = project_service.load_script(project_dir)
        assert json.loads(loaded) == json.loads(SAMPLE_SCRIPT)


SAMPLE_SLIDE_HTMLS = [
    "<html><body><section>Slide 1</section></body></html>",
    "<html><body><section>Slide 2</section></body></html>",
]
SAMPLE_CONTAINER_HTML = "<html><body><iframe src='slides/slide_01.html'></iframe></body></html>"


class TestSaveSlidesHtml:
    def test_files_created(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid", SAMPLE_SLIDE_HTMLS, SAMPLE_CONTAINER_HTML)
        assert (project_dir / "slides.html").exists()
        assert (project_dir / "slides_meta.json").exists()
        assert (project_dir / "slides" / "slide_01.html").exists()
        assert (project_dir / "slides" / "slide_02.html").exists()

    def test_container_html_content(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid-123", SAMPLE_SLIDE_HTMLS, SAMPLE_CONTAINER_HTML)
        html = (project_dir / "slides.html").read_text(encoding="utf-8")
        assert html == SAMPLE_CONTAINER_HTML

    def test_slide_html_content(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid-123", SAMPLE_SLIDE_HTMLS, SAMPLE_CONTAINER_HTML)
        slide1 = (project_dir / "slides" / "slide_01.html").read_text(encoding="utf-8")
        assert "Slide 1" in slide1
        slide2 = (project_dir / "slides" / "slide_02.html").read_text(encoding="utf-8")
        assert "Slide 2" in slide2

    def test_meta_content(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid-123", SAMPLE_SLIDE_HTMLS, SAMPLE_CONTAINER_HTML)
        meta = json.loads((project_dir / "slides_meta.json").read_text(encoding="utf-8"))
        assert meta["session_id"] == "sid-123"

    def test_overwrite_clears_old_files(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_slides_html(project_dir, "sid-1", SAMPLE_SLIDE_HTMLS, SAMPLE_CONTAINER_HTML)
        # 슬라이드 1개로 다시 저장
        project_service.save_slides_html(project_dir, "sid-2", [SAMPLE_SLIDE_HTMLS[0]], SAMPLE_CONTAINER_HTML)
        slides_dir = project_dir / "slides"
        files = list(slides_dir.glob("slide_*.html"))
        assert len(files) == 1


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
        meta = ProjectMetadata(topic="테스트", num_slides=5, audience_type="technical", presentation_minutes=20)
        project_service.save_metadata(project_dir, meta)

        loaded = project_service.load_metadata(project_dir)
        assert loaded.topic == "테스트"
        assert loaded.num_slides == 5
        assert loaded.audience_type == "technical"
        assert loaded.presentation_minutes == 20

    def test_load_metadata_backward_compatibility(self, project_service: ProjectService, project_dir: Path) -> None:
        """audience_type, presentation_minutes가 없는 기존 project.json도 로드 가능."""
        old_data = {"topic": "구형 프로젝트", "num_slides": 3, "steps_completed": {}}
        (project_dir / "project.json").write_text(json.dumps(old_data, ensure_ascii=False), encoding="utf-8")

        loaded = project_service.load_metadata(project_dir)
        assert loaded.topic == "구형 프로젝트"
        assert loaded.audience_type == "general"
        assert loaded.presentation_minutes == 15

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


def _make_slide_spec(title: str = "테스트") -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=[
            PptxTextBox(
                left_px=40, top_px=40, width_px=600, height_px=60,
                paragraphs=[PptxParagraph(runs=[PptxTextRun(text=title, font_size_pt=32, bold=True)])],
            ),
        ],
        shapes=[],
        images=[],
        speaker_notes="",
    )


def _make_design_spec(n: int = 3) -> DesignSpec:
    return DesignSpec(slides=[_make_slide_spec(f"슬라이드 {i+1}") for i in range(n)])


class TestSaveAndLoadDesignSpec:
    def test_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        spec = _make_design_spec(3)
        project_service.save_design_spec(project_dir, spec)
        loaded = project_service.load_design_spec(project_dir)
        assert len(loaded.slides) == 3

    def test_directory_created(self, project_service: ProjectService, project_dir: Path) -> None:
        spec = _make_design_spec(2)
        project_service.save_design_spec(project_dir, spec)
        spec_dir = project_dir / "design_spec"
        assert spec_dir.is_dir()
        files = sorted(spec_dir.glob("slide_*.json"))
        assert len(files) == 2
        assert files[0].name == "slide_01.json"
        assert files[1].name == "slide_02.json"

    def test_overwrite_clears_old_files(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_design_spec(project_dir, _make_design_spec(5))
        project_service.save_design_spec(project_dir, _make_design_spec(2))
        spec_dir = project_dir / "design_spec"
        files = list(spec_dir.glob("slide_*.json"))
        assert len(files) == 2

    def test_load_nonexistent_raises(self, project_service: ProjectService, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            project_service.load_design_spec(tmp_path / "nonexistent")


class TestDesignSpecSlideCRUD:
    def test_load_single_slide(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_design_spec(project_dir, _make_design_spec(3))
        slide = project_service.load_design_spec_slide(project_dir, 0)
        assert slide.textboxes[0].paragraphs[0].runs[0].text == "슬라이드 1"

    def test_save_single_slide(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_design_spec(project_dir, _make_design_spec(3))
        new_slide = _make_slide_spec("수정됨")
        project_service.save_design_spec_slide(project_dir, 1, new_slide)
        loaded = project_service.load_design_spec_slide(project_dir, 1)
        assert loaded.textboxes[0].paragraphs[0].runs[0].text == "수정됨"

    def test_delete_slide(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_design_spec(project_dir, _make_design_spec(3))
        project_service.delete_design_spec_slide(project_dir, 1)
        assert project_service.get_design_spec_slide_count(project_dir) == 2
        # 삭제 후 재번호 확인
        slide_0 = project_service.load_design_spec_slide(project_dir, 0)
        slide_1 = project_service.load_design_spec_slide(project_dir, 1)
        assert slide_0.textboxes[0].paragraphs[0].runs[0].text == "슬라이드 1"
        assert slide_1.textboxes[0].paragraphs[0].runs[0].text == "슬라이드 3"

    def test_insert_slide(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_design_spec(project_dir, _make_design_spec(2))
        new_slide = _make_slide_spec("삽입됨")
        project_service.insert_design_spec_slide(project_dir, 1, new_slide)
        assert project_service.get_design_spec_slide_count(project_dir) == 3
        slide_1 = project_service.load_design_spec_slide(project_dir, 1)
        assert slide_1.textboxes[0].paragraphs[0].runs[0].text == "삽입됨"

    def test_get_slide_count(self, project_service: ProjectService, project_dir: Path) -> None:
        assert project_service.get_design_spec_slide_count(project_dir) == 0
        project_service.save_design_spec(project_dir, _make_design_spec(4))
        assert project_service.get_design_spec_slide_count(project_dir) == 4


class TestCreateDesignSpecSlide:
    def test_creates_slide_without_existing_file(self, project_service: ProjectService, project_dir: Path) -> None:
        slide = _make_slide_spec("새 슬라이드")
        project_service.create_design_spec_slide(project_dir, 0, slide)
        loaded = project_service.load_design_spec_slide(project_dir, 0)
        assert loaded.textboxes[0].paragraphs[0].runs[0].text == "새 슬라이드"

    def test_overwrites_existing_file(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_design_spec(project_dir, _make_design_spec(3))
        new_slide = _make_slide_spec("덮어쓴 슬라이드")
        project_service.create_design_spec_slide(project_dir, 1, new_slide)
        loaded = project_service.load_design_spec_slide(project_dir, 1)
        assert loaded.textboxes[0].paragraphs[0].runs[0].text == "덮어쓴 슬라이드"

    def test_creates_design_spec_dir_if_missing(self, project_service: ProjectService, project_dir: Path) -> None:
        slide = _make_slide_spec("테스트")
        project_service.create_design_spec_slide(project_dir, 0, slide)
        assert (project_dir / "design_spec").is_dir()
        assert (project_dir / "design_spec" / "slide_01.json").exists()


class TestSaveAndLoadDesignSummary:
    def test_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        summary = {"background_color": "#1a1a2e", "text_colors": ["#ffffff"]}
        project_service.save_design_summary(project_dir, summary)
        loaded = project_service.load_design_summary(project_dir)
        assert loaded == summary

    def test_load_returns_none_when_missing(self, project_service: ProjectService, project_dir: Path) -> None:
        result = project_service.load_design_summary(project_dir)
        assert result is None

    def test_creates_design_spec_dir_if_missing(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_design_summary(project_dir, {"test": True})
        assert (project_dir / "design_spec" / "design_summary.json").exists()

    def test_not_counted_as_slide(self, project_service: ProjectService, project_dir: Path) -> None:
        """design_summary.json은 slide_*.json glob에 매칭되지 않는다."""
        project_service.save_design_summary(project_dir, {"test": True})
        assert project_service.get_design_spec_slide_count(project_dir) == 0


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
