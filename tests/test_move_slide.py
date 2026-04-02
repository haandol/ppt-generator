"""move_slide 기능 테스트: 특히 16페이지 이상 대규모 프로젝트에서의 정확성 검증.

16페이지를 11페이지로 이동하는 등 다수 슬라이드 시나리오에서
전체 페이지 개수 인지, 파일 정렬, 인덱스 검증 등을 테스트한다.
"""

import json
from pathlib import Path

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.project.design_spec_store import DesignSpecStore
from ppt_generator.tools.project.html_store import HtmlStore
from ppt_generator.tools.project.jsonl_store import JsonlStore
from ppt_generator.tools.project.service import ProjectService


def _make_slide_spec(title: str) -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=[
            PptxTextBox(
                left_px=40,
                top_px=40,
                width_px=600,
                height_px=60,
                paragraphs=[
                    PptxParagraph(
                        runs=[PptxTextRun(text=title, font_size_pt=32, bold=True)]
                    ),
                ],
            ),
        ],
        shapes=[],
        images=[],
        speaker_notes="",
    )


def _setup_project(tmp_path: Path, num_slides: int) -> tuple[ProjectService, Path]:
    """num_slides 개의 슬라이드를 가진 프로젝트를 생성한다."""
    project_service = ProjectService()
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # project.json
    meta = {"topic": "테스트", "num_slides": num_slides, "steps_completed": {}}
    (project_dir / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )

    # outline
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

    # script
    script_data = json.dumps(
        {
            "slides": [
                {
                    "title": f"슬라이드 {i + 1}",
                    "content_summary": f"내용 {i + 1}",
                    "component_hint": "bullets",
                    "speaker_notes": f"노트 {i + 1}",
                    "slide_type": "content",
                }
                for i in range(num_slides)
            ]
        },
        ensure_ascii=False,
    )
    project_service.save_script(project_dir, script_data)

    # design_spec
    spec = DesignSpec(
        slides=[_make_slide_spec(f"슬라이드 {i + 1}") for i in range(num_slides)]
    )
    project_service.save_design_spec(project_dir, spec)

    # slides/ HTML
    slides_dir = project_dir / "slides"
    slides_dir.mkdir(exist_ok=True)
    for i in range(num_slides):
        (slides_dir / f"slide_{i + 1:02d}.html").write_text(
            f"<div>slide {i + 1}</div>",
            encoding="utf-8",
        )

    return project_service, project_dir


# ============================================================
# 전체 페이지 개수 인지 테스트
# ============================================================


class TestSlideCountDetection:
    """다양한 슬라이드 수에서 전체 개수를 정확히 인지하는지 검증."""

    @pytest.mark.parametrize("num_slides", [10, 16, 20, 25])
    def test_design_spec_slide_count(self, tmp_path: Path, num_slides: int) -> None:
        """design_spec 파일 수가 정확히 인식되는지 확인."""
        svc, project_dir = _setup_project(tmp_path, num_slides)
        assert svc.get_design_spec_slide_count(project_dir) == num_slides

    @pytest.mark.parametrize("num_slides", [10, 16, 20, 25])
    def test_outline_slide_count(self, tmp_path: Path, num_slides: int) -> None:
        """outline 슬라이드 수가 정확히 인식되는지 확인."""
        svc, project_dir = _setup_project(tmp_path, num_slides)
        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == num_slides

    @pytest.mark.parametrize("num_slides", [10, 16, 20, 25])
    def test_script_slide_count(self, tmp_path: Path, num_slides: int) -> None:
        """script 슬라이드 수가 정확히 인식되는지 확인."""
        svc, project_dir = _setup_project(tmp_path, num_slides)
        script = json.loads(svc.load_script(project_dir))
        assert len(script["slides"]) == num_slides

    @pytest.mark.parametrize("num_slides", [10, 16, 20, 25])
    def test_html_file_count(self, tmp_path: Path, num_slides: int) -> None:
        """HTML 파일 수가 정확히 인식되는지 확인."""
        _, project_dir = _setup_project(tmp_path, num_slides)
        slides_dir = project_dir / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == num_slides


