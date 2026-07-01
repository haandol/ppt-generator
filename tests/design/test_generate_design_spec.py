"""generate_slides_design_spec 도구 테스트.

배치 도구 — outline_json 또는 project_id 의 outline 파일을 읽어 슬라이드별
design spec 을 생성한다. design_summary 단일 호출 + 슬라이드별 병렬 생성.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import (
    OutlineResponse,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
    SlideOutline,
)
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService
from _helpers import make_slide_spec


def _run(coro):
    return asyncio.run(coro)


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


class TestGenerateSlidesDesignSpecFromProject:
    """project_id 만으로 outline 파일을 읽어 생성."""

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
        outline_dir = proj_dir / "outline"
        outline_dir.mkdir()
        for i in range(num_slides):
            slide = {
                "title": f"슬라이드 {i + 1}",
                "content_summary": f"내용 {i + 1}",
                "component_hint": "bullets",
                "speaker_notes": "",
                "slide_index": i,
            }
            (outline_dir / f"slide_{i + 1:02d}.json").write_text(
                json.dumps(slide, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return "batch-file-proj"

    def test_load_from_outline_file(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project_with_outline(
            tmp_path, monkeypatch, num_slides=3
        )
        result = json.loads(
            _run(
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
        project_id = self._setup_project_with_outline(
            tmp_path, monkeypatch, num_slides=4
        )
        result = json.loads(
            _run(
                mcp_tools["generate_slides_design_spec"](
                    project_id=project_id,
                    total_slides=0,
                )
            )
        )
        assert result["total_slides"] == 4
        assert result["success_count"] == 4

    def test_no_outline_no_project_raises(self, mcp_tools: dict) -> None:
        with pytest.raises(ValueError, match="Either outline_json or project_id"):
            _run(mcp_tools["generate_slides_design_spec"]())


class TestGenerateSlidesDesignSpec:
    """outline_json 명시 호출 + 옵션."""

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

    def test_batch_generates_all_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        result = json.loads(
            _run(
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
            _run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                )
            )
        )
        for i, r in enumerate(result["results"]):
            assert r["slide_index"] == i + 1
            assert r["status"] == "success"
            assert r["slide_file"] == f"slide_{i + 1:02d}.json"

    def test_batch_creates_design_doc_md(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        _run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )
        # DESIGN.md 가 디자인 의도의 단일 소스.
        design_doc_path = tmp_path / project_id / "DESIGN.md"
        assert design_doc_path.exists()

    def test_existing_design_md_not_regenerated_and_directives_injected(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """사람이 편집한 DESIGN.md 는 덮어쓰지 않고, 톤+페이지 요청이
        generate_single_slide 프롬프트에 주입된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)
        design_md = (
            "# DESIGN\n\n"
            "## 전역 디자인 시스템\n"
            "- color_theme: dark\n"
            "- background_color: #0F172A\n\n"
            "## 톤 & 방향\n차분한 기업 톤.\n\n"
            "## 페이지별 요청\n### 2. 슬라이드 2\n좌우 비교 레이아웃으로.\n"
        )
        (tmp_path / project_id / "DESIGN.md").write_text(design_md, encoding="utf-8")

        design_service = mcp_tools["_design_service"]
        _run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        # 기존 DESIGN.md 를 덮어쓰지 않았으므로 draft 생성 LLM 호출 없음.
        assert not design_service.generate_design_doc_draft.called

        # 슬라이드별 directives 주입 확인.
        directives_by_index = {
            call.kwargs["slide_index"]: call.kwargs.get("design_directives", "")
            for call in design_service.generate_single_slide.call_args_list
        }
        # 전역 톤은 모든 슬라이드에.
        assert "차분한 기업 톤." in directives_by_index[1]
        # 페이지 요청은 슬라이드 2 에만.
        assert "좌우 비교 레이아웃으로." in directives_by_index[2]
        assert "좌우 비교 레이아웃으로." not in directives_by_index[1]

    def test_batch_mismatched_total_slides_raises(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        self._setup_project(tmp_path, monkeypatch)
        with pytest.raises(ValueError, match="does not match"):
            _run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=3,
                    project_id="batch-proj",
                )
            )

    def test_batch_single_slide(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
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
            _run(
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
            _run(
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
        project_id = self._setup_project(tmp_path, monkeypatch)
        design_service = mcp_tools["_design_service"]

        def side_effect(*args, **kwargs):
            if kwargs.get("slide_index") == 3:
                raise RuntimeError("LLM 호출 실패")
            return make_slide_spec("생성됨")

        design_service.generate_single_slide.side_effect = side_effect

        result = json.loads(
            _run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                )
            )
        )
        assert result["success_count"] == 4
        assert result["error_count"] == 1

        failed = [r for r in result["results"] if r["status"] == "error"]
        assert len(failed) == 1
        assert failed[0]["slide_index"] == 3
        assert "LLM 호출 실패" in failed[0]["error"]

        succeeded = [r for r in result["results"] if r["status"] == "success"]
        assert len(succeeded) == 4

    def test_batch_respects_parallel_limit(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        import ppt_generator.tools.design.parallel_runner as runner_module

        monkeypatch.setattr(runner_module, "DESIGN_SPEC_PARALLEL", 2)

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
            time.sleep(0.05)
            with lock:
                current_concurrent -= 1
            return make_slide_spec("생성됨")

        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.side_effect = slow_generate

        result = json.loads(
            _run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=outline_10,
                    total_slides=10,
                    project_id=project_id,
                )
            )
        )
        assert result["success_count"] == 10
        assert result["error_count"] == 0
        assert peak_concurrent <= 2, f"동시 실행 peak={peak_concurrent}, 제한=2"

    def test_batch_reports_progress(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
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
            await asyncio.sleep(0.1)
            return result

        result = json.loads(asyncio.run(_run_and_drain()))
        assert result["success_count"] == 5
        non_heartbeat = [
            c for c in progress_calls if "디자인 스펙 생성 중..." not in c[2]
        ]
        assert len(non_heartbeat) == 7
        assert non_heartbeat[-1][0] == 5
        assert non_heartbeat[-1][1] == 5

    def test_batch_with_slide_indices(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        _run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.reset_mock()

        result = json.loads(
            _run(
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
        assert [r["slide_index"] for r in result["results"]] == [2, 4]

    def test_batch_slide_indices_with_index_one(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        result = json.loads(
            _run(
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
        assert [r["slide_index"] for r in result["results"]] == [1, 3, 5]

        design_doc_path = tmp_path / project_id / "DESIGN.md"
        assert design_doc_path.exists()
        assert mcp_tools["_design_service"].generate_design_doc_draft.called

    def test_batch_slide_indices_without_index_zero(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        _run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        design_service = mcp_tools["_design_service"]
        design_service.generate_design_doc_draft.reset_mock()

        result = json.loads(
            _run(
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
        assert not design_service.generate_design_doc_draft.called

    def test_batch_single_index(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        _run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.reset_mock()

        result = json.loads(
            _run(
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
        assert result["results"][0]["slide_index"] == 3
        assert result["results"][0]["slide_file"] == "slide_03.json"

    def test_batch_slide_indices_invalid_raises(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        with pytest.raises(ValueError, match="Invalid slide_index"):
            _run(
                mcp_tools["generate_slides_design_spec"](
                    outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                    total_slides=5,
                    project_id=project_id,
                    slide_indices="0,10",
                )
            )

    def test_batch_enforces_background_color_from_design_summary(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """content 슬라이드 배경색이 design_summary.background_color 로 보정된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        design_service = mcp_tools["_design_service"]
        design_service.generate_design_doc_draft.return_value = (
            {
                "background_color": "#1a1a2e",
                "text_colors": ["#ffffff"],
                "title_font_pt": 32,
                "body_font_pt": 18,
                "card_fills": [],
                "card_borders": [],
            },
            "",
            [],
        )
        wrong_bg_spec = PptxSlideSpec(
            background_color="#ffffff",
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

        _run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        project_service = mcp_tools["_project_service"]
        proj_dir = tmp_path / project_id
        for i in range(5):
            saved_spec = project_service.load_design_spec_slide(proj_dir, i)
            assert saved_spec.background_color == "#1a1a2e"

    def test_closing_bg_enforced_when_image_policy_none(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """배경 주입을 끈 경우(background_image: none) title/closing 도 deck
        배경색으로 결정론적으로 채워진다 (design/0016).

        평소 title/closing 은 배경 이미지가 깔려 background_color=None 으로
        생성되지만, 주입을 끄면 빈 배경이 되므로 deck 배경색으로 마감해야 한다.
        """
        project_id = self._setup_project(tmp_path, monkeypatch)
        # DESIGN.md 로 배경 주입 끔 + deck 배경색 지정
        proj_dir = tmp_path / project_id
        project_service = mcp_tools["_project_service"]
        project_service.save_design_doc_md(
            proj_dir,
            "## 전역 디자인 시스템\n"
            "- background_color: #1A1815\n"
            "- background_image: none\n",
        )

        # LLM 이 closing 을 background_color=None 으로 생성했다고 가정
        design_service = mcp_tools["_design_service"]
        closing_spec = PptxSlideSpec(
            background_color=None,
            textboxes=[
                PptxTextBox(
                    left_px=64,
                    top_px=300,
                    width_px=600,
                    height_px=60,
                    paragraphs=[
                        PptxParagraph(
                            runs=[PptxTextRun(text="감사합니다", font_size_pt=40)]
                        )
                    ],
                )
            ],
            shapes=[],
            images=[],
            speaker_notes="",
            slide_type="closing",
        )
        design_service.generate_single_slide.return_value = closing_spec

        _run(
            mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
            )
        )

        saved = project_service.load_design_spec_slide(proj_dir, 0)
        assert saved.background_color == "#1A1815"


class TestGenerateSlidesDesignSpecWithSlidesService:
    """slides_service 가 등록되면 slides.html 컨테이너가 자동 생성된다."""

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
        project_id = self._setup_project(tmp_path, monkeypatch)

        mcp = MagicMock()
        tools: dict = {}

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func

            return decorator

        mcp.tool = tool_decorator

        design_service = MagicMock()
        design_service.generate_single_slide.return_value = make_slide_spec("생성됨")
        design_service.last_token_usage = {}
        design_service.last_overflow = []
        _summary = {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        }
        design_service.generate_design_summary.return_value = _summary
        design_service.generate_design_doc_draft.return_value = (_summary, "", [])

        from ppt_generator.tools.slides.service import SlidesService

        slides_service = SlidesService()
        project_service = ProjectService()

        register_design_tools(
            mcp,
            project_service,
            design_service_factory=lambda slide_type="content", effort="medium": (
                design_service
            ),
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
            _run(
                tools["generate_slides_design_spec"](
                    outline_json=outline_3,
                    total_slides=3,
                    project_id=project_id,
                )
            )
        )
        assert result["success_count"] == 3
        assert "slides_html_path" in result

        slides_html_path = tmp_path / project_id / "slides.html"
        assert slides_html_path.exists()
        content = slides_html_path.read_text(encoding="utf-8")
        assert "slide_01.html" in content
        assert "slide_02.html" in content
        assert "slide_03.html" in content


class TestAdjacentContextSection:
    """DesignService._adjacent_context_section 단위 테스트."""

    def test_both_none_returns_empty(self) -> None:
        assert DesignService._adjacent_context_section(None, None) == ""

    def test_prev_only(self) -> None:
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


class TestGenerateDesignDocDraft:
    """generate_design_doc_draft — 톤+선별적 페이지 요청까지 LLM 으로 생성하는
    초안 단계 (design/0018). 응답 파싱 견고성 위주로 검증."""

    @staticmethod
    def _service_returning(text: str) -> DesignService:
        agent_result = MagicMock()
        agent_result.metrics.accumulated_usage = {}
        agent_result.__str__ = lambda self: text
        agent = MagicMock(return_value=agent_result)
        return DesignService(agent=agent)

    @staticmethod
    def _outline():
        return OutlineResponse(
            slides=[
                SlideOutline(title="표지", content_summary="제목", slide_type="title"),
                SlideOutline(title="현황", content_summary="병렬 항목 3개"),
                SlideOutline(title="제안", content_summary="핵심 전환점"),
            ]
        )

    def test_parses_theme_tone_and_page_requests(self) -> None:
        payload = json.dumps(
            {
                "theme": {
                    "background_color": "#0B1020",
                    "text_colors": ["#FFFFFF", "#A0AEC0"],
                    "title_font_pt": 34,
                    "body_font_pt": 18,
                    "card_fills": ["#15203A"],
                    "card_borders": [],
                    "header_region": {"top_px": 64, "height_px": 64},
                    "content_region": {"top_px": 148, "height_px": 508},
                    "footer_region": {"top_px": 664, "height_px": 24},
                },
                "tone": "고객 대상, 여백을 넉넉히. 표지에서 크게 열고 제안에서 전환.",
                "page_requests": [
                    {
                        "number": 3,
                        "title": "제안",
                        "request": "풀블리드 한 문장으로 전환점을 강조.",
                    }
                ],
            },
            ensure_ascii=False,
        )
        svc = self._service_returning(payload)
        summary, tone, page_requests = svc.generate_design_doc_draft(self._outline())

        assert summary["background_color"] == "#0B1020"
        assert summary["title_font_pt"] == 34
        assert "전환" in tone
        assert len(page_requests) == 1
        assert page_requests[0].number == 3
        assert page_requests[0].title == "제안"
        assert "풀블리드" in page_requests[0].text

    def test_handles_json_fence(self) -> None:
        payload = (
            "```json\n"
            + json.dumps({"theme": {"background_color": "#111111"}, "tone": "x"})
            + "\n```"
        )
        svc = self._service_returning(payload)
        summary, tone, page_requests = svc.generate_design_doc_draft(self._outline())
        assert summary["background_color"] == "#111111"
        assert tone == "x"
        assert page_requests == []

    def test_empty_page_requests_is_valid(self) -> None:
        payload = json.dumps(
            {
                "theme": {"background_color": "#222"},
                "tone": "절제된 톤",
                "page_requests": [],
            }
        )
        svc = self._service_returning(payload)
        _, _, page_requests = svc.generate_design_doc_draft(self._outline())
        assert page_requests == []

    def test_malformed_page_request_entries_skipped(self) -> None:
        payload = json.dumps(
            {
                "theme": {"background_color": "#333"},
                "tone": "",
                "page_requests": [
                    {"number": 2, "title": "현황", "request": ""},  # 빈 request → 스킵
                    {
                        "number": "nope",
                        "title": "현황",
                        "request": "유효",
                    },  # 번호 비정수
                    "garbage",  # dict 아님 → 스킵
                ],
            }
        )
        svc = self._service_returning(payload)
        _, _, page_requests = svc.generate_design_doc_draft(self._outline())
        # 빈 request 와 garbage 는 빠지고, 번호 비정수 1건만 number=None 으로 남는다.
        assert len(page_requests) == 1
        assert page_requests[0].number is None
        assert page_requests[0].text == "유효"
