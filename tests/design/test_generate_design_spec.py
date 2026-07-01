"""design spec 생성 도구 테스트 (prepare/ingest 오프로딩).

배치 생성이 클라이언트로 옮겨졌다. 서버는 슬라이드별 prepare/ingest 와 draft
prepare/ingest, finalize 를 제공한다. 이 파일은 그 서버 도구들의 파일 저장/보정/lint
오케스트레이션을 검증한다. LLM 병렬 루프는 클라이언트 책임이므로 테스트 대상이 아니다.

배치 흐름을 재현하기 위해 클라이언트가 하는 일을 `_run_batch` 헬퍼로 흉내낸다:
  prepare_design_doc_draft → (skip 아니면) ingest_design_doc_draft →
  각 슬라이드 prepare_design_slide + ingest_design_slide → finalize_design_spec.
mock design_service.ingest_slide 는 고정 (spec, overflow) 를 돌려주므로, ingest 에
넘기는 spec_json 은 무의미하다 — "{}" 를 넘긴다.
"""

from __future__ import annotations

import json
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


def _run(result):
    """서버 도구는 동기 함수라 str 을 바로 반환한다. 호출부 형태를 유지하기 위한 패스스루."""
    return result


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


def _run_batch(
    tools: dict,
    *,
    project_id: str = "",
    outline_json: str = "",
    total_slides: int = 0,
    slide_indices: str = "",
    color_theme: str = "dark",
) -> dict:
    """클라이언트 배치 흐름을 재현한다.

    prepare_design_doc_draft(→ skip 아니면 ingest) 를 한 번 돌리고, 대상 슬라이드마다
    prepare_design_slide + ingest_design_slide 를 호출한 뒤 finalize_design_spec 로
    마무리한다. 슬라이드별 ingest 결과를 모아 예전 배치 응답과 유사한 형태로 집계한다.

    slide_indices 가 있으면 그 1-based 인덱스들만 (draft 는 인덱스 1 이 포함될 때만)
    처리한다. slide_indices 가 비어 있으면 outline 의 모든 슬라이드를 처리한다.
    """
    if not outline_json and not project_id:
        raise ValueError("Either outline_json or project_id must be provided.")

    project_service = tools["_project_service"]

    # 프로젝트 id 를 먼저 확정한다 (빈 값이면 UUID 자동 생성). 클라이언트가
    # outline_json 을 넘긴 경우, 실제 워크플로우처럼 outline 을 프로젝트에 저장해
    # ingest_design_slide 가 프로젝트에서 outline 을 로드할 수 있게 한다.
    resolved_project_id, proj_dir = project_service.resolve_project_dir(project_id)
    if outline_json:
        project_service.save_outline(proj_dir, outline_json)

    outline = _parse_outline(
        tools, project_id=resolved_project_id, outline_json=outline_json
    )
    n = len(outline.slides)
    if total_slides <= 0:
        total_slides = n
    if total_slides != n:
        raise ValueError(
            f"total_slides ({total_slides}) does not match outline slide count ({n})"
        )

    if slide_indices.strip():
        indices = [int(x) for x in slide_indices.split(",") if x.strip()]
        for i in indices:
            if i < 1 or i > n:
                raise ValueError(f"Invalid slide_index: {i} (valid range: 1-{n})")
    else:
        indices = list(range(1, n + 1))

    # DESIGN.md 초안: 인덱스 1 이 포함될 때만 (부분 재생성은 초안 재생성 안 함).
    if 1 in indices:
        draft_raw = _run(
            tools["prepare_design_doc_draft"](
                project_id=resolved_project_id,
                color_theme=color_theme,
            )
        )
        draft = json.loads(draft_raw)
        if not draft.get("skip"):
            _run(
                tools["ingest_design_doc_draft"](
                    project_id=resolved_project_id,
                    draft_json="{}",
                    color_theme=color_theme,
                )
            )

    results: list[dict] = []
    all_overflow: list[dict] = []
    for i in indices:
        _run(
            tools["prepare_design_slide"](
                project_id=resolved_project_id,
                slide_index=i,
                total_slides=total_slides,
                color_theme=color_theme,
            )
        )
        try:
            ing_raw = _run(
                tools["ingest_design_slide"](
                    project_id=resolved_project_id,
                    slide_index=i,
                    spec_json="{}",
                    color_theme=color_theme,
                )
            )
            ing = json.loads(ing_raw)
            results.append(ing)
            all_overflow.extend(ing.get("overflow", []))
        except Exception as exc:  # noqa: BLE001 — 배치 부분 실패 재현
            results.append({"slide_index": i, "status": "error", "error": str(exc)})

    fin_raw = _run(
        tools["finalize_design_spec"](
            project_id=resolved_project_id,
            overflow_json=json.dumps(all_overflow) if all_overflow else "",
        )
    )
    fin = json.loads(fin_raw)

    success = [r for r in results if r.get("status") == "success"]
    errors = [r for r in results if r.get("status") == "error"]
    return {
        "project_id": resolved_project_id,
        "total_slides": total_slides,
        "success_count": len(success),
        "error_count": len(errors),
        "slide_count": fin.get("slide_count", 0),
        "results": results,
        "finalize": fin,
        "slides_html_path": fin.get("slides_html_path"),
    }