# ============================================================
# 파일 정렬 순서 테스트 (10개 이상 슬라이드)
# ============================================================


class TestFileSortOrder:
    """10개 이상 슬라이드에서 파일 정렬 순서가 올바른지 검증.

    slide_01 ~ slide_16 같은 파일이 문자열 정렬 시 올바른 순서를 유지하는지 확인.
    """

    def test_outline_file_sort_order_16_slides(self, tmp_path: Path) -> None:
        """16개 슬라이드 outline 파일이 올바르게 정렬되는지 확인."""
        _, project_dir = _setup_project(tmp_path, 16)
        outline_dir = project_dir / "outline"
        files = sorted(outline_dir.glob("slide_*.json"))
        assert len(files) == 16
        for i, f in enumerate(files):
            assert f.name == f"slide_{i + 1:02d}.json"

    def test_design_spec_file_sort_order_16_slides(self, tmp_path: Path) -> None:
        """16개 슬라이드 design_spec 파일이 올바르게 정렬되는지 확인."""
        _, project_dir = _setup_project(tmp_path, 16)
        spec_dir = project_dir / "design_spec"
        files = sorted(spec_dir.glob("slide_*.json"))
        assert len(files) == 16
        for i, f in enumerate(files):
            assert f.name == f"slide_{i + 1:02d}.json"

    def test_html_file_sort_order_16_slides(self, tmp_path: Path) -> None:
        """16개 슬라이드 HTML 파일이 올바르게 정렬되는지 확인."""
        _, project_dir = _setup_project(tmp_path, 16)
        slides_dir = project_dir / "slides"
        files = sorted(slides_dir.glob("slide_*.html"))
        assert len(files) == 16
        for i, f in enumerate(files):
            assert f.name == f"slide_{i + 1:02d}.html"


# ============================================================
# JsonlStore move 테스트
# ============================================================


