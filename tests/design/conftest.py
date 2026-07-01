"""tests/design/ 공용 fixture.

design tool (prepare/ingest 오프로딩) 테스트들이 공유하는 fixture.
LLM 생성은 클라이언트가 하므로, 테스트는 mock design_service 가 반환하는
(spec, overflow) 를 ingest 결과로 쓴다.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ppt_generator.tools.design.controller import register_design_tools
from ppt_generator.tools.project.service import ProjectService
from _helpers import make_design_spec, make_slide_spec


@pytest.fixture()
def project_service() -> ProjectService:
    return ProjectService()


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """기본 generated 프로젝트 디렉토리 (project.json 포함, 슬라이드 3장 메타)."""
    d = tmp_path / "test_project"
    d.mkdir()
    meta = {"topic": "테스트", "num_slides": 3, "steps_completed": {}}
    (d / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )
    return d


@pytest.fixture()
def project_with_design_spec(
    project_service: ProjectService, project_dir: Path
) -> tuple[str, Path]:
    """design_spec + design_summary + outline 이 모두 채워진 generated 프로젝트."""
    spec = make_design_spec(3)
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
                for i in range(3)
            ]
        },
        ensure_ascii=False,
    )
    project_service.save_outline(project_dir, outline_data)
    return project_dir.name, project_dir


def _build_design_service_mock() -> MagicMock:
    """prepare/ingest 를 노출하는 mock DesignService.

    - prepare_* 는 stub 태스크 dict 를 반환한다 (프롬프트 조립은 실제 서비스가 검증하므로
      여기선 형태만).
    - ingest_slide 는 (spec, overflow) 를 반환한다 — 기본은 새 spec + overflow 없음.
    - ingest_modify_component / ingest_backfill 은 새 spec 을 반환한다.
    """
    design_service = MagicMock()
    design_service.prepare_slide.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }
    design_service.prepare_design_doc_draft.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
    }
    design_service.prepare_backfill.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }
    design_service.prepare_modify_component.return_value = {
        "system_prompt": "sys",
        "user_prompt": "usr",
        "response_schema": {},
    }
    design_service.ingest_slide.return_value = (make_slide_spec("새로 생성됨"), [])
    _summary = {
        "background_color": "#1a1a2e",
        "text_colors": ["#ffffff"],
        "title_font_pt": 32,
        "body_font_pt": 18,
        "card_fills": [],
        "card_borders": [],
    }
    design_service.ingest_design_doc_draft.return_value = (_summary, "", [])
    return design_service


def _register_tools(
    project_service: ProjectService,
    *,
    slides_service=None,
) -> dict:
    """register_design_tools 를 mock MCP 에 적용해 도구 dict 를 만든다."""
    mcp = MagicMock()
    tools: dict = {}

    def tool_decorator():
        def decorator(func):
            tools[func.__name__] = func
            return func

        return decorator

    mcp.tool = tool_decorator

    design_service = _build_design_service_mock()

    kwargs = {"design_service": design_service}
    if slides_service is not None:
        kwargs["slides_service"] = slides_service

    register_design_tools(mcp, project_service, **kwargs)
    tools["_design_service"] = design_service
    tools["_project_service"] = project_service
    return tools


@pytest.fixture()
def mcp_tools(project_service: ProjectService) -> dict:
    """slides_service 미설정 — 파일 동기화만 테스트할 때 사용."""
    return _register_tools(project_service)


@pytest.fixture()
def mcp_tools_with_slides(project_service: ProjectService) -> dict:
    """slides_service mock 포함 — HTML 슬라이드 동기화 검증용."""
    slides_service = MagicMock()
    slides_service.render_single_slide_html.return_value = "<html>new slide</html>"
    tools = _register_tools(project_service, slides_service=slides_service)
    tools["_slides_service"] = slides_service
    return tools
