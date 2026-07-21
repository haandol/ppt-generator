"""Visual QA service 테스트: prepare/ingest + 스크린샷 캡처(Playwright mock).

LLM 호출은 클라이언트로 오프로딩되었으므로 서버는 스크린샷 캡처(결정론적)와
prepare(태스크 조립)/ingest(클라이언트 JSON 검증·후처리)만 담당한다. 이 파일은
그 세 지점을 검증한다:
  - capture_screenshots — Playwright mock
  - prepare_analysis / ingest_analysis — 이슈 감지
  - prepare_fix / ingest_fix — 수정 spec 검증·정합화
"""

from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic
from unittest.mock import MagicMock, patch

import pytest

from ppt_generator.interfaces.llm_output_models import (
    ParagraphOutput,
    SimpleSlideSpecOutput,
    TextBoxOutput,
    TextRunOutput,
    VisualQAIssue,
    VisualQAOutput,
)
from ppt_generator.interfaces.schemas import (
    PptxImage,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
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
    """클라이언트가 생성했을 법한 수정 spec JSON 을 조립한다 (ingest_fix 입력).

    slide_type != "content" 슬라이드는 SimpleSlideSpecOutput 을 사용하므로
    grid_layout/design_doc 없이 textbox 만으로 유효하다.
    """
    output = SimpleSlideSpecOutput(
        background_color="#1a1a2e",
        textboxes=[
            TextBoxOutput(
                left_px=40,
                top_px=40,
                width_px=700,
                height_px=60,
                paragraphs=[
                    ParagraphOutput(
                        runs=[TextRunOutput(text="테스트", font_size_pt=28, bold=True)]
                    ),
                ],
            ),
        ],
        shapes=[],
    )
    return output.model_dump_json()


def _make_simple_spec(title: str = "테스트") -> PptxSlideSpec:
    """slide_type='title' 인 spec — ingest_fix 가 SimpleSlideSpecOutput 을 쓰게 한다."""
    return replace(_make_spec(title), slide_type="title")


class TestVisualQAServiceCapture:
    """capture_screenshots 테스트 (Playwright mock)."""

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
        """이슈 없는 분석 결과 검증."""
        svc = VisualQAService()
        result = svc.ingest_analysis(_make_qa_output_json(has_issues=False))
        assert result.has_issues is False
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
            _make_qa_output_json(has_issues=True, issues=issues)
        )
        assert result.has_issues is True
        assert len(result.issues) == 1
        assert result.issues[0].issue_type == "text_truncation"


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
        result = svc.ingest_fix(_make_fix_output_json(), _make_simple_spec())
        assert result is not None
        assert isinstance(result, PptxSlideSpec)
        assert result.textboxes[0].width_px == 700

    def test_fix_failure_returns_none(self) -> None:
        """수정 실패(잘못된 JSON) 시 None 반환."""
        svc = VisualQAService()
        result = svc.ingest_fix("{ not valid json", _make_simple_spec())
        assert result is None

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

        result = svc.ingest_fix(_make_fix_output_json(), spec_with_images)
        assert result is not None
        assert len(result.images) == 1
        assert result.images[0].src == "images/bg.png"


class TestVisualQAModels:
    """Pydantic 모델 테스트."""

    def test_visual_qa_output_no_issues(self) -> None:
        output = VisualQAOutput(has_issues=False, issues=[], overall_quality="good")
        assert output.has_issues is False

    def test_visual_qa_output_with_issues(self) -> None:
        issue = VisualQAIssue(
            issue_type="text_truncation",
            severity="high",
            element_type="textbox",
            element_index=0,
            description="단어 중간 줄바꿈",
            suggested_fix="텍스트박스 너비 확장",
        )
        output = VisualQAOutput(
            has_issues=True,
            issues=[issue],
            overall_quality="needs_improvement",
        )
        assert output.has_issues is True
        assert len(output.issues) == 1
        assert output.issues[0].issue_type == "text_truncation"

    def test_visual_qa_issue_valid_types(self) -> None:
        for issue_type in (
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
        ):
            issue = VisualQAIssue(
                issue_type=issue_type,
                severity="medium",
                element_type="textbox",
                element_index=0,
                description="test",
                suggested_fix="test",
            )
            assert issue.issue_type == issue_type