class TestJsonlStoreMove:
    """JsonlStore._move_slide_in_dir 의 직접 테스트."""

    def test_move_16th_to_11th_in_dir(self, tmp_path: Path) -> None:
        """16번째 슬라이드(index=15)를 11번째(index=10)로 이동."""
        svc, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()

        store.move_outline_slide(project_dir, from_index=15, to_index=10)

        outline = json.loads(store.load_outline(project_dir))
        titles = [s["title"] for s in outline["slides"]]
        # [1..10, 16, 11..15]
        expected = [
            f"슬라이드 {i}"
            for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 11, 12, 13, 14, 15]
        ]
        assert titles == expected
        assert len(outline["slides"]) == 16

    def test_move_preserves_slide_index_field(self, tmp_path: Path) -> None:
        """이동 후 각 슬라이드의 slide_index 필드가 올바르게 갱신되는지 확인."""
        svc, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()

        store.move_outline_slide(project_dir, from_index=15, to_index=10)

        outline = json.loads(store.load_outline(project_dir))
        for i, slide in enumerate(outline["slides"]):
            assert slide["slide_index"] == i, f"slide_index mismatch at position {i}"

    def test_move_first_to_last(self, tmp_path: Path) -> None:
        """첫 번째 슬라이드를 마지막으로 이동."""
        svc, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()

        store.move_outline_slide(project_dir, from_index=0, to_index=15)

        outline = json.loads(store.load_outline(project_dir))
        titles = [s["title"] for s in outline["slides"]]
        expected = [
            f"슬라이드 {i}"
            for i in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 1]
        ]
        assert titles == expected

    def test_move_last_to_first(self, tmp_path: Path) -> None:
        """마지막 슬라이드를 첫 번째로 이동."""
        svc, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()

        store.move_outline_slide(project_dir, from_index=15, to_index=0)

        outline = json.loads(store.load_outline(project_dir))
        titles = [s["title"] for s in outline["slides"]]
        expected = [
            f"슬라이드 {i}"
            for i in [16, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        ]
        assert titles == expected

    def test_move_invalid_from_index_raises(self, tmp_path: Path) -> None:
        """from_index가 범위 밖이면 IndexError."""
        _, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()
        with pytest.raises(IndexError, match="from_index"):
            store.move_outline_slide(project_dir, from_index=16, to_index=0)

    def test_move_invalid_to_index_raises(self, tmp_path: Path) -> None:
        """to_index가 범위 밖이면 IndexError."""
        _, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()
        with pytest.raises(IndexError, match="to_index"):
            store.move_outline_slide(project_dir, from_index=0, to_index=16)

    def test_move_same_index_noop(self, tmp_path: Path) -> None:
        """같은 인덱스로 이동하면 아무 변화 없음."""
        _, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()

        outline_before = store.load_outline(project_dir)
        store.move_outline_slide(project_dir, from_index=10, to_index=10)
        outline_after = store.load_outline(project_dir)

        assert json.loads(outline_before) == json.loads(outline_after)


# ============================================================
# DesignSpecStore move 테스트
# ============================================================


class TestDesignSpecStoreMove:
    """DesignSpecStore.move_design_spec_slide 직접 테스트."""

    def test_move_16th_to_11th(self, tmp_path: Path) -> None:
        """design_spec에서 16번째를 11번째로 이동."""
        svc, project_dir = _setup_project(tmp_path, 16)
        store = DesignSpecStore()

        store.move_design_spec_slide(project_dir, from_index=15, to_index=10)

        spec = store.load_design_spec(project_dir)
        assert len(spec.slides) == 16
        titles = [s.textboxes[0].paragraphs[0].runs[0].text for s in spec.slides]
        expected = [
            f"슬라이드 {i}"
            for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 11, 12, 13, 14, 15]
        ]
        assert titles == expected

    def test_move_preserves_file_count(self, tmp_path: Path) -> None:
        """이동 후 design_spec 파일 수가 보존되는지 확인."""
        svc, project_dir = _setup_project(tmp_path, 16)
        store = DesignSpecStore()

        store.move_design_spec_slide(project_dir, from_index=15, to_index=10)

        assert store.get_design_spec_slide_count(project_dir) == 16

    def test_move_invalid_from_index_raises(self, tmp_path: Path) -> None:
        _, project_dir = _setup_project(tmp_path, 16)
        store = DesignSpecStore()
        with pytest.raises(IndexError, match="from_index"):
            store.move_design_spec_slide(project_dir, from_index=16, to_index=0)

    def test_move_invalid_to_index_raises(self, tmp_path: Path) -> None:
        _, project_dir = _setup_project(tmp_path, 16)
        store = DesignSpecStore()
        with pytest.raises(IndexError, match="to_index"):
            store.move_design_spec_slide(project_dir, from_index=0, to_index=16)


# ============================================================
# HtmlStore move 테스트
# ============================================================


class TestHtmlStoreMove:
    """HtmlStore.move_slide_html 직접 테스트."""

    def test_move_16th_to_11th(self, tmp_path: Path) -> None:
        """HTML에서 16번째를 11번째로 이동."""
        _, project_dir = _setup_project(tmp_path, 16)
        store = HtmlStore()

        store.move_slide_html(project_dir, from_index=15, to_index=10)

        slides_dir = project_dir / "slides"
        files = sorted(slides_dir.glob("slide_*.html"))
        assert len(files) == 16
        contents = [f.read_text(encoding="utf-8") for f in files]
        expected = [
            f"<div>slide {i}</div>"
            for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 11, 12, 13, 14, 15]
        ]
        assert contents == expected

    def test_move_preserves_file_count(self, tmp_path: Path) -> None:
        _, project_dir = _setup_project(tmp_path, 16)
        store = HtmlStore()

        store.move_slide_html(project_dir, from_index=15, to_index=10)

        slides_dir = project_dir / "slides"
        assert len(list(slides_dir.glob("slide_*.html"))) == 16

    def test_move_out_of_range_is_noop(self, tmp_path: Path) -> None:
        """범위 밖 인덱스는 무시(HtmlStore는 에러를 발생시키지 않고 return)."""
        _, project_dir = _setup_project(tmp_path, 16)
        store = HtmlStore()

        # 에러 없이 무시되어야 함
        store.move_slide_html(project_dir, from_index=16, to_index=0)
        store.move_slide_html(project_dir, from_index=0, to_index=16)

        slides_dir = project_dir / "slides"
        assert len(list(slides_dir.glob("slide_*.html"))) == 16


