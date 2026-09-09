"""Visual QA service 테스트: prepare/ingest + 스크린샷 캡처(Playwright mock).

LLM 호출은 클라이언트로 오프로딩되었으므로 서버는 스크린샷 캡처(결정론적)와
prepare(태스크 조립)/ingest(클라이언트 JSON 검증·후처리)만 담당한다. 이 파일은
그 세 지점을 검증한다:
  - capture_screenshots — Playwright mock
  - prepare_analysis / ingest_analysis — 이슈 감지
  - prepare_fix / ingest_fix — 수정 spec 검증·정합화
"""

import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic
from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.interfaces.llm_output_models import (
    VisualQAFixPatchOutput,
    VisualQAIssue,
    VisualQAOutput,
)
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxImage,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.visual_qa.controller import register_visual_qa_tools
from ppt_generator.tools.visual_qa.service import VisualQAService

from _helpers import make_slide_spec as _make_spec


def _make_qa_output_json(has_issues: bool, issues: list[dict] | None = None) -> str:
    """클라이언트가 생성했을 법한 분석 결과 JSON 을 조립한다 (ingest_analysis 입력)."""
    if issues is None:
        issues = []
    output = VisualQAOutput(
        has_issues=has_issues,
        issues=[VisualQAIssue(**i) for i in issues],
        overall_quality="good" if not has_issues else "needs_improvement",
    )
    return output.model_dump_json()


def _make_fix_output_json() -> str:
    """클라이언트가 생성했을 법한 최소 시각 patch JSON."""
    return VisualQAFixPatchOutput.model_validate(
        {
            "operations": [
                {
                    "element_type": "textbox",
                    "element_index": 0,
                    "field": "width_px",
                    "value": 700,
                },
                {
                    "element_type": "textbox",
                    "element_index": 0,
                    "field": "font_size_pt",
                    "value": 28,
                    "paragraph_index": 0,
                    "run_index": 0,
                },
            ]
        }
    ).model_dump_json()


def _patch_json(*operations: dict) -> str:
    return VisualQAFixPatchOutput.model_validate(
        {"operations": list(operations)}
    ).model_dump_json()


def _run_patch(
    field: str,
    value,
) -> str:
    return _patch_json(
        {
            "element_type": "textbox",
            "element_index": 0,
            "field": field,
            "value": value,
            "paragraph_index": 0,
            "run_index": 0,
        }
    )


def _make_simple_spec(title: str = "테스트") -> PptxSlideSpec:
    """slide_type='title' 인 spec — ingest_fix 가 SimpleSlideSpecOutput 을 쓰게 한다."""
    return replace(_make_spec(title), slide_type="title")


def _register_visual_tools(
    project_service: ProjectService,
) -> dict[str, object]:
    mcp = MagicMock()
    tools: dict[str, object] = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator
    register_visual_qa_tools(
        mcp,
        project_service,
        VisualQAService(),
        MagicMock(),
    )
    return tools


def _setup_visual_project(
    tmp_path: Path, monkeypatch
) -> tuple[str, Path, ProjectService, dict[str, object]]:
    import ppt_generator.tools.project.service as service_module

    monkeypatch.setattr(service_module, "PPT_GENERATOR_HOME", tmp_path)
    project_id = "visual-project"
    project_dir = tmp_path / project_id
    project_dir.mkdir()
    (project_dir / "project.json").write_text(
        '{"topic":"visual","num_slides":1,"steps_completed":{}}',
        encoding="utf-8",
    )
    project_service = ProjectService()
    project_service.save_design_spec(
        project_dir, DesignSpec(slides=[_make_simple_spec()])
    )
    screenshot = project_dir / "screenshots" / "slide_01_v0.png"
    screenshot.parent.mkdir()
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")
    return (
        project_id,
        project_dir,
        project_service,
        _register_visual_tools(project_service),
    )


def _prepare_analysis_context(tools: dict, project_id: str) -> str:
    """분석 결과를 만들기 전에 준비한 현재 입력의 검증 토큰을 받는다."""
    prepared = json.loads(
        tools["prepare_visual_qa_analysis"](project_id=project_id, slide_index=1)
    )
    return prepared["prepared_context"]


