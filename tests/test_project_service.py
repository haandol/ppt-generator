import json
from pathlib import Path

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    ProjectMetadata,
    PptxImage,
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


MULTI_SLIDE_OUTLINE = json.dumps(
    {
        "slides": [
            {"title": "제목 슬라이드", "content_summary": "소개", "slide_type": "title"},
            {"title": "본문 슬라이드", "content_summary": "핵심 내용", "component_hint": "bullets"},
            {"title": "마무리", "content_summary": "감사합니다", "slide_type": "closing"},
        ]
    },
    ensure_ascii=False,
)

MULTI_SLIDE_SCRIPT = json.dumps(
    {
        "slides": [
            {"title": "제목 슬라이드", "content_summary": "소개", "speaker_notes": "안녕하세요."},
            {"title": "본문 슬라이드", "content_summary": "핵심 내용", "speaker_notes": "핵심 내용입니다."},
            {"title": "마무리", "content_summary": "감사합니다", "speaker_notes": "감사합니다."},
        ]
    },
    ensure_ascii=False,
)


class TestSaveAndLoadOutline:
    def test_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_outline(project_dir, SAMPLE_OUTLINE)
        loaded = project_service.load_outline(project_dir)
        loaded_slides = json.loads(loaded)["slides"]
        original_slides = json.loads(SAMPLE_OUTLINE)["slides"]
        assert len(loaded_slides) == len(original_slides)
        assert loaded_slides[0]["title"] == original_slides[0]["title"]
        assert loaded_slides[0]["slide_index"] == 0

    def test_saves_as_individual_files(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_outline(project_dir, SAMPLE_OUTLINE)
        outline_dir = project_dir / "outline"
        assert outline_dir.exists()
        files = sorted(outline_dir.glob("slide_*.json"))
        assert len(files) == 1
        slide = json.loads(files[0].read_text(encoding="utf-8"))
        assert slide["title"] == "제목"
        assert slide["slide_index"] == 0

    def test_slide_index_injected(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_outline(project_dir, MULTI_SLIDE_OUTLINE)
        outline_dir = project_dir / "outline"
        files = sorted(outline_dir.glob("slide_*.json"))
        for i, f in enumerate(files):
            slide = json.loads(f.read_text(encoding="utf-8"))
            assert slide["slide_index"] == i

    def test_legacy_jsonl_fallback(self, project_service: ProjectService, project_dir: Path) -> None:
        """outline/ 디렉토리가 없고 outline.jsonl이 있으면 fallback으로 읽는다."""
        lines = [json.dumps(s, ensure_ascii=False) for s in json.loads(SAMPLE_OUTLINE)["slides"]]
        (project_dir / "outline.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        loaded = project_service.load_outline(project_dir)
        loaded_slides = json.loads(loaded)["slides"]
        original_slides = json.loads(SAMPLE_OUTLINE)["slides"]
        assert loaded_slides[0]["title"] == original_slides[0]["title"]

    def test_legacy_json_fallback(self, project_service: ProjectService, project_dir: Path) -> None:
        """outline.jsonl도 없고 outline.json이 있으면 fallback으로 읽는다."""
        (project_dir / "outline.json").write_text(SAMPLE_OUTLINE, encoding="utf-8")
        loaded = project_service.load_outline(project_dir)
        assert json.loads(loaded) == json.loads(SAMPLE_OUTLINE)


class TestSaveAndLoadScript:
    def test_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_script(project_dir, SAMPLE_SCRIPT)
        loaded = project_service.load_script(project_dir)
        loaded_slides = json.loads(loaded)["slides"]
        original_slides = json.loads(SAMPLE_SCRIPT)["slides"]
        assert len(loaded_slides) == len(original_slides)
        assert loaded_slides[0]["title"] == original_slides[0]["title"]
        assert loaded_slides[0]["slide_index"] == 0

    def test_saves_as_individual_files(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_script(project_dir, SAMPLE_SCRIPT)
        script_dir = project_dir / "script"
        assert script_dir.exists()
        files = sorted(script_dir.glob("slide_*.json"))
        assert len(files) == 1
        slide = json.loads(files[0].read_text(encoding="utf-8"))
        assert slide["title"] == "제목"
        assert slide["slide_index"] == 0

    def test_slide_index_injected(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_script(project_dir, MULTI_SLIDE_SCRIPT)
        script_dir = project_dir / "script"
        files = sorted(script_dir.glob("slide_*.json"))
        for i, f in enumerate(files):
            slide = json.loads(f.read_text(encoding="utf-8"))
            assert slide["slide_index"] == i

    def test_legacy_jsonl_fallback(self, project_service: ProjectService, project_dir: Path) -> None:
        """script/ 디렉토리가 없고 script.jsonl이 있으면 fallback으로 읽는다."""
        lines = [json.dumps(s, ensure_ascii=False) for s in json.loads(SAMPLE_SCRIPT)["slides"]]
        (project_dir / "script.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        loaded = project_service.load_script(project_dir)
        loaded_slides = json.loads(loaded)["slides"]
        original_slides = json.loads(SAMPLE_SCRIPT)["slides"]
        assert loaded_slides[0]["title"] == original_slides[0]["title"]

    def test_legacy_json_fallback(self, project_service: ProjectService, project_dir: Path) -> None:
        """script.jsonl도 없고 script.json이 있으면 fallback으로 읽는다."""
        (project_dir / "script.json").write_text(SAMPLE_SCRIPT, encoding="utf-8")
        loaded = project_service.load_script(project_dir)
        assert json.loads(loaded) == json.loads(SAMPLE_SCRIPT)


class TestLoadOutlineSlide:
    def test_load_specific_slide(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_outline(project_dir, MULTI_SLIDE_OUTLINE)
        slide = json.loads(project_service.load_outline_slide(project_dir, 1))
        assert slide["title"] == "본문 슬라이드"
        assert slide["slide_index"] == 1

    def test_index_out_of_range(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_outline(project_dir, MULTI_SLIDE_OUTLINE)
        with pytest.raises(IndexError):
            project_service.load_outline_slide(project_dir, 10)

    def test_legacy_json_fallback(self, project_service: ProjectService, project_dir: Path) -> None:
        (project_dir / "outline.json").write_text(MULTI_SLIDE_OUTLINE, encoding="utf-8")
        slide = json.loads(project_service.load_outline_slide(project_dir, 0))
        assert slide["title"] == "제목 슬라이드"


class TestLoadScriptSlide:
    def test_load_specific_slide(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_script(project_dir, MULTI_SLIDE_SCRIPT)
        slide = json.loads(project_service.load_script_slide(project_dir, 2))
        assert slide["title"] == "마무리"
        assert slide["slide_index"] == 2

    def test_index_out_of_range(self, project_service: ProjectService, project_dir: Path) -> None:
        project_service.save_script(project_dir, MULTI_SLIDE_SCRIPT)
        with pytest.raises(IndexError):
            project_service.load_script_slide(project_dir, 10)

    def test_legacy_json_fallback(self, project_service: ProjectService, project_dir: Path) -> None:
        (project_dir / "script.json").write_text(MULTI_SLIDE_SCRIPT, encoding="utf-8")
        slide = json.loads(project_service.load_script_slide(project_dir, 0))
        assert slide["title"] == "제목 슬라이드"


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


class TestProjectSource:
    def test_default_source_is_generated(self, project_service: ProjectService, project_dir: Path) -> None:
        meta = ProjectMetadata(topic="테스트", num_slides=5)
        project_service.save_metadata(project_dir, meta)

        loaded = project_service.load_metadata(project_dir)
        assert loaded.source == "generated"

    def test_imported_source_roundtrip(self, project_service: ProjectService, project_dir: Path) -> None:
        meta = ProjectMetadata(topic="임포트 프로젝트", num_slides=3, source="imported")
        project_service.save_metadata(project_dir, meta)

        loaded = project_service.load_metadata(project_dir)
        assert loaded.source == "imported"

    def test_source_persisted_in_json(self, project_service: ProjectService, project_dir: Path) -> None:
        meta = ProjectMetadata(topic="테스트", num_slides=2, source="imported")
        project_service.save_metadata(project_dir, meta)

        data = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
        assert data["source"] == "imported"

    def test_backward_compatibility_defaults_to_generated(self, project_service: ProjectService, project_dir: Path) -> None:
        """source 필드가 없는 기존 project.json도 로드 가능 (기본값 generated)."""
        old_data = {"topic": "구형 프로젝트", "num_slides": 3, "steps_completed": {}}
        (project_dir / "project.json").write_text(json.dumps(old_data, ensure_ascii=False), encoding="utf-8")

        loaded = project_service.load_metadata(project_dir)
        assert loaded.source == "generated"

    def test_list_projects_includes_source(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        for name, source in [("proj-gen", "generated"), ("proj-imp", "imported")]:
            d = tmp_path / name
            d.mkdir()
            meta = {"topic": name, "num_slides": 3, "steps_completed": {}, "source": source}
            (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        result = project_service.list_projects()
        sources = {p["project_id"]: p["source"] for p in result}
        assert sources["proj-gen"] == "generated"
        assert sources["proj-imp"] == "imported"

    def test_list_projects_defaults_source_for_legacy(self, project_service: ProjectService, tmp_path: Path, monkeypatch) -> None:
        """source 필드가 없는 기존 프로젝트는 list_projects에서 generated로 표시."""
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        d = tmp_path / "legacy-proj"
        d.mkdir()
        meta = {"topic": "레거시", "num_slides": 2, "steps_completed": {}}
        (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        result = project_service.list_projects()
        assert result[0]["source"] == "generated"


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


class TestSlideImages:
    """save_slide_images / get_slide_image_srcs 테스트."""

    def test_save_and_get_images(self, project_service: ProjectService, project_dir: Path) -> None:
        images = [
            PptxImage(left_px=0, top_px=0, width_px=100, height_px=100, image_bytes=b"\x89PNG_fake"),
            PptxImage(left_px=50, top_px=50, width_px=200, height_px=200, image_bytes=b"\x89PNG_fake2"),
        ]
        srcs = project_service.save_slide_images(project_dir, 0, images)

        assert srcs == ["images/slide_01_img_01.png", "images/slide_01_img_02.png"]
        assert (project_dir / "slides/images/slide_01_img_01.png").exists()
        assert (project_dir / "slides/images/slide_01_img_02.png").read_bytes() == b"\x89PNG_fake2"

        # get_slide_image_srcs로 조회
        got = project_service.get_slide_image_srcs(project_dir, 0, 2)
        assert got == ["images/slide_01_img_01.png", "images/slide_01_img_02.png"]

    def test_empty_image_bytes_returns_empty_src(self, project_service: ProjectService, project_dir: Path) -> None:
        images = [
            PptxImage(left_px=0, top_px=0, width_px=100, height_px=100, image_bytes=b""),
        ]
        srcs = project_service.save_slide_images(project_dir, 0, images)

        assert srcs == [""]
        assert not (project_dir / "slides/images/slide_01_img_01.png").exists()

    def test_get_missing_images_returns_empty_src(self, project_service: ProjectService, project_dir: Path) -> None:
        got = project_service.get_slide_image_srcs(project_dir, 0, 2)
        assert got == ["", ""]

    def test_mixed_images(self, project_service: ProjectService, project_dir: Path) -> None:
        images = [
            PptxImage(left_px=0, top_px=0, width_px=100, height_px=100, image_bytes=b"data"),
            PptxImage(left_px=50, top_px=50, width_px=200, height_px=200, image_bytes=b""),
        ]
        srcs = project_service.save_slide_images(project_dir, 2, images)

        assert srcs == ["images/slide_03_img_01.png", ""]
        assert (project_dir / "slides/images/slide_03_img_01.png").read_bytes() == b"data"

    def test_save_slides_html_preserves_images(self, project_service: ProjectService, project_dir: Path) -> None:
        """save_slide_images 후 save_slides_html 호출해도 이미지 파일이 보존되어야 한다."""
        images = [
            PptxImage(left_px=0, top_px=0, width_px=100, height_px=100, image_bytes=b"PNG_DATA"),
        ]
        project_service.save_slide_images(project_dir, 0, images)
        assert (project_dir / "slides/images/slide_01_img_01.png").exists()

        # save_slides_html은 slides/ 디렉토리를 정리하지만 images/는 보존해야 함
        project_service.save_slides_html(
            project_dir, "test-session", ["<html>slide1</html>"], "<html>container</html>",
        )

        assert (project_dir / "slides/images/slide_01_img_01.png").exists()
        assert (project_dir / "slides/images/slide_01_img_01.png").read_bytes() == b"PNG_DATA"
        assert (project_dir / "slides/slide_01.html").exists()

    def test_save_slides_html_twice_preserves_images(self, project_service: ProjectService, project_dir: Path) -> None:
        """save_slides_html을 두 번 호출해도 이미지 파일이 보존되어야 한다."""
        images = [
            PptxImage(left_px=0, top_px=0, width_px=100, height_px=100, image_bytes=b"DATA"),
        ]
        project_service.save_slide_images(project_dir, 0, images)

        project_service.save_slides_html(
            project_dir, "s1", ["<html>v1</html>"], "<html>c1</html>",
        )
        project_service.save_slides_html(
            project_dir, "s2", ["<html>v2</html>"], "<html>c2</html>",
        )

        assert (project_dir / "slides/images/slide_01_img_01.png").read_bytes() == b"DATA"
        assert (project_dir / "slides/slide_01.html").read_text() == "<html>v2</html>"