# ============================================================
# ProjectService 통합: move_slide 전체 동기화 테스트
# ============================================================


class TestProjectServiceMoveSlide:
    """ProjectService를 통해 move가 outline, script, design_spec, HTML 전부 동기화되는지 검증."""

    def test_move_16th_to_11th_all_stores(self, tmp_path: Path) -> None:
        """16번째(index=15)를 11번째(index=10)로 이동 시 모든 store가 동기화."""
        svc, project_dir = _setup_project(tmp_path, 16)

        svc.move_outline_slide(project_dir, from_index=15, to_index=10)
        svc.move_design_spec_slide(project_dir, from_index=15, to_index=10)
        svc.move_slide_html(project_dir, from_index=15, to_index=10)

        expected_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 11, 12, 13, 14, 15]

        # outline
        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == 16
        outline_titles = [s["title"] for s in outline["slides"]]
        assert outline_titles == [f"슬라이드 {i}" for i in expected_order]

        # script
        script = json.loads(svc.load_script(project_dir))
        assert len(script["slides"]) == 16
        script_titles = [s["title"] for s in script["slides"]]
        assert script_titles == [f"슬라이드 {i}" for i in expected_order]

        # design_spec
        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 16
        spec_titles = [s.textboxes[0].paragraphs[0].runs[0].text for s in spec.slides]
        assert spec_titles == [f"슬라이드 {i}" for i in expected_order]

        # HTML
        slides_dir = project_dir / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == 16
        html_contents = [f.read_text(encoding="utf-8") for f in html_files]
        assert html_contents == [f"<div>slide {i}</div>" for i in expected_order]

        # design_spec slide count
        assert svc.get_design_spec_slide_count(project_dir) == 16

    def test_move_middle_slides_20_pages(self, tmp_path: Path) -> None:
        """20페이지에서 중간 슬라이드 이동 (index 14 → 5)."""
        svc, project_dir = _setup_project(tmp_path, 20)

        svc.move_outline_slide(project_dir, from_index=14, to_index=5)
        svc.move_design_spec_slide(project_dir, from_index=14, to_index=5)
        svc.move_slide_html(project_dir, from_index=14, to_index=5)

        # [1..5, 15, 6..14, 16..20]
        expected_order = [
            1,
            2,
            3,
            4,
            5,
            15,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            16,
            17,
            18,
            19,
            20,
        ]

        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == 20
        titles = [s["title"] for s in outline["slides"]]
        assert titles == [f"슬라이드 {i}" for i in expected_order]

        assert svc.get_design_spec_slide_count(project_dir) == 20

    def test_consecutive_moves(self, tmp_path: Path) -> None:
        """연속 이동이 올바르게 동작하는지 확인."""
        svc, project_dir = _setup_project(tmp_path, 16)

        # 첫 번째 이동: index 15 → 10
        svc.move_outline_slide(project_dir, from_index=15, to_index=10)
        svc.move_design_spec_slide(project_dir, from_index=15, to_index=10)
        svc.move_slide_html(project_dir, from_index=15, to_index=10)

        # 두 번째 이동: index 0 → 15 (첫 슬라이드를 마지막으로)
        svc.move_outline_slide(project_dir, from_index=0, to_index=15)
        svc.move_design_spec_slide(project_dir, from_index=0, to_index=15)
        svc.move_slide_html(project_dir, from_index=0, to_index=15)

        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == 16
        # 1차: [1..10, 16, 11..15] → 2차: [2..10, 16, 11..15, 1]
        expected_order = [2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 11, 12, 13, 14, 15, 1]
        titles = [s["title"] for s in outline["slides"]]
        assert titles == [f"슬라이드 {i}" for i in expected_order]

        assert svc.get_design_spec_slide_count(project_dir) == 16

    def test_move_adjacent_forward(self, tmp_path: Path) -> None:
        """인접 슬라이드 앞으로 이동 (index 10 → 11)."""
        svc, project_dir = _setup_project(tmp_path, 16)

        svc.move_outline_slide(project_dir, from_index=10, to_index=11)

        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == 16
        # [1..10, 12, 11, 13..16]
        expected = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 11, 13, 14, 15, 16]
        titles = [s["title"] for s in outline["slides"]]
        assert titles == [f"슬라이드 {i}" for i in expected]

    def test_move_adjacent_backward(self, tmp_path: Path) -> None:
        """인접 슬라이드 뒤로 이동 (index 11 → 10)."""
        svc, project_dir = _setup_project(tmp_path, 16)

        svc.move_outline_slide(project_dir, from_index=11, to_index=10)

        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == 16
        # [1..10, 12, 11, 13..16]
        expected = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 11, 13, 14, 15, 16]
        titles = [s["title"] for s in outline["slides"]]
        assert titles == [f"슬라이드 {i}" for i in expected]


