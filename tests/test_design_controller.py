"""design controller 테스트: modify_design_spec, generate_slides_design_spec 검증."""

import asyncio
import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.interfaces.spec_utils import design_spec_to_json  # noqa: F401 — 하위 호환 확인용
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.project.service import ProjectService


def _make_slide_spec(title: str = "테스트") -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=[
            PptxTextBox(
                left_px=40, top_px=40, width_px=600, height_px=60,
                paragraphs=[
                    PptxParagraph(runs=[PptxTextRun(text=title, font_size_pt=32, bold=True)]),
                ],
            ),
        ],
        shapes=[],
        images=[],
        speaker_notes="",
    )


def _make_design_spec(n: int = 3) -> DesignSpec:
    return DesignSpec(slides=[_make_slide_spec(f"슬라이드 {i+1}") for i in range(n)])


SAMPLE_OUTLINE_JSON = json.dumps(
    {"slides": [{"title": "새 슬라이드", "content_summary": "내용", "component_hint": "bullets", "speaker_notes": ""}]},
    ensure_ascii=False,
)


@pytest.fixture()
def project_service() -> ProjectService:
    return ProjectService()


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    d = tmp_path / "test_project"
    d.mkdir()
    meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
    (d / "project.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return d


@pytest.fixture()
def project_with_design_spec(project_service: ProjectService, project_dir: Path) -> tuple[str, Path]:
    spec = _make_design_spec(3)
    project_service.save_design_spec(project_dir, spec)
    return project_dir.name, project_dir


@pytest.fixture()
def mcp_tools(project_service: ProjectService) -> dict:
    """MCP 도구를 등록하고 도구 함수들을 반환한다."""
    mcp = MagicMock()
    tools = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func
        return decorator

    mcp.tool = tool_decorator

    design_service = MagicMock()
    design_service.generate_single_slide.return_value = _make_slide_spec("새로 생성됨")
    design_service.extract_design_summary.return_value = {"background_color": "#1a1a2e", "text_colors": ["#ffffff"]}
    design_service.generate_design_summary.return_value = {"background_color": "#1a1a2e", "text_colors": ["#ffffff"], "title_font_pt": 32, "body_font_pt": 18, "card_fills": [], "card_borders": []}

    design_service_factory = lambda: design_service  # noqa: E731

    register_design_tools(
        mcp, design_service, project_service,
        design_service_factory=design_service_factory,
    )
    tools["_design_service"] = design_service
    tools["_design_service_factory"] = design_service_factory
    tools["_project_service"] = project_service
    return tools


class TestModifyDesignSpec:
    """modify_design_spec 도구 테스트."""

    def test_add_slide_at_end(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        # tmp_path 아래에 프로젝트 디렉토리 심볼릭 링크 또는 복사
        # resolve_project_dir가 PPT_GENERATOR_HOME / project_id 를 반환하므로 monkeypatch
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="add",
            slide_index=-1,
            outline_json=SAMPLE_OUTLINE_JSON,
        ))
        assert result["slide_count"] == 4
        assert result["project_id"] == project_id

    def test_add_slide_at_index(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="add",
            slide_index=1,
            outline_json=SAMPLE_OUTLINE_JSON,
        ))
        assert result["slide_count"] == 4

    def test_update_slide(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="update",
            slide_index=0,
            outline_json=SAMPLE_OUTLINE_JSON,
        ))
        assert result["slide_count"] == 3  # 슬라이드 수 변경 없음

    def test_delete_slide(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        result = json.loads(mcp_tools["modify_design_spec"](
            project_id=project_id,
            action="delete",
            slide_index=1,
        ))
        assert result["slide_count"] == 2

    def test_invalid_action_raises(self, mcp_tools: dict) -> None:
        with pytest.raises(ValueError, match="action은"):
            mcp_tools["modify_design_spec"](
                project_id="any",
                action="invalid",
            )

    def test_delete_invalid_index_raises(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        with pytest.raises(ValueError, match="유효하지 않은 slide_index"):
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="delete",
                slide_index=99,
            )

    def test_add_without_outline_raises(self, mcp_tools: dict, project_with_design_spec: tuple, monkeypatch, tmp_path: Path) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        project_id, project_dir = project_with_design_spec
        import shutil
        dest = tmp_path / project_id
        if not dest.exists():
            shutil.copytree(project_dir, dest)

        with pytest.raises(ValueError, match="outline_json이 필수"):
            mcp_tools["modify_design_spec"](
                project_id=project_id,
                action="add",
            )


class TestGenerateSlidesDesignSpecFromProject:
    """generate_slides_design_spec project_id 기반 파일 로드 테스트."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def _setup_project_with_outline(self, tmp_path: Path, monkeypatch, num_slides: int = 5) -> str:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        proj_dir = tmp_path / "batch-file-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "테스트", "num_slides": num_slides, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        outline = {
            "slides": [
                {"title": f"슬라이드 {i+1}", "content_summary": f"내용 {i+1}", "component_hint": "bullets", "speaker_notes": ""}
                for i in range(num_slides)
            ],
        }
        (proj_dir / "outline.json").write_text(json.dumps(outline, ensure_ascii=False), encoding="utf-8")
        return "batch-file-proj"

    def _setup_project_with_script(self, tmp_path: Path, monkeypatch, num_slides: int = 5) -> str:
        project_id = self._setup_project_with_outline(tmp_path, monkeypatch, num_slides)
        proj_dir = tmp_path / project_id
        script = {
            "slides": [
                {"title": f"스크립트 {i+1}", "content_summary": f"내용 {i+1}", "component_hint": "bullets", "speaker_notes": f"노트 {i+1}"}
                for i in range(num_slides)
            ],
        }
        (proj_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
        return project_id

    def test_load_from_outline_file(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """project_id만 제공하면 outline.json에서 로드한다."""
        project_id = self._setup_project_with_outline(tmp_path, monkeypatch, num_slides=3)

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            project_id=project_id,
        )))

        assert result["total_slides"] == 3
        assert result["success_count"] == 3
        assert result["project_id"] == project_id

    def test_load_from_script_file(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """script.json이 있으면 우선 로드한다."""
        project_id = self._setup_project_with_script(tmp_path, monkeypatch, num_slides=3)

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            project_id=project_id,
        )))

        assert result["total_slides"] == 3
        assert result["success_count"] == 3

    def test_auto_calculates_total_slides(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """total_slides=0이면 자동 계산한다."""
        project_id = self._setup_project_with_outline(tmp_path, monkeypatch, num_slides=4)

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            project_id=project_id,
            total_slides=0,
        )))

        assert result["total_slides"] == 4
        assert result["success_count"] == 4

    def test_no_outline_no_project_raises(self, mcp_tools: dict) -> None:
        """outline_json도 project_id도 없으면 ValueError."""
        with pytest.raises(ValueError, match="outline_json 또는 project_id"):
            self._run(mcp_tools["generate_slides_design_spec"]())


SAMPLE_BATCH_OUTLINE_JSON = json.dumps(
    {
        "slides": [
            {"title": f"슬라이드 {i+1}", "content_summary": f"내용 {i+1}", "component_hint": "bullets", "speaker_notes": ""}
            for i in range(5)
        ],
    },
    ensure_ascii=False,
)


class TestGenerateSlidesDesignSpec:
    """generate_slides_design_spec 배치 도구 테스트."""

    def _setup_project(self, tmp_path: Path, monkeypatch) -> str:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        proj_dir = tmp_path / "batch-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return "batch-proj"

    @staticmethod
    def _run(coro):
        """async 도구 함수를 동기 테스트에서 실행하는 헬퍼."""
        return asyncio.run(coro)

    def test_batch_generates_all_slides(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )))

        assert result["total_slides"] == 5
        assert result["success_count"] == 5
        assert result["error_count"] == 0
        assert result["slide_count"] == 5
        assert result["project_id"] == project_id
        assert len(result["results"]) == 5

    def test_batch_results_ordered_by_index(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )))

        for i, r in enumerate(result["results"]):
            assert r["slide_index"] == i
            assert r["status"] == "success"
            assert r["slide_file"] == f"slide_{i + 1:02d}.json"

    def test_batch_creates_design_summary(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        project_id = self._setup_project(tmp_path, monkeypatch)

        self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        ))

        summary_path = tmp_path / project_id / "design_spec" / "design_summary.json"
        assert summary_path.exists()

    def test_batch_mismatched_total_slides_raises(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        self._setup_project(tmp_path, monkeypatch)

        with pytest.raises(ValueError, match="일치하지 않습니다"):
            self._run(mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=3,  # outline에는 5개
                project_id="batch-proj",
            ))

    def test_batch_single_slide(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """슬라이드 1장짜리 배치도 정상 동작."""
        project_id = self._setup_project(tmp_path, monkeypatch)
        single_outline = json.dumps(
            {"slides": [{"title": "단일", "content_summary": "내용", "component_hint": "bullets", "speaker_notes": ""}]},
            ensure_ascii=False,
        )

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=single_outline,
            total_slides=1,
            project_id=project_id,
        )))

        assert result["success_count"] == 1
        assert result["error_count"] == 0
        assert result["slide_count"] == 1

    def test_batch_auto_generates_project_id(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        single_outline = json.dumps(
            {"slides": [{"title": "단일", "content_summary": "내용", "component_hint": "bullets", "speaker_notes": ""}]},
            ensure_ascii=False,
        )

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=single_outline,
            total_slides=1,
        )))

        assert result["project_id"]
        assert len(result["project_id"]) == 36  # UUID

    def test_batch_partial_failure(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """일부 슬라이드 실패 시 나머지는 정상 저장되고 에러가 보고된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        design_service = mcp_tools["_design_service"]
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # 3번째 호출(slide_index=2)에서 실패
            if kwargs.get("slide_index") == 3:
                raise RuntimeError("LLM 호출 실패")
            return _make_slide_spec("생성됨")

        design_service.generate_single_slide.side_effect = side_effect

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        )))

        assert result["success_count"] == 4
        assert result["error_count"] == 1

        # 실패한 슬라이드 확인
        failed = [r for r in result["results"] if r["status"] == "error"]
        assert len(failed) == 1
        assert failed[0]["slide_index"] == 2
        assert "LLM 호출 실패" in failed[0]["error"]

        # 성공한 슬라이드 확인
        succeeded = [r for r in result["results"] if r["status"] == "success"]
        assert len(succeeded) == 4

    def test_batch_respects_parallel_limit(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """동시 실행 스레드가 DESIGN_SPEC_PARALLEL 값을 초과하지 않는지 검증."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # DESIGN_SPEC_PARALLEL을 2로 제한
        import ppt_generator.tools.design.controller as ctrl_module
        monkeypatch.setattr(ctrl_module, "DESIGN_SPEC_PARALLEL", 2)

        # 10장짜리 아웃라인 (모든 슬라이드 병렬 생성)
        outline_10 = json.dumps(
            {
                "slides": [
                    {"title": f"슬라이드 {i+1}", "content_summary": f"내용 {i+1}", "component_hint": "bullets", "speaker_notes": ""}
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
            time.sleep(0.05)  # 병렬 스레드가 겹칠 수 있도록 약간의 지연
            with lock:
                current_concurrent -= 1
            return _make_slide_spec("생성됨")

        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.side_effect = slow_generate

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=outline_10,
            total_slides=10,
            project_id=project_id,
        )))

        assert result["success_count"] == 10
        assert result["error_count"] == 0
        # 모든 슬라이드가 병렬 생성되며, max_workers=2이므로 동시 최대 2를 초과하면 안 됨
        assert peak_concurrent <= 2, f"동시 실행 peak={peak_concurrent}, 제한=2"

    def test_batch_reports_progress(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """ctx.report_progress가 각 슬라이드 완료 시 호출되는지 검증."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        from unittest.mock import AsyncMock
        ctx = AsyncMock()

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            ctx=ctx,
        )))

        assert result["success_count"] == 5
        # report_progress: design_summary 생성 1회 + 슬라이드 5회 = 총 6회
        assert ctx.report_progress.await_count == 6
        # 마지막 호출의 progress 값은 target_count와 같아야 함
        last_call = ctx.report_progress.await_args
        assert last_call[0][0] == 5  # progress
        assert last_call[0][1] == 5  # total

    def test_batch_with_slide_indices(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """slide_indices로 특정 인덱스만 생성한다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # 먼저 전체 생성하여 design_summary 확보
        self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        ))

        # design_service 호출 카운터 리셋
        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.reset_mock()

        # 특정 인덱스만 재생성
        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="1,3",
        )))

        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert len(result["results"]) == 2
        indices = [r["slide_index"] for r in result["results"]]
        assert indices == [1, 3]

    def test_batch_slide_indices_with_index_zero(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """slide_indices에 인덱스 0 포함 시 design_summary가 없으면 LLM으로 사전 생성 후 전체 병렬."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="0,2,4",
        )))

        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert len(result["results"]) == 3
        indices = [r["slide_index"] for r in result["results"]]
        assert indices == [0, 2, 4]

        # design_summary.json이 생성되었는지 확인
        summary_path = tmp_path / project_id / "design_spec" / "design_summary.json"
        assert summary_path.exists()

        # design_service.generate_design_summary가 호출되었는지 확인 (LLM으로 사전 생성)
        design_service = mcp_tools["_design_service"]
        assert design_service.generate_design_summary.called

    def test_batch_slide_indices_without_index_zero(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """slide_indices에 인덱스 0 미포함 시 기존 design_summary를 로드하여 전부 병렬 생성."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # 먼저 전체 생성하여 design_summary 확보
        self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        ))

        design_service = mcp_tools["_design_service"]
        design_service.generate_design_summary.reset_mock()

        # 인덱스 0 없이 재생성
        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="2,3",
        )))

        assert result["success_count"] == 2
        assert result["error_count"] == 0
        assert len(result["results"]) == 2

        # design_summary가 이미 존재하므로 generate_design_summary가 호출되지 않아야 함
        assert not design_service.generate_design_summary.called

    def test_batch_single_index(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """단일 인덱스만 지정하여 1장 생성."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        # 먼저 전체 생성하여 design_summary 확보
        self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        ))

        design_service = mcp_tools["_design_service"]
        design_service.generate_single_slide.reset_mock()

        result = json.loads(self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
            slide_indices="2",
        )))

        assert result["success_count"] == 1
        assert result["error_count"] == 0
        assert len(result["results"]) == 1
        assert result["results"][0]["slide_index"] == 2
        assert result["results"][0]["slide_file"] == "slide_03.json"

    def test_batch_slide_indices_invalid_raises(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """유효하지 않은 slide_index는 ValueError를 발생시킨다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        with pytest.raises(ValueError, match="유효하지 않은 slide_index"):
            self._run(mcp_tools["generate_slides_design_spec"](
                outline_json=SAMPLE_BATCH_OUTLINE_JSON,
                total_slides=5,
                project_id=project_id,
                slide_indices="0,10",
            ))

    def test_batch_enforces_background_color_from_design_summary(self, mcp_tools: dict, tmp_path: Path, monkeypatch) -> None:
        """content 슬라이드의 배경색이 design_summary의 background_color로 강제 보정된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        design_service = mcp_tools["_design_service"]
        # design_summary에는 #1a1a2e를 반환하지만 슬라이드 스펙에는 #ffffff를 사용
        design_service.generate_design_summary.return_value = {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        }
        wrong_bg_spec = PptxSlideSpec(
            background_color="#ffffff",  # 잘못된 밝은 배경
            textboxes=[
                PptxTextBox(
                    left_px=40, top_px=40, width_px=600, height_px=60,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=32, bold=True)])],
                ),
            ],
            shapes=[], images=[], speaker_notes="",
            slide_type="content",
        )
        design_service.generate_single_slide.return_value = wrong_bg_spec

        self._run(mcp_tools["generate_slides_design_spec"](
            outline_json=SAMPLE_BATCH_OUTLINE_JSON,
            total_slides=5,
            project_id=project_id,
        ))

        # 저장된 스펙의 배경색이 design_summary 값으로 보정되었는지 확인
        project_service = mcp_tools["_project_service"]
        proj_dir = tmp_path / project_id
        for i in range(5):
            saved_spec = project_service.load_design_spec_slide(proj_dir, i)
            assert saved_spec.background_color == "#1a1a2e", (
                f"slide[{i}] 배경색이 보정되지 않음: {saved_spec.background_color}"
            )