class TestVisualQAServiceCapture:
    """capture_screenshots 테스트 (Playwright mock)."""

    def test_playwright_package_is_optional(self) -> None:
        import sys

        import ppt_generator.tools.visual_qa.screenshot as screenshot_module

        with patch.dict(
            sys.modules,
            {"playwright": None, "playwright.sync_api": None},
        ):
            with pytest.raises(RuntimeError, match="Playwright 패키지가 설치되지"):
                screenshot_module.sync_playwright()

    def test_chromium_not_installed_raises(self, tmp_path: Path) -> None:
        """Chromium 브라우저 바이너리 미설치 시 RuntimeError 발생."""
        svc = VisualQAService()
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "slide_01.html").write_text("<html></html>")

        mock_pw_ctx = MagicMock()
        mock_pw_ctx.__enter__ = MagicMock(return_value=mock_pw_ctx)
        mock_pw_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw_ctx.chromium.launch.side_effect = Exception(
            "Executable doesn't exist at /path/chromium"
        )

        with patch(
            "ppt_generator.tools.visual_qa.screenshot.sync_playwright",
            return_value=mock_pw_ctx,
        ):
            with pytest.raises(
                RuntimeError, match="Chromium 브라우저가 설치되지 않았습니다"
            ):
                svc.capture_screenshots(tmp_path, [0])

    def test_missing_html_returns_empty(self, tmp_path: Path) -> None:
        """HTML 파일이 없으면 빈 딕셔너리 반환."""
        svc = VisualQAService()
        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()

        mock_pw_ctx = MagicMock()
        mock_pw_ctx.__enter__ = MagicMock(return_value=mock_pw_ctx)
        mock_pw_ctx.__exit__ = MagicMock(return_value=False)

        with patch(
            "ppt_generator.tools.visual_qa.screenshot.sync_playwright",
            return_value=mock_pw_ctx,
        ):
            result = svc.capture_screenshots(tmp_path, [0])
            assert result == {}

    def test_timeout_returns_without_waiting_for_worker(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """worker가 멈춰도 executor shutdown이 MCP 호출을 다시 블로킹하지 않는다."""
        import ppt_generator.tools.visual_qa.screenshot as screenshot_module

        slides_dir = tmp_path / "slides"
        slides_dir.mkdir()
        (slides_dir / "slide_01.html").write_text("<html></html>")

        release_worker = Event()
        mock_pw_ctx = MagicMock()
        mock_pw_ctx.__enter__ = MagicMock(return_value=mock_pw_ctx)
        mock_pw_ctx.__exit__ = MagicMock(return_value=False)

        def _blocked_launch(*, headless: bool):
            release_worker.wait(timeout=1)
            return MagicMock()

        mock_pw_ctx.chromium.launch.side_effect = _blocked_launch
        monkeypatch.setattr(screenshot_module, "SCREENSHOT_TIMEOUT", 0.01)
        monkeypatch.setattr(screenshot_module, "VISUAL_QA_PARALLEL", 1)

        try:
            started = monotonic()
            with patch(
                "ppt_generator.tools.visual_qa.screenshot.sync_playwright",
                return_value=mock_pw_ctx,
            ):
                result = VisualQAService.capture_screenshots(tmp_path, [0])
            elapsed = monotonic() - started

            assert result == {}
            assert elapsed < 0.1
        finally:
            release_worker.set()


class TestVisualQAServiceAnalyze:
    """prepare_analysis / ingest_analysis 테스트."""

    def test_prepare_analysis_carries_screenshot_and_schema(
        self, tmp_path: Path
    ) -> None:
        """prepare_analysis 는 스크린샷 경로(images)와 응답 스키마를 태스크에 실어준다."""
        png_path = tmp_path / "test.png"
        png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        svc = VisualQAService()
        task = svc.prepare_analysis(png_path, 0, _make_spec())

        assert task["images"] == [str(png_path)]
        assert "system_prompt" in task
        assert "user_prompt" in task
        assert "response_schema" in task

    def test_ingest_no_issues(self) -> None:
        """issue 목록이 비어 있으면 상충하는 요약값도 서버가 정상화한다."""
        svc = VisualQAService()
        result = svc.ingest_analysis(
            {"has_issues": True, "issues": [], "overall_quality": "poor"}
        )
        assert result.has_issues is False
        assert result.overall_quality == "good"
        assert result.issues == []

    def test_ingest_with_issues(self) -> None:
        """이슈가 있는 분석 결과 검증."""
        issues = [
            {
                "issue_type": "text_truncation",
                "severity": "high",
                "element_type": "textbox",
                "element_index": 0,
                "description": "제목이 단어 중간에서 잘림",
                "suggested_fix": "텍스트박스 너비 확장",
            },
        ]
        svc = VisualQAService()
        result = svc.ingest_analysis(
            {
                "has_issues": False,
                "issues": issues,
                "overall_quality": "good",
            }
        )
        assert result.has_issues is True
        assert result.overall_quality == "poor"
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "text_truncation"

    def test_controller_rejects_out_of_range_analysis_before_ingest(self) -> None:
        tools: dict = {}
        mcp = MagicMock()

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func

            return decorator

        mcp.tool = tool_decorator
        project_service = MagicMock()
        project_service.resolve_existing_project_dir.return_value = (
            "project-1",
            Path("/tmp/project-1"),
        )
        project_service.get_design_spec_slide_count.return_value = 1
        visual_qa_service = MagicMock()
        register_visual_qa_tools(
            mcp,
            project_service,
            visual_qa_service,
            MagicMock(),
        )

        with pytest.raises(ValueError, match="valid range: 1-1"):
            tools["ingest_visual_qa_analysis"](
                project_id="project-1",
                slide_index=2,
                analysis_json="{}",
            )

        visual_qa_service.ingest_analysis.assert_not_called()


class TestVisualQAServiceFix:
    """prepare_fix / ingest_fix 테스트."""

    def test_prepare_fix_carries_screenshot_and_schema(self, tmp_path: Path) -> None:
        """prepare_fix 는 스크린샷 경로(images)와 응답 스키마를 태스크에 실어준다."""
        png_path = tmp_path / "test.png"
        png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        svc = VisualQAService()
        task = svc.prepare_fix(
            png_path,
            _make_spec(),
            issues=[
                {
                    "issue_type": "text_truncation",
                    "severity": "high",
                    "element_type": "textbox",
                    "element_index": 0,
                    "description": "test",
                    "suggested_fix": "test",
                }
            ],
        )
        assert task["images"] == [str(png_path)]
        assert "system_prompt" in task
        assert "response_schema" in task

    def test_successful_fix(self) -> None:
        """수정 성공: 검증된 JSON 이 PptxSlideSpec 으로 정합화된다."""
        svc = VisualQAService()
        result = svc.ingest_fix(
            _make_fix_output_json(),
            _make_simple_spec(),
            [
                {
                    "issue_type": "text_truncation",
                    "element_type": "textbox",
                    "element_index": 0,
                }
            ],
        )
        assert result is not None
        assert isinstance(result, PptxSlideSpec)
        assert result.textboxes[0].width_px == 700
        assert result.textboxes[0].paragraphs[0].runs[0].font_size_pt == 28

    def test_fix_failure_returns_none(self) -> None:
        """수정 실패(잘못된 JSON) 시 None 반환."""
        svc = VisualQAService()
        result = svc.ingest_fix("{ not valid json", _make_simple_spec())
        assert result is None

    def test_numeric_patch_rejects_boolean(self) -> None:
        result = VisualQAService().ingest_fix(
            _patch_json(
                {
                    "element_type": "textbox",
                    "element_index": 0,
                    "field": "width_px",
                    "value": True,
                }
            ),
            _make_simple_spec(),
            [
                {
                    "issue_type": "text_truncation",
                    "element_type": "textbox",
                    "element_index": 0,
                }
            ],
        )
        assert result is None


class TestVisualQAControllerContexts:
    @pytest.mark.parametrize("changed", ["spec", "intent", "screenshot"])
    def test_analysis_rejects_input_changed_since_prepare(
        self, tmp_path: Path, monkeypatch, changed: str
    ) -> None:
        project_id, project_dir, project_service, tools = _setup_visual_project(
            tmp_path, monkeypatch
        )
        project_service.save_design_doc_md(project_dir, "## 톤 & 방향\nBefore")
        prepared = json.loads(
            tools["prepare_visual_qa_analysis"](project_id=project_id, slide_index=1)
        )
        if changed == "spec":
            project_service.save_design_spec_slide(
                project_dir, 0, _make_simple_spec("Changed")
            )
        elif changed == "intent":
            project_service.save_design_doc_md(project_dir, "## 톤 & 방향\nAfter")
        else:
            (project_dir / "screenshots/slide_01_v0.png").write_bytes(
                b"\x89PNG\r\n\x1a\nchanged"
            )
        with pytest.raises(ValueError, match="Stale"):
            tools["ingest_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                analysis_json=_make_qa_output_json(False),
                prepared_context=prepared["prepared_context"],
            )

    def test_analysis_requires_its_prepare_context(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, _, _, tools = _setup_visual_project(tmp_path, monkeypatch)
        with pytest.raises(ValueError, match="prepared_context"):
            tools["ingest_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                analysis_json=_make_qa_output_json(False),
            )

    def test_fix_rejects_stale_design_intent(self, tmp_path: Path, monkeypatch) -> None:
        project_id, project_dir, project_service, tools = _setup_visual_project(
            tmp_path, monkeypatch
        )
        project_service.save_design_doc_md(project_dir, "## 톤 & 방향\n한 문장 전환")
        analyzed = json.loads(
            tools["ingest_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                analysis_json=_make_qa_output_json(False),
                prepared_context=_prepare_analysis_context(tools, project_id),
            )
        )
        prepared = json.loads(
            tools["prepare_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                analysis_context=analyzed["analysis_context"],
            )
        )
        assert "한 문장 전환" in prepared["user_prompt"]
        project_service.save_design_doc_md(project_dir, "## 톤 & 방향\n균일한 비교 표")
        with pytest.raises(ValueError, match="design intent changed"):
            tools["ingest_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                fix_context=prepared["fix_context"],
                fix_json='{"operations":[]}',
            )

    def test_prepare_analysis_accepts_external_png(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, project_dir, _, tools = _setup_visual_project(tmp_path, monkeypatch)
        canonical = project_dir / "screenshots" / "slide_01_v0.png"
        canonical.unlink()
        external = tmp_path / "external.png"
        external.write_bytes(b"\x89PNG\r\n\x1a\nexternal")

        prepared = json.loads(
            tools["prepare_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                iteration=0,
                screenshot_path=str(external),
            )
        )

        assert canonical.read_bytes() == external.read_bytes()
        assert prepared["images"] == [str(canonical)]

    def test_prepare_analysis_rejects_non_png(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, _, _, tools = _setup_visual_project(tmp_path, monkeypatch)
        external = tmp_path / "external.txt"
        external.write_text("not png", encoding="utf-8")

        with pytest.raises(ValueError, match="must be a PNG"):
            tools["prepare_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                screenshot_path=str(external),
            )

    def test_analysis_fix_round_trip(self, tmp_path: Path, monkeypatch) -> None:
        project_id, project_dir, project_service, tools = _setup_visual_project(
            tmp_path, monkeypatch
        )
        issue = {
            "issue_type": "text_truncation",
            "severity": "high",
            "element_type": "textbox",
            "element_index": 0,
            "description": "제목이 잘림",
            "suggested_fix": "텍스트박스 너비 확장",
        }

        analysis = json.loads(
            tools["ingest_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                analysis_json=_make_qa_output_json(True, [issue]),
                prepared_context=_prepare_analysis_context(tools, project_id),
            )
        )
        prepared = json.loads(
            tools["prepare_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                analysis_context=analysis["analysis_context"],
                iteration=0,
            )
        )
        monkeypatch.setattr(
            project_service,
            "renumber_design_spec_image_srcs",
            lambda *args, **kwargs: pytest.fail(
                "visual QA fix must not renumber unrelated slides"
            ),
        )
        fixed = json.loads(
            tools["ingest_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                fix_json=_make_fix_output_json(),
                fix_context=prepared["fix_context"],
            )
        )

        assert fixed["status"] == "fixed"
        assert Path(fixed["slide_html_path"]).exists()
        assert (
            project_service.load_design_spec_slide(project_dir, 0).textboxes[0].width_px
            == 700
        )

    def test_unchanged_fix_reports_unresolved_without_saving(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, project_dir, project_service, tools = _setup_visual_project(
            tmp_path, monkeypatch
        )
        issue = {
            "issue_type": "overlap",
            "severity": "high",
            "element_type": "textbox",
            "element_index": 0,
            "description": "구조 변경 없이는 해결 불가",
            "suggested_fix": "슬라이드 편집으로 재구성",
        }
        analysis = json.loads(
            tools["ingest_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                analysis_json=_make_qa_output_json(True, [issue]),
                prepared_context=_prepare_analysis_context(tools, project_id),
            )
        )
        prepared = json.loads(
            tools["prepare_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                analysis_context=analysis["analysis_context"],
                iteration=0,
            )
        )
        monkeypatch.setattr(
            project_service,
            "save_design_spec_slide",
            lambda *args, **kwargs: pytest.fail(
                "unchanged Visual QA result must not be saved"
            ),
        )

        result = json.loads(
            tools["ingest_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                fix_json=_patch_json(),
                fix_context=prepared["fix_context"],
            )
        )

        assert result["status"] == "unresolved"
        assert result["remaining_issues"][0]["issue_type"] == "overlap"
        assert "slide_html_path" not in result

    def test_rejects_forged_and_stale_analysis_context(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        project_id, project_dir, project_service, tools = _setup_visual_project(
            tmp_path, monkeypatch
        )
        issue = {
            "issue_type": "overlap",
            "severity": "high",
            "element_type": "textbox",
            "element_index": 0,
            "description": "겹침",
            "suggested_fix": "이동",
        }
        analysis = json.loads(
            tools["ingest_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                analysis_json=_make_qa_output_json(True, [issue]),
                prepared_context=_prepare_analysis_context(tools, project_id),
            )
        )
        context = analysis["analysis_context"]
        forged = context[:-1] + ("A" if context[-1] != "A" else "B")
        with pytest.raises(ValueError, match="edit_context"):
            tools["prepare_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                analysis_context=forged,
                iteration=0,
            )

        project_service.save_design_spec_slide(
            project_dir, 0, replace(_make_simple_spec(), background_color="#ffffff")
        )
        with pytest.raises(ValueError, match="Stale analysis_context"):
            tools["prepare_visual_qa_fix"](
                project_id=project_id,
                slide_index=1,
                analysis_context=context,
                iteration=0,
            )

    @pytest.mark.parametrize(
        "target",
        [
            {"element_type": "textbox", "element_index": 1},
            {
                "element_type": "textbox",
                "element_index": 0,
                "related_element_type": "shape",
                "related_element_index": 0,
            },
        ],
    )
    def test_rejects_out_of_range_issue_targets(
        self, tmp_path: Path, monkeypatch, target: dict
    ) -> None:
        project_id, _, _, tools = _setup_visual_project(tmp_path, monkeypatch)
        issue = {
            "issue_type": "overlap",
            "severity": "high",
            "description": "겹침",
            "suggested_fix": "이동",
            **target,
        }

        with pytest.raises(ValueError, match="invalid"):
            tools["ingest_visual_qa_analysis"](
                project_id=project_id,
                slide_index=1,
                analysis_json=_make_qa_output_json(True, [issue]),
                prepared_context=_prepare_analysis_context(tools, project_id),
            )


class TestVisualQAServiceFixPreservation:
    def test_fix_preserves_images(self) -> None:
        """수정 시 기존 spec 의 images 가 보존된다."""
        svc = VisualQAService()

        # 기존 spec 에 images 포함 (slide_type='title' → SimpleSlideSpecOutput 경로)
        spec_with_images = PptxSlideSpec(
            slide_type="title",
            background_color="#1a1a2e",
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
                        ),
                    ],
                ),
            ],
            shapes=[],
            images=[
                PptxImage(
                    left_px=0,
                    top_px=0,
                    width_px=1280,
                    height_px=720,
                    src="images/bg.png",
                ),
            ],
        )

        result = svc.ingest_fix(
            _make_fix_output_json(),
            spec_with_images,
            [
                {
                    "issue_type": "text_truncation",
                    "element_type": "textbox",
                    "element_index": 0,
                }
            ],
        )
        assert result is not None
        assert len(result.images) == 1
        assert result.images[0].src == "images/bg.png"

    def test_fix_rejects_z_index_change_without_layering_issue(self) -> None:
        current = replace(
            _make_simple_spec("원문"),
            speaker_notes="발표 노트",
            textboxes=[replace(_make_simple_spec("원문").textboxes[0], z_index=1)],
        )
        result = VisualQAService().ingest_fix(
            _patch_json(
                {
                    "element_type": "textbox",
                    "element_index": 0,
                    "field": "z_index",
                    "value": 9,
                }
            ),
            current,
        )

        assert result is None

    def test_layering_fix_can_change_z_index_but_preserves_content(self) -> None:
        current = replace(
            _make_simple_spec("원문"),
            speaker_notes="발표 노트",
            textboxes=[replace(_make_simple_spec("원문").textboxes[0], z_index=1)],
        )
        result = VisualQAService().ingest_fix(
            _patch_json(
                {
                    "element_type": "textbox",
                    "element_index": 0,
                    "field": "z_index",
                    "value": 9,
                }
            ),
            current,
            [
                {
                    "issue_type": "wrong_z_order",
                    "element_type": "textbox",
                    "element_index": 0,
                }
            ],
        )

        assert result is not None
        assert result.textboxes[0].z_index == 9
        assert result.textboxes[0].paragraphs[0].runs[0].text == "원문"
        assert result.speaker_notes == "발표 노트"

    def test_fix_rejects_content_change(self) -> None:
        current = _make_simple_spec("원문")
        result = VisualQAService().ingest_fix(
            '{"operations":[{"element_type":"textbox","element_index":0,'
            '"field":"text","value":"변조된 문구"}]}',
            current,
            [{"issue_type": "overlap"}],
        )

        assert result is None

    def test_fix_rejects_changes_to_unmentioned_element(self) -> None:
        first = _make_simple_spec("첫째").textboxes[0]
        second = replace(
            first,
            top_px=140,
            paragraphs=_make_simple_spec("둘째").textboxes[0].paragraphs,
        )
        current = replace(_make_simple_spec("첫째"), textboxes=[first, second])
        result = VisualQAService().ingest_fix(
            _patch_json(
                {
                    "element_type": "textbox",
                    "element_index": 1,
                    "field": "top_px",
                    "value": 200,
                }
            ),
            current,
            [
                {
                    "issue_type": "misalignment",
                    "element_type": "textbox",
                    "element_index": 0,
                }
            ],
        )

        assert result is None

    @pytest.mark.parametrize(
        ("issue_type", "field_name", "value"),
        [
            ("small_font", "font_size_pt", 36),
            ("contrast", "color", "#ffffff"),
        ],
    )
    def test_fix_allows_only_matching_run_style(
        self, issue_type: str, field_name: str, value: object
    ) -> None:
        current = _make_simple_spec()
        result = VisualQAService().ingest_fix(
            _run_patch(field_name, value),
            current,
            [
                {
                    "issue_type": issue_type,
                    "element_type": "textbox",
                    "element_index": 0,
                }
            ],
        )

        assert result is not None
        assert getattr(result.textboxes[0].paragraphs[0].runs[0], field_name) == value

    @pytest.mark.parametrize(
        ("issue_type", "field_name", "value"),
        [
            ("small_font", "color", "#ffffff"),
            ("contrast", "font_size_pt", 36),
        ],
    )
    def test_fix_rejects_unrelated_run_style(
        self, issue_type: str, field_name: str, value: object
    ) -> None:
        current = _make_simple_spec()
        result = VisualQAService().ingest_fix(
            _run_patch(field_name, value),
            current,
            [
                {
                    "issue_type": issue_type,
                    "element_type": "textbox",
                    "element_index": 0,
                }
            ],
        )

        assert result is None


@pytest.mark.parametrize(
    "issue_type",
    [
        "text_truncation",
        "overlap",
        "overflow",
        "contrast",
        "misalignment",
        "inconsistent_font_size",
        "inconsistent_spacing",
        "wrong_vertical_alignment",
        "arrow_disconnected",
        "zero_gap",
        "small_font",
        "insufficient_padding",
        "content_too_sparse",
        "content_too_dense",
        "unbalanced_spacing",
        "inconsistent_padding",
        "label_intrusion",
        "decoration_overlap",
        "arrow_through_card",
        "orphan_label_no_arrow",
        "label_line_overlap",
        "hidden_decorative_strip",
        "wrong_z_order",
    ],
)
def test_visual_qa_issue_valid_types(issue_type: str) -> None:
    issue = VisualQAIssue(
        issue_type=issue_type,
        severity="medium",
        element_type="textbox",
        element_index=0,
        description="test",
        suggested_fix="test",
    )
    assert issue.issue_type == issue_type