# ============================================================
# move_slide 도구 레벨 통합 테스트 (controller)
# ============================================================


class TestMoveSlideToolWith16Pages:
    """move_slide MCP 도구를 16페이지 프로젝트에서 테스트."""

    @staticmethod
    def _register_tools(project_service: ProjectService) -> dict:
        from unittest.mock import MagicMock

        from ppt_generator.tools.design.controller import register_design_tools

        mcp = MagicMock()
        tools: dict = {}

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func

            return decorator

        mcp.tool = tool_decorator
        design_service = MagicMock()
        design_service.generate_single_slide.return_value = _make_slide_spec(
            "새로 생성됨"
        )
        design_service.last_token_usage = {}
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
            mcp, project_service, design_service_factory=design_service_factory
        )
        tools["_project_service"] = project_service
        return tools

    def test_move_slide_16_to_11(self, tmp_path: Path, monkeypatch) -> None:
        """16페이지 프로젝트에서 16 → 11 이동 (1-based)."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        svc, project_dir = _setup_project(tmp_path, 16)
        import shutil

        dest = tmp_path / "proj-16"
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        tools = self._register_tools(svc)
        result = json.loads(
            tools["move_slide"](
                project_id="proj-16",
                from_index=16,
                to_index=11,
            )
        )
        assert result["slide_count"] == 16
        assert result["from_index"] == 16
        assert result["to_index"] == 11

        resolved_dir = tmp_path / "proj-16"

        # outline 순서 확인
        outline = json.loads(svc.load_outline(resolved_dir))
        assert len(outline["slides"]) == 16
        titles = [s["title"] for s in outline["slides"]]
        expected = [
            f"슬라이드 {i}"
            for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 16, 11, 12, 13, 14, 15]
        ]
        assert titles == expected

        # design_spec 순서 확인
        spec = svc.load_design_spec(resolved_dir)
        assert len(spec.slides) == 16

        # HTML 순서 확인
        slides_dir = resolved_dir / "slides"
        html_files = sorted(slides_dir.glob("slide_*.html"))
        assert len(html_files) == 16

    def test_move_slide_invalid_from_index_16_pages(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """16페이지에서 from_index=17 (범위 초과) 시 ValueError."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        svc, project_dir = _setup_project(tmp_path, 16)
        import shutil

        dest = tmp_path / "proj-16-err"
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        tools = self._register_tools(svc)
        with pytest.raises(ValueError, match="Invalid from_index"):
            tools["move_slide"](project_id="proj-16-err", from_index=17, to_index=1)

    def test_move_slide_invalid_to_index_16_pages(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """16페이지에서 to_index=17 (범위 초과) 시 ValueError."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        svc, project_dir = _setup_project(tmp_path, 16)
        import shutil

        dest = tmp_path / "proj-16-err2"
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        tools = self._register_tools(svc)
        with pytest.raises(ValueError, match="Invalid to_index"):
            tools["move_slide"](project_id="proj-16-err2", from_index=1, to_index=17)

    def test_move_slide_zero_index_raises(self, tmp_path: Path, monkeypatch) -> None:
        """1-based이므로 from_index=0은 에러."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        svc, project_dir = _setup_project(tmp_path, 16)
        import shutil

        dest = tmp_path / "proj-16-zero"
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        tools = self._register_tools(svc)
        with pytest.raises(ValueError, match="Invalid from_index"):
            tools["move_slide"](project_id="proj-16-zero", from_index=0, to_index=1)

    def test_move_slide_boundary_last_valid_index(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """16페이지에서 마지막 유효 인덱스(16)가 정상 동작하는지 확인."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        svc, project_dir = _setup_project(tmp_path, 16)
        import shutil

        dest = tmp_path / "proj-16-boundary"
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        tools = self._register_tools(svc)
        result = json.loads(
            tools["move_slide"](
                project_id="proj-16-boundary",
                from_index=15,
                to_index=16,
            )
        )
        assert result["slide_count"] == 16

    def test_move_slide_with_25_pages(self, tmp_path: Path, monkeypatch) -> None:
        """25페이지 프로젝트에서 이동이 정상 동작하는지 확인."""
        import ppt_generator.tools.project.service as svc_module

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        svc, project_dir = _setup_project(tmp_path, 25)
        import shutil

        dest = tmp_path / "proj-25"
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        tools = self._register_tools(svc)
        result = json.loads(
            tools["move_slide"](
                project_id="proj-25",
                from_index=25,
                to_index=1,
            )
        )
        assert result["slide_count"] == 25

        resolved_dir = tmp_path / "proj-25"
        outline = json.loads(svc.load_outline(resolved_dir))
        assert len(outline["slides"]) == 25
        assert outline["slides"][0]["title"] == "슬라이드 25"
        assert outline["slides"][1]["title"] == "슬라이드 1"
        assert outline["slides"][24]["title"] == "슬라이드 24"


# ============================================================
# 엣지 케이스
# ============================================================


class TestMoveSlideEdgeCases:
    """move_slide의 엣지 케이스 테스트."""

    def test_single_slide_same_position(self, tmp_path: Path) -> None:
        """1페이지 프로젝트에서 같은 위치 이동."""
        svc, project_dir = _setup_project(tmp_path, 1)
        store = JsonlStore()

        # 에러 없이 동작해야 함
        store.move_outline_slide(project_dir, from_index=0, to_index=0)

        outline = json.loads(store.load_outline(project_dir))
        assert len(outline["slides"]) == 1
        assert outline["slides"][0]["title"] == "슬라이드 1"

    def test_two_slides_swap(self, tmp_path: Path) -> None:
        """2페이지 프로젝트에서 순서 교환."""
        svc, project_dir = _setup_project(tmp_path, 2)
        store = JsonlStore()

        store.move_outline_slide(project_dir, from_index=0, to_index=1)

        outline = json.loads(store.load_outline(project_dir))
        assert outline["slides"][0]["title"] == "슬라이드 2"
        assert outline["slides"][1]["title"] == "슬라이드 1"

    def test_negative_index_raises(self, tmp_path: Path) -> None:
        """음수 인덱스는 에러."""
        _, project_dir = _setup_project(tmp_path, 16)
        store = JsonlStore()
        with pytest.raises(IndexError):
            store.move_outline_slide(project_dir, from_index=-1, to_index=0)

    def test_move_does_not_create_extra_files(self, tmp_path: Path) -> None:
        """이동 후 추가 파일이 생성되지 않는지 확인."""
        _, project_dir = _setup_project(tmp_path, 16)
        store = DesignSpecStore()

        spec_dir = project_dir / "design_spec"
        before_count = len(list(spec_dir.glob("slide_*.json")))

        store.move_design_spec_slide(project_dir, from_index=15, to_index=0)

        after_count = len(list(spec_dir.glob("slide_*.json")))
        assert before_count == after_count == 16