class TestGenerateSlidesDesignSpecWithSlidesService:
    """slides_service가 제공될 때 slides.html 컨테이너 생성 테스트."""

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def _setup_project(self, tmp_path: Path, monkeypatch) -> str:
        import ppt_generator.tools.project.service as svc_module
        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)
        proj_dir = tmp_path / "slides-html-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )
        return "slides-html-proj"

    def test_generates_slides_html_container(self, tmp_path: Path, monkeypatch) -> None:
        """전체 슬라이드 생성 완료 시 slides.html 컨테이너가 자동 생성된다."""
        project_id = self._setup_project(tmp_path, monkeypatch)

        mcp = MagicMock()
        tools = {}

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func
            return decorator

        mcp.tool = tool_decorator

        design_service = MagicMock()
        design_service.generate_single_slide.return_value = _make_slide_spec("생성됨")
        design_service.generate_design_summary.return_value = {
            "background_color": "#1a1a2e", "text_colors": ["#ffffff"],
            "title_font_pt": 32, "body_font_pt": 18, "card_fills": [], "card_borders": [],
        }

        from ppt_generator.tools.slides.service import SlidesService
        slides_service = SlidesService()
        project_service = ProjectService()

        register_design_tools(
            mcp, design_service, project_service,
            slides_service=slides_service,
            design_service_factory=lambda: design_service,
        )

        outline_3 = json.dumps(
            {"slides": [
                {"title": f"슬라이드 {i+1}", "content_summary": f"내용 {i+1}", "component_hint": "bullets", "speaker_notes": ""}
                for i in range(3)
            ]},
            ensure_ascii=False,
        )

        result = json.loads(self._run(tools["generate_slides_design_spec"](
            outline_json=outline_3,
            total_slides=3,
            project_id=project_id,
        )))

        assert result["success_count"] == 3
        assert "slides_html_path" in result

        # slides.html 파일이 생성되었는지 확인
        slides_html_path = tmp_path / project_id / "slides.html"
        assert slides_html_path.exists()

        # 컨테이너 HTML에 iframe 참조가 포함되어 있는지 확인
        content = slides_html_path.read_text(encoding="utf-8")
        assert "slide_01.html" in content
        assert "slide_02.html" in content
        assert "slide_03.html" in content
