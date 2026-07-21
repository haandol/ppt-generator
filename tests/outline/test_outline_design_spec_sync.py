"""outline과 design_spec 불일치 시나리오 테스트.

imported 프로젝트에서 outline 없이 design_spec만 있는 경우,
add 반복 후 outline과 design_spec 수가 달라지는 경우,
delete/move 시 불일치 상태에서도 안전하게 동작하는지 검증한다.

오프로딩 리팩터 이후 modify_design_spec 단일 도구는 사라지고,
delete 는 delete_slide, add 는 prepare_slide_edit/ingest_slide_edit 쌍으로 나뉘었다.
move_slide 는 LLM 이 없어 그대로 유지된다. 서버가 수행하는 파일 이동/삭제/삽입/동기화
동작은 변경되지 않았으므로 그대로 검증한다.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock


from ppt_generator.interfaces.schemas import (
    DesignSpec,
)
from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.project.service import ProjectService

from _helpers import make_slide_spec as _make_slide_spec


def _register_tools(project_service: ProjectService) -> dict:
    mcp = MagicMock()
    tools: dict = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator

    # mock DesignService — prepare/ingest 오프로딩 형태.
    # ingest_slide 는 (spec, overflow) 를 반환한다. spec_json 내용은 무관하다.
    design_service = MagicMock()
    design_service.prepare_slide.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }
    design_service.ingest_slide.return_value = (_make_slide_spec("새로 생성됨"), [])

    slides_service = MagicMock()
    slides_service.render_single_slide_html.return_value = "<html>new slide</html>"

    register_design_tools(
        mcp,
        project_service,
        design_service=design_service,
        slides_service=slides_service,
    )
    tools["_project_service"] = project_service
    tools["_design_service"] = design_service
    return tools


def _add_slide(
    tools: dict,
    project_id: str,
    *,
    slide_index: int = -1,
    title: str = "추가 슬라이드",
    content_summary: str = "내용",
) -> dict:
    """prepare_slide_edit(add) + ingest_slide_edit(add) 쌍을 실행하고 ingest 결과를 반환한다.

    mock ingest_slide 가 고정 spec 을 반환하므로 spec_json 은 "{}" 로 충분하다.
    """
    prepared = json.loads(
        tools["prepare_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=slide_index,
            title=title,
            content_summary=content_summary,
        )
    )
    return json.loads(
        tools["ingest_slide_edit"](
            project_id=project_id,
            action="add",
            slide_index=slide_index,
            spec_json="{}",
            edit_context=prepared["edit_context"],
        )
    )


def _setup_imported_project(
    tmp_path: Path,
    monkeypatch,
    num_slides: int = 20,
) -> tuple[str, Path, ProjectService]:
    """outline/script이 없고 design_spec만 있는 imported 프로젝트를 생성한다."""
    import ppt_generator.tools.project.service as svc_module

    monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

    project_service = ProjectService()
    project_id = "imported-proj"
    project_dir = tmp_path / project_id
    project_dir.mkdir()

    meta = {
        "topic": "Imported",
        "num_slides": num_slides,
        "steps_completed": {"import": "2025-01-01"},
        "source": "imported",
    }
    (project_dir / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )

    # design_spec만 생성 (outline/script 없음)
    spec = DesignSpec(
        slides=[_make_slide_spec(f"슬라이드 {i + 1}") for i in range(num_slides)]
    )
    project_service.save_design_spec(project_dir, spec)
    project_service.save_design_summary(
        project_dir,
        {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        },
    )

    # slides/ HTML만 생성 (outline/script 없음)
    slides_dir = project_dir / "slides"
    slides_dir.mkdir(exist_ok=True)
    for i in range(num_slides):
        (slides_dir / f"slide_{i + 1:02d}.html").write_text(
            f"<div>slide {i + 1}</div>",
            encoding="utf-8",
        )

    return project_id, project_dir, project_service


def _setup_partial_outline_project(
    tmp_path: Path,
    monkeypatch,
    design_spec_count: int = 20,
    outline_count: int = 10,
) -> tuple[str, Path, ProjectService]:
    """design_spec은 N장, outline은 M장(M < N)인 불일치 프로젝트를 생성한다."""
    import ppt_generator.tools.project.service as svc_module

    monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

    project_service = ProjectService()
    project_id = "partial-proj"
    project_dir = tmp_path / project_id
    project_dir.mkdir()

    meta = {
        "topic": "Partial",
        "num_slides": design_spec_count,
        "steps_completed": {},
    }
    (project_dir / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )

    # design_spec: N장
    spec = DesignSpec(
        slides=[_make_slide_spec(f"디자인 {i + 1}") for i in range(design_spec_count)]
    )
    project_service.save_design_spec(project_dir, spec)
    project_service.save_design_summary(
        project_dir,
        {
            "background_color": "#1a1a2e",
            "text_colors": ["#ffffff"],
            "title_font_pt": 32,
            "body_font_pt": 18,
            "card_fills": [],
            "card_borders": [],
        },
    )

    # outline: M장 (M < N)
    outline_data = json.dumps(
        {
            "slides": [
                {
                    "title": f"아웃라인 {i + 1}",
                    "content_summary": f"내용 {i + 1}",
                    "component_hint": "bullets",
                    "speaker_notes": "",
                    "slide_type": "content",
                }
                for i in range(outline_count)
            ]
        },
        ensure_ascii=False,
    )
    project_service.save_outline(project_dir, outline_data)

    # slides/ HTML: N장
    slides_dir = project_dir / "slides"
    slides_dir.mkdir(exist_ok=True)
    for i in range(design_spec_count):
        (slides_dir / f"slide_{i + 1:02d}.html").write_text(
            f"<div>slide {i + 1}</div>",
            encoding="utf-8",
        )

    return project_id, project_dir, project_service


# ============================================================
# imported 프로젝트 (outline 없음) 에서의 동작
# ============================================================


class TestImportedProjectNoOutline:
    """outline이 없는 imported 프로젝트에서 move/delete가 안전하게 동작하는지 검증."""

    def test_move_slide_no_outline(self, tmp_path: Path, monkeypatch) -> None:
        """imported 프로젝트(outline 없음)에서 move_slide이 에러 없이 동작."""
        project_id, project_dir, svc = _setup_imported_project(
            tmp_path, monkeypatch, 20
        )
        tools = _register_tools(svc)

        # 20번 슬라이드를 11번으로 이동 (1-based)
        result = json.loads(
            tools["move_slide"](
                project_id=project_id,
                from_index=20,
                to_index=11,
            )
        )
        assert result["slide_count"] == 20

        # design_spec 순서 확인
        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 20
        titles = [s.textboxes[0].paragraphs[0].runs[0].text for s in spec.slides]
        expected = [
            f"슬라이드 {i}"
            for i in [
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                10,
                20,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                18,
                19,
            ]
        ]
        assert titles == expected

    def test_delete_slide_no_outline(self, tmp_path: Path, monkeypatch) -> None:
        """imported 프로젝트(outline 없음)에서 delete가 에러 없이 동작."""
        project_id, project_dir, svc = _setup_imported_project(
            tmp_path, monkeypatch, 20
        )
        tools = _register_tools(svc)

        result = json.loads(
            tools["delete_slide"](
                project_id=project_id,
                slide_index=15,
            )
        )
        assert result["slide_count"] == 19

        # design_spec 확인
        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 19

    def test_add_then_delete_no_outline(self, tmp_path: Path, monkeypatch) -> None:
        """imported 프로젝트에서 add 후 delete가 에러 없이 동작."""
        project_id, project_dir, svc = _setup_imported_project(tmp_path, monkeypatch, 5)
        tools = _register_tools(svc)

        # add로 슬라이드 추가 (prepare_slide_edit + ingest_slide_edit)
        result = _add_slide(
            tools,
            project_id,
            slide_index=-1,
            title="추가 슬라이드",
            content_summary="내용",
        )
        assert result["slide_count"] == 6

        # 추가한 슬라이드(6번째, 1-based) 삭제
        result = json.loads(
            tools["delete_slide"](
                project_id=project_id,
                slide_index=6,
            )
        )
        assert result["slide_count"] == 5

    def test_add_then_move_no_outline(self, tmp_path: Path, monkeypatch) -> None:
        """imported 프로젝트에서 add 후 move가 에러 없이 동작."""
        project_id, project_dir, svc = _setup_imported_project(tmp_path, monkeypatch, 5)
        tools = _register_tools(svc)

        # add
        _add_slide(
            tools,
            project_id,
            slide_index=-1,
            title="추가",
            content_summary="내용",
        )
        assert svc.get_design_spec_slide_count(project_dir) == 6

        # move
        result = json.loads(
            tools["move_slide"](
                project_id=project_id,
                from_index=6,
                to_index=1,
            )
        )
        assert result["slide_count"] == 6

    def test_consecutive_adds_on_imported(self, tmp_path: Path, monkeypatch) -> None:
        """imported 프로젝트에서 연속 add 후 전체 슬라이드 수가 올바르게 유지."""
        project_id, project_dir, svc = _setup_imported_project(
            tmp_path, monkeypatch, 10
        )
        tools = _register_tools(svc)

        for i in range(5):
            result = _add_slide(
                tools,
                project_id,
                slide_index=-1,
                title=f"추가 {i + 1}",
                content_summary=f"내용 {i + 1}",
            )
            assert result["slide_count"] == 10 + i + 1

        assert svc.get_design_spec_slide_count(project_dir) == 15

    def test_delete_original_slides_on_imported(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """imported 프로젝트에서 원래 슬라이드(outline 없는)를 삭제할 수 있다."""
        project_id, project_dir, svc = _setup_imported_project(tmp_path, monkeypatch, 5)
        tools = _register_tools(svc)

        # 3번째 슬라이드 삭제 (1-based) — outline이 없어도 에러 없어야 함
        result = json.loads(
            tools["delete_slide"](
                project_id=project_id,
                slide_index=3,
            )
        )
        assert result["slide_count"] == 4


# ============================================================
# outline과 design_spec 수가 불일치하는 경우
# ============================================================


class TestPartialOutlineMismatch:
    """outline < design_spec인 불일치 상태에서의 동작 검증."""

    def test_move_with_fewer_outlines(self, tmp_path: Path, monkeypatch) -> None:
        """outline(10장) < design_spec(20장) 상태에서 move_slide 동작."""
        project_id, project_dir, svc = _setup_partial_outline_project(
            tmp_path,
            monkeypatch,
            design_spec_count=20,
            outline_count=10,
        )
        tools = _register_tools(svc)

        # 20번 → 11번 이동 (design_spec 기준으로 동작해야 함)
        result = json.loads(
            tools["move_slide"](
                project_id=project_id,
                from_index=20,
                to_index=11,
            )
        )
        assert result["slide_count"] == 20

        # design_spec은 올바르게 이동되었는지 확인
        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 20

    def test_delete_beyond_outline_range(self, tmp_path: Path, monkeypatch) -> None:
        """outline 범위 밖 인덱스(11~20)의 슬라이드 삭제가 에러 없이 동작."""
        project_id, project_dir, svc = _setup_partial_outline_project(
            tmp_path,
            monkeypatch,
            design_spec_count=20,
            outline_count=10,
        )
        tools = _register_tools(svc)

        # 15번째 슬라이드 삭제 (1-based) — outline에는 해당 인덱스가 없음
        result = json.loads(
            tools["delete_slide"](
                project_id=project_id,
                slide_index=15,
            )
        )
        assert result["slide_count"] == 19

        # design_spec 확인
        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 19

    def test_delete_within_outline_range(self, tmp_path: Path, monkeypatch) -> None:
        """outline 범위 내 인덱스 삭제 시 outline도 같이 삭제 (sync로 패딩 후)."""
        project_id, project_dir, svc = _setup_partial_outline_project(
            tmp_path,
            monkeypatch,
            design_spec_count=20,
            outline_count=10,
        )
        tools = _register_tools(svc)

        # 5번째 슬라이드 삭제 (1-based) — sync로 outline 20장 패딩 후 삭제
        result = json.loads(
            tools["delete_slide"](
                project_id=project_id,
                slide_index=5,
            )
        )
        assert result["slide_count"] == 19

        # outline도 design_spec과 동일하게 19개
        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == 19

    def test_move_within_outline_range(self, tmp_path: Path, monkeypatch) -> None:
        """outline 범위 내 이동 시 outline도 같이 이동."""
        project_id, project_dir, svc = _setup_partial_outline_project(
            tmp_path,
            monkeypatch,
            design_spec_count=20,
            outline_count=10,
        )
        tools = _register_tools(svc)

        # 1번 → 5번 이동 (둘 다 outline 범위 내)
        result = json.loads(
            tools["move_slide"](
                project_id=project_id,
                from_index=1,
                to_index=5,
            )
        )
        assert result["slide_count"] == 20

        # outline 순서 확인: [1,2,...,10] → pop(0) → [2,3,4,5,...,10] → insert(4,1) → [2,3,4,5,1,6,...,10]
        outline = json.loads(svc.load_outline(project_dir))
        assert outline["slides"][0]["title"] == "아웃라인 2"
        assert outline["slides"][4]["title"] == "아웃라인 1"

    def test_consecutive_deletes_across_boundary(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """outline 범위 안/밖을 넘나드는 연속 삭제 (sync로 패딩 후)."""
        project_id, project_dir, svc = _setup_partial_outline_project(
            tmp_path,
            monkeypatch,
            design_spec_count=20,
            outline_count=10,
        )
        tools = _register_tools(svc)

        # 15번 삭제 — sync로 outline 20장 패딩 후 삭제
        result = json.loads(
            tools["delete_slide"](
                project_id=project_id,
                slide_index=15,
            )
        )
        assert result["slide_count"] == 19

        # 5번 삭제
        result = json.loads(
            tools["delete_slide"](
                project_id=project_id,
                slide_index=5,
            )
        )
        assert result["slide_count"] == 18

        # outline과 design_spec 모두 18개로 동기화
        outline = json.loads(svc.load_outline(project_dir))
        assert len(outline["slides"]) == 18
        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 18