def _parse_outline(
    tools: dict, *, project_id: str, outline_json: str
) -> OutlineResponse:
    """배치 헬퍼에서 슬라이드 수/인덱스 계산을 위해 outline 을 로드한다."""
    from ppt_generator.interfaces.utils import parse_outline_json

    if outline_json:
        return parse_outline_json(outline_json)
    project_service = tools["_project_service"]
    _, proj_dir = project_service.resolve_project_dir(project_id)
    return parse_outline_json(project_service.load_outline(proj_dir))


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
        result = _run_batch(mcp_tools, project_id=project_id)
        assert result["total_slides"] == 3
        assert result["success_count"] == 3
        assert result["project_id"] == project_id

    def test_auto_calculates_total_slides(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project_with_outline(
            tmp_path, monkeypatch, num_slides=4
        )
        result = _run_batch(mcp_tools, project_id=project_id, total_slides=0)
        assert result["total_slides"] == 4
        assert result["success_count"] == 4

    def test_no_outline_no_project_raises(self, mcp_tools: dict) -> None:
        with pytest.raises(ValueError, match="Either outline_json or project_id"):
            _run_batch(mcp_tools)


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
        result = _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
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
        result = _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )
        for i, r in enumerate(result["results"]):
            assert r["slide_index"] == i + 1
            assert r["status"] == "success"
            assert r["slide_file"] == f"slide_{i + 1:02d}.json"

    def test_batch_creates_design_doc_md(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )
        # DESIGN.md 가 디자인 의도의 단일 소스.
        design_doc_path = tmp_path / project_id / "DESIGN.md"
        assert design_doc_path.exists()

    def test_existing_design_md_not_regenerated_and_directives_injected(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """사람이 편집한 DESIGN.md 는 덮어쓰지 않고(초안 ingest 스킵), 톤+페이지
        요청이 prepare_design_slide 프롬프트에 design_directives 로 주입된다."""
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
        _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )

        # 기존 DESIGN.md 를 덮어쓰지 않았으므로 draft ingest(저장) 호출 없음.
        assert not design_service.ingest_design_doc_draft.called

        # 슬라이드별 directives 주입 확인 (prepare_slide 에 전달됨).
        directives_by_index = {
            call.kwargs["slide_index"]: call.kwargs.get("design_directives", "")
            for call in design_service.prepare_slide.call_args_list
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
            _run_batch(
                mcp_tools,
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=3,
                project_id="batch-proj",
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
        result = _run_batch(
            mcp_tools,
            outline_json=single_outline,
            total_slides=1,
            project_id=project_id,
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
        result = _run_batch(
            mcp_tools,
            outline_json=single_outline,
            total_slides=1,
        )
        assert result["project_id"]
        assert len(result["project_id"]) == 36  # UUID

    def test_batch_partial_failure(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        design_service = mcp_tools["_design_service"]

        # ingest_slide 는 (spec, overflow) 를 반환. 슬라이드 3 에서만 실패시킨다.
        # ingest_design_slide 는 outline 로딩 후 순서대로 호출되므로 호출 카운트로
        # 3번째(slide_index=3) 를 식별한다.
        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise RuntimeError("LLM 호출 실패")
            return (make_slide_spec("생성됨"), [])

        design_service.ingest_slide.side_effect = side_effect

        result = _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )
        assert result["success_count"] == 4
        assert result["error_count"] == 1

        failed = [r for r in result["results"] if r["status"] == "error"]
        assert len(failed) == 1
        assert failed[0]["slide_index"] == 3
        assert "LLM 호출 실패" in failed[0]["error"]

        succeeded = [r for r in result["results"] if r["status"] == "success"]
        assert len(succeeded) == 4

    def test_batch_with_slide_indices(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )

        design_service = mcp_tools["_design_service"]
        design_service.ingest_slide.reset_mock()

        result = _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="2,4",
        )
        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert len(result["results"]) == 2
        assert [r["slide_index"] for r in result["results"]] == [2, 4]

    def test_batch_slide_indices_with_index_one(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)
        result = _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="1,3,5",
        )
        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert len(result["results"]) == 3
        assert [r["slide_index"] for r in result["results"]] == [1, 3, 5]

        design_doc_path = tmp_path / project_id / "DESIGN.md"
        assert design_doc_path.exists()
        # 인덱스 1 이 포함되므로 초안을 ingest(저장)한다.
        assert mcp_tools["_design_service"].ingest_design_doc_draft.called

    def test_batch_slide_indices_without_index_zero(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )

        design_service = mcp_tools["_design_service"]
        design_service.ingest_design_doc_draft.reset_mock()

        result = _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="3,4",
        )
        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert len(result["results"]) == 2
        # 인덱스 1 이 없으므로 초안을 다시 ingest 하지 않는다.
        assert not design_service.ingest_design_doc_draft.called

    def test_batch_single_index(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )

        design_service = mcp_tools["_design_service"]
        design_service.ingest_slide.reset_mock()

        result = _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="3",
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
            _run_batch(
                mcp_tools,
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
                slide_indices="0,10",
            )

    def test_batch_enforces_background_color_from_design_summary(
        self, mcp_tools: dict, tmp_path: Path, monkeypatch
    ) -> None:
        """content 슬라이드 배경색이 design_summary.background_color 로 보정된다.

        보정 로직은 ingest_design_slide 의 서버 후처리(_enforce_background_color)에 있다.
        """
        project_id = self._setup_project(tmp_path, monkeypatch)

        design_service = mcp_tools["_design_service"]
        design_service.ingest_design_doc_draft.return_value = (
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
        design_service.ingest_slide.return_value = (wrong_bg_spec, [])

        _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
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

        # 클라이언트가 closing 을 background_color=None 으로 생성했다고 가정
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
        design_service.ingest_slide.return_value = (closing_spec, [])

        _run_batch(
            mcp_tools,
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
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

        # 실제 SlidesService 로 컨테이너 HTML 생성을 검증한다.
        design_service = MagicMock()
        design_service.prepare_design_doc_draft.return_value = {
            "system_prompt": "sys",
            "user_prompt": "usr",
        }
        design_service.prepare_slide.return_value = {
            "system_prompt": "sys",
            "user_prompt": "usr",
            "response_schema": {},
        }
        design_service.ingest_slide.return_value = (make_slide_spec("생성됨"), [])
        _summary = {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        }
        design_service.ingest_design_doc_draft.return_value = (_summary, "", [])

        from ppt_generator.tools.slides.service import SlidesService

        slides_service = SlidesService()
        project_service = ProjectService()

        register_design_tools(
            mcp,
            project_service,
            design_service=design_service,
            slides_service=slides_service,
        )
        tools["_project_service"] = project_service

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

        result = _run_batch(
            tools,
            outline_json=outline_3,
            total_slides=3,
            project_id=project_id,
        )
        assert result["success_count"] == 3
        assert result["slides_html_path"]

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


class TestIngestDesignDocDraft:
    """DesignService.ingest_design_doc_draft — 클라이언트가 생성한 DESIGN.md 초안
    JSON(테마 + 톤 + 선별적 페이지 요청) 파싱 견고성 검증 (design/0018).

    LLM 호출 없이 순수 파싱만 하므로 DesignService() 를 직접 인스턴스화해 검증한다.
    """

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
        svc = DesignService()
        summary, tone, page_requests = svc.ingest_design_doc_draft(payload)

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
        svc = DesignService()
        summary, tone, page_requests = svc.ingest_design_doc_draft(payload)
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
        svc = DesignService()
        _, _, page_requests = svc.ingest_design_doc_draft(payload)
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
        svc = DesignService()
        _, _, page_requests = svc.ingest_design_doc_draft(payload)
        # 빈 request 와 garbage 는 빠지고, 번호 비정수 1건만 number=None 으로 남는다.
        assert len(page_requests) == 1
        assert page_requests[0].number is None
        assert page_requests[0].text == "유효"


class TestIngestSlideTypeInvariance:
    """동작 불변: ingest_slide 는 응답 모델을 정규화된 slide_type 으로 고르되,
    최종 spec 에는 전달받은 원본 slide_type(None/"" 포함)을 그대로 저장한다.

    오프로딩 이전 generate_single_slide 는 모델 선택에 `slide_type or "content"` 를
    쓰고 `replace(spec, slide_type=slide_outline.slide_type)` 로 원본을 저장했다.
    """

    # content 모델은 grid/cell/design_doc 이 Required.
    _CONTENT_SPEC_JSON = json.dumps(
        {
            "grid_layout": {
                "regions": ["content"],
                "content_columns": 1,
                "content_rows": 1,
            },
            "cell_assignment": {"cells": []},
            "design_doc": {"topic": "t", "layout_summary": "s", "layout": []},
            "background_color": "#101010",
            "speaker_notes": "",
            "textboxes": [],
            "shapes": [],
            "overflow": [],
        }
    )
    # simple 모델은 grid/cell/design_doc 이 Optional.
    _SIMPLE_SPEC_JSON = json.dumps(
        {
            "grid_layout": None,
            "cell_assignment": None,
            "design_doc": None,
            "background_color": "#101010",
            "speaker_notes": "",
            "textboxes": [],
            "shapes": [],
            "overflow": [],
        }
    )

    def test_content_slide_type_preserved(self) -> None:
        spec, _ = DesignService().ingest_slide(
            self._CONTENT_SPEC_JSON, slide_type="content"
        )
        assert spec.slide_type == "content"

    def test_none_slide_type_preserved_not_normalized(self) -> None:
        # 원본이 None 이면 저장도 None (정규화된 "content" 로 덮어쓰지 않는다).
        # 단, 모델 선택은 `None or "content"` → Content 모델이라 content 페이로드가 필요.
        spec, _ = DesignService().ingest_slide(self._CONTENT_SPEC_JSON, slide_type=None)
        assert spec.slide_type is None

    def test_empty_slide_type_preserved(self) -> None:
        # `"" or "content"` → Content 모델 선택.
        spec, _ = DesignService().ingest_slide(self._CONTENT_SPEC_JSON, slide_type="")
        assert spec.slide_type == ""

    def test_title_slide_type_preserved(self) -> None:
        spec, _ = DesignService().ingest_slide(
            self._SIMPLE_SPEC_JSON, slide_type="title"
        )
        assert spec.slide_type == "title"
