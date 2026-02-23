"""토큰 사용량 로깅 테스트.

log_token_usage 헬퍼 함수 단위 테스트 및 각 서비스(outline, script, design)에서
Agent 호출 시 토큰 로깅이 정상 동작하는지 검증한다.
"""

import json
import logging
from unittest.mock import MagicMock

import pytest

from ppt_generator.interfaces.utils import estimate_cost, format_token_usage, log_token_usage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_USAGE = {
    "inputTokens": 5000,
    "outputTokens": 2000,
    "totalTokens": 7000,
}

SAMPLE_USAGE_WITH_CACHE = {
    "inputTokens": 5000,
    "outputTokens": 2000,
    "totalTokens": 7000,
    "cacheReadInputTokens": 3000,
    "cacheWriteInputTokens": 500,
}


def _make_agent_result(usage: dict | None = None) -> MagicMock:
    """strands AgentResult를 모사하는 mock 객체를 생성한다."""
    result = MagicMock()
    result.metrics.accumulated_usage = usage if usage is not None else {}
    return result


# ---------------------------------------------------------------------------
# log_token_usage 단위 테스트
# ---------------------------------------------------------------------------


class TestLogTokenUsage:
    def test_returns_usage_dict(self) -> None:
        result = _make_agent_result(SAMPLE_USAGE)
        usage = log_token_usage(result, "test")

        assert usage["inputTokens"] == 5000
        assert usage["outputTokens"] == 2000
        assert usage["totalTokens"] == 7000

    def test_logs_info_with_label(self, caplog: pytest.LogCaptureFixture) -> None:
        result = _make_agent_result(SAMPLE_USAGE)
        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            log_token_usage(result, "outline")

        assert len(caplog.records) == 1
        msg = caplog.records[0].message
        assert "[tokens] outline:" in msg
        assert "input=5,000" in msg
        assert "output=2,000" in msg
        assert "total=7,000" in msg

    def test_logs_cache_tokens(self, caplog: pytest.LogCaptureFixture) -> None:
        result = _make_agent_result(SAMPLE_USAGE_WITH_CACHE)
        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            log_token_usage(result, "design")

        msg = caplog.records[0].message
        assert "cache_read=3,000" in msg
        assert "cache_write=500" in msg

    def test_omits_cache_tokens_when_zero(self, caplog: pytest.LogCaptureFixture) -> None:
        result = _make_agent_result(SAMPLE_USAGE)
        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            log_token_usage(result, "test")

        msg = caplog.records[0].message
        assert "cache_read" not in msg
        assert "cache_write" not in msg

    def test_returns_empty_dict_on_no_metrics(self) -> None:
        """result.metrics가 없으면 빈 dict를 반환한다."""
        result = MagicMock(spec=[])  # metrics 속성 없음
        usage = log_token_usage(result, "test")

        assert usage == {}

    def test_returns_empty_dict_on_empty_usage(self) -> None:
        """accumulated_usage가 빈 dict이면 빈 dict를 반환한다."""
        result = _make_agent_result({})
        usage = log_token_usage(result, "test")

        assert usage == {}

    def test_returns_empty_dict_on_none_usage(self) -> None:
        """accumulated_usage가 None이면 빈 dict를 반환한다."""
        result = _make_agent_result(None)
        usage = log_token_usage(result, "test")

        assert usage == {}

    def test_returns_empty_dict_on_attribute_error(self) -> None:
        """일반 문자열 등 metrics가 없는 객체도 안전하게 처리."""
        usage = log_token_usage("not an agent result", "test")

        assert usage == {}


# ---------------------------------------------------------------------------
# format_token_usage / estimate_cost 단위 테스트
# ---------------------------------------------------------------------------


class TestFormatTokenUsage:
    def test_returns_only_nonzero_keys(self) -> None:
        usage = {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150}
        result = format_token_usage(usage)
        assert result == {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150}

    def test_includes_cache_when_nonzero(self) -> None:
        result = format_token_usage(SAMPLE_USAGE_WITH_CACHE)
        assert result["cacheReadInputTokens"] == 3000
        assert result["cacheWriteInputTokens"] == 500

    def test_empty_on_empty_dict(self) -> None:
        assert format_token_usage({}) == {}


class TestEstimateCost:
    def test_sonnet_pricing(self) -> None:
        usage = {"inputTokens": 1_000_000, "outputTokens": 1_000_000}
        cost = estimate_cost(usage, "claude-sonnet-4-6")
        assert cost["input_cost"] == 3.0
        assert cost["output_cost"] == 15.0
        assert cost["total_cost"] == 18.0

    def test_bedrock_model_id_resolves(self) -> None:
        usage = {"inputTokens": 1_000_000, "outputTokens": 1_000_000}
        cost = estimate_cost(usage, "global.anthropic.claude-sonnet-4-6")
        assert cost["input_cost"] == 3.0

    def test_cache_tokens_included_in_cost(self) -> None:
        usage = {
            "inputTokens": 0,
            "outputTokens": 0,
            "cacheReadInputTokens": 1_000_000,
            "cacheWriteInputTokens": 1_000_000,
        }
        cost = estimate_cost(usage, "claude-sonnet-4-6")
        assert cost["cache_read_cost"] == 0.30
        assert cost["cache_write_cost"] == 3.75
        assert cost["total_cost"] == pytest.approx(4.05)

    def test_empty_usage_returns_zero(self) -> None:
        cost = estimate_cost({})
        assert cost["total_cost"] == 0.0

    def test_unknown_model_uses_default(self) -> None:
        usage = {"inputTokens": 1_000_000, "outputTokens": 1_000_000}
        cost = estimate_cost(usage, "unknown-model-id")
        # 기본값 sonnet-4-6 가격 적용
        assert cost["input_cost"] == 3.0


# ---------------------------------------------------------------------------
# OutlineService 토큰 로깅 테스트
# ---------------------------------------------------------------------------


class TestOutlineServiceTokenLogging:
    def test_logs_tokens_on_successful_generate(self, caplog: pytest.LogCaptureFixture) -> None:
        from ppt_generator.interfaces.schemas import OutlineRequest
        from ppt_generator.tools.outline.service import OutlineService

        valid_json = json.dumps(
            {"slides": [{"title": "테스트", "content_summary": "내용"}]},
            ensure_ascii=False,
        )

        agent_result = _make_agent_result(SAMPLE_USAGE)
        agent_result.__str__ = lambda self: valid_json

        agent = MagicMock(return_value=agent_result)
        service = OutlineService(agent=agent)

        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            service.generate(OutlineRequest(topic="AI", num_slides=1))

        token_logs = [r for r in caplog.records if "[tokens]" in r.message]
        assert len(token_logs) == 1
        assert "outline (시도 1/3)" in token_logs[0].message
        assert "input=5,000" in token_logs[0].message

    def test_last_token_usage_populated(self) -> None:
        from ppt_generator.interfaces.schemas import OutlineRequest
        from ppt_generator.tools.outline.service import OutlineService

        valid_json = json.dumps(
            {"slides": [{"title": "테스트", "content_summary": "내용"}]},
            ensure_ascii=False,
        )
        agent_result = _make_agent_result(SAMPLE_USAGE)
        agent_result.__str__ = lambda self: valid_json
        agent = MagicMock(return_value=agent_result)
        service = OutlineService(agent=agent)

        assert service.last_token_usage == {}
        service.generate(OutlineRequest(topic="AI", num_slides=1))
        assert service.last_token_usage["inputTokens"] == 5000

    def test_no_token_log_on_plain_string_result(self, caplog: pytest.LogCaptureFixture) -> None:
        """Agent가 plain string을 반환해도 예외 없이 동작한다 (legacy 호환)."""
        from ppt_generator.interfaces.schemas import OutlineRequest
        from ppt_generator.tools.outline.service import OutlineService

        valid_json = json.dumps(
            {"slides": [{"title": "테스트", "content_summary": "내용"}]},
            ensure_ascii=False,
        )

        agent = MagicMock(return_value=valid_json)
        service = OutlineService(agent=agent)

        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            service.generate(OutlineRequest(topic="AI", num_slides=1))


# ---------------------------------------------------------------------------
# ScriptService 토큰 로깅 테스트
# ---------------------------------------------------------------------------


class TestScriptServiceTokenLogging:
    def test_logs_tokens_on_successful_generate(self, caplog: pytest.LogCaptureFixture) -> None:
        from ppt_generator.interfaces.schemas import OutlineResponse, ScriptRequest, SlideOutline
        from ppt_generator.tools.script.service import ScriptService

        valid_json = json.dumps(
            {"scripts": [{"slide_index": 0, "speaker_notes": "노트"}]},
            ensure_ascii=False,
        )

        agent_result = _make_agent_result(SAMPLE_USAGE)
        agent_result.__str__ = lambda self: valid_json

        agent = MagicMock(return_value=agent_result)
        service = ScriptService(agent=agent)

        outline = OutlineResponse(
            slides=[SlideOutline(title="테스트", content_summary="내용")],
        )

        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            service.generate(ScriptRequest(outline=outline))

        token_logs = [r for r in caplog.records if "[tokens]" in r.message]
        assert len(token_logs) == 1
        assert "script" in token_logs[0].message
        assert "input=5,000" in token_logs[0].message

    def test_last_token_usage_populated(self) -> None:
        from ppt_generator.interfaces.schemas import OutlineResponse, ScriptRequest, SlideOutline
        from ppt_generator.tools.script.service import ScriptService

        valid_json = json.dumps(
            {"scripts": [{"slide_index": 0, "speaker_notes": "노트"}]},
            ensure_ascii=False,
        )
        agent_result = _make_agent_result(SAMPLE_USAGE)
        agent_result.__str__ = lambda self: valid_json
        agent = MagicMock(return_value=agent_result)
        service = ScriptService(agent=agent)

        assert service.last_token_usage == {}
        outline = OutlineResponse(slides=[SlideOutline(title="테스트", content_summary="내용")])
        service.generate(ScriptRequest(outline=outline))
        assert service.last_token_usage["inputTokens"] == 5000


# ---------------------------------------------------------------------------
# DesignService 토큰 로깅 테스트
# ---------------------------------------------------------------------------


class TestDesignServiceTokenLogging:
    def test_logs_tokens_on_design_summary(self, caplog: pytest.LogCaptureFixture) -> None:
        from ppt_generator.interfaces.schemas import OutlineResponse, SlideOutline
        from ppt_generator.tools.design.service import DesignService

        summary_json = json.dumps(
            {"background_color": "#1a1a2e", "text_colors": ["#ffffff"]},
            ensure_ascii=False,
        )

        agent_result = _make_agent_result(SAMPLE_USAGE)
        agent_result.__str__ = lambda self: summary_json

        agent = MagicMock(return_value=agent_result)
        service = DesignService(agent=agent)

        outline = OutlineResponse(
            slides=[SlideOutline(title="테스트", content_summary="내용")],
        )

        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            service.generate_design_summary(outline)

        token_logs = [r for r in caplog.records if "[tokens]" in r.message]
        assert len(token_logs) == 1
        assert "design_summary" in token_logs[0].message

    def test_logs_tokens_on_structured_output(self, caplog: pytest.LogCaptureFixture) -> None:
        from ppt_generator.interfaces.llm_output_models import SlideSpecOutput
        from ppt_generator.interfaces.schemas import SlideOutline
        from ppt_generator.tools.design.service import DesignService

        mock_output = SlideSpecOutput(
            background_color="#1a1a2e",
            textboxes=[],
            shapes=[],
        )

        agent_result = _make_agent_result(SAMPLE_USAGE)
        agent_result.structured_output = mock_output

        agent = MagicMock(return_value=agent_result)
        service = DesignService(agent=agent)

        slide = SlideOutline(title="테스트", content_summary="내용")

        with caplog.at_level(logging.INFO, logger="ppt_generator.interfaces.utils"):
            service.generate_single_slide(slide, slide_index=2, total_slides=5)

        token_logs = [r for r in caplog.records if "[tokens]" in r.message]
        assert len(token_logs) == 1
        assert "slide[2/5]" in token_logs[0].message

    def test_last_token_usage_property(self) -> None:
        from ppt_generator.interfaces.llm_output_models import SlideSpecOutput
        from ppt_generator.interfaces.schemas import SlideOutline
        from ppt_generator.tools.design.service import DesignService

        mock_output = SlideSpecOutput(
            background_color="#1a1a2e",
            textboxes=[],
            shapes=[],
        )

        agent_result = _make_agent_result(SAMPLE_USAGE)
        agent_result.structured_output = mock_output

        agent = MagicMock(return_value=agent_result)
        service = DesignService(agent=agent)

        # 호출 전 빈 dict
        assert service.last_token_usage == {}

        slide = SlideOutline(title="테스트", content_summary="내용")
        service.generate_single_slide(slide)

        # 호출 후 usage가 채워짐
        assert service.last_token_usage["inputTokens"] == 5000
        assert service.last_token_usage["outputTokens"] == 2000


# ---------------------------------------------------------------------------
# Design Controller 토큰 합산 로깅 테스트
# ---------------------------------------------------------------------------


class TestDesignControllerTokenAggregation:
    """design controller의 병렬 처리 시 전체 토큰 합산 로깅 검증."""

    @staticmethod
    def _run(coro):
        import asyncio
        return asyncio.run(coro)

    def _setup(self, tmp_path, monkeypatch) -> tuple[dict, str]:
        """MCP 도구 등록 + 프로젝트 디렉토리 설정."""
        import ppt_generator.tools.project.service as svc_module
        from ppt_generator.interfaces.schemas import (
            PptxParagraph,
            PptxSlideSpec,
            PptxTextBox,
            PptxTextRun,
        )
        from ppt_generator.tools.design.controller import register_design_tools
        from ppt_generator.tools.project.service import ProjectService

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        proj_dir = tmp_path / "token-test-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )

        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            textboxes=[
                PptxTextBox(
                    left_px=40, top_px=40, width_px=600, height_px=60,
                    paragraphs=[PptxParagraph(runs=[PptxTextRun(text="테스트", font_size_pt=32, bold=True)])],
                ),
            ],
            shapes=[], images=[], speaker_notes="",
        )

        design_service = MagicMock()
        design_service.generate_single_slide.return_value = spec
        design_service.generate_design_summary.return_value = {
            "background_color": "#1a1a2e", "text_colors": ["#ffffff"],
            "title_font_pt": 32, "body_font_pt": 18, "card_fills": [], "card_borders": [],
        }
        design_service.last_token_usage = {
            "inputTokens": 10000,
            "outputTokens": 3000,
            "totalTokens": 13000,
        }

        mcp = MagicMock()
        tools = {}

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func
            return decorator

        mcp.tool = tool_decorator
        project_service = ProjectService()

        register_design_tools(mcp, project_service, design_service_factory=lambda effort: design_service)
        return tools, "token-test-proj"

    def test_logs_aggregated_tokens(self, tmp_path, monkeypatch, caplog) -> None:
        tools, project_id = self._setup(tmp_path, monkeypatch)

        outline_3 = json.dumps(
            {"slides": [
                {"title": f"슬라이드 {i+1}", "content_summary": f"내용 {i+1}", "component_hint": "bullets", "speaker_notes": ""}
                for i in range(3)
            ]},
            ensure_ascii=False,
        )

        with caplog.at_level(logging.INFO, logger="ppt_generator.tools.design.parallel_runner"):
            result = json.loads(self._run(tools["generate_slides_design_spec"](
                outline_json=outline_3,
                total_slides=3,
                project_id=project_id,
            )))

        assert result["success_count"] == 3

        # 합산 토큰 로그 검증
        agg_logs = [r for r in caplog.records if "[tokens] design_spec 합산" in r.message]
        assert len(agg_logs) == 1
        msg = agg_logs[0].message
        assert "input=30,000" in msg
        assert "output=9,000" in msg
        assert "total=39,000" in msg

    def test_response_includes_token_usage_and_cost(self, tmp_path, monkeypatch) -> None:
        """응답 JSON에 token_usage와 estimated_cost가 포함된다."""
        tools, project_id = self._setup(tmp_path, monkeypatch)

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

        # token_usage 검증
        assert "token_usage" in result
        tu = result["token_usage"]
        assert tu["inputTokens"] == 30000
        assert tu["outputTokens"] == 9000
        assert tu["totalTokens"] == 39000

        # estimated_cost 검증
        assert "estimated_cost" in result
        ec = result["estimated_cost"]
        assert ec["input_cost"] > 0
        assert ec["output_cost"] > 0
        assert ec["total_cost"] > 0

    def test_aggregation_handles_missing_usage(self, tmp_path, monkeypatch, caplog) -> None:
        """last_token_usage가 빈 dict인 서비스에서도 합산이 0으로 정상 동작."""
        import ppt_generator.tools.project.service as svc_module
        from ppt_generator.interfaces.schemas import (
            PptxParagraph,
            PptxSlideSpec,
            PptxTextBox,
            PptxTextRun,
        )
        from ppt_generator.tools.design.controller import register_design_tools
        from ppt_generator.tools.project.service import ProjectService

        monkeypatch.setattr(svc_module, "PPT_GENERATOR_HOME", tmp_path)

        proj_dir = tmp_path / "no-usage-proj"
        proj_dir.mkdir()
        (proj_dir / "project.json").write_text(
            json.dumps({"topic": "", "num_slides": 0, "steps_completed": {}}, ensure_ascii=False),
            encoding="utf-8",
        )

        spec = PptxSlideSpec(
            background_color="#1a1a2e",
            textboxes=[PptxTextBox(
                left_px=40, top_px=40, width_px=600, height_px=60,
                paragraphs=[PptxParagraph(runs=[PptxTextRun(text="t", font_size_pt=32, bold=True)])],
            )],
            shapes=[], images=[], speaker_notes="",
        )

        design_service = MagicMock()
        design_service.generate_single_slide.return_value = spec
        design_service.generate_design_summary.return_value = {
            "background_color": "#1a1a2e", "text_colors": ["#ffffff"],
            "title_font_pt": 32, "body_font_pt": 18, "card_fills": [], "card_borders": [],
        }
        # last_token_usage가 빈 dict
        design_service.last_token_usage = {}

        mcp = MagicMock()
        tools = {}

        def tool_decorator():
            def decorator(func):
                tools[func.__name__] = func
                return func
            return decorator

        mcp.tool = tool_decorator
        project_service = ProjectService()
        register_design_tools(mcp, project_service, design_service_factory=lambda effort: design_service)

        outline_2 = json.dumps(
            {"slides": [
                {"title": f"S{i+1}", "content_summary": f"C{i+1}", "component_hint": "bullets", "speaker_notes": ""}
                for i in range(2)
            ]},
            ensure_ascii=False,
        )

        with caplog.at_level(logging.INFO, logger="ppt_generator.tools.design.parallel_runner"):
            result = json.loads(self._run(tools["generate_slides_design_spec"](
                outline_json=outline_2,
                total_slides=2,
                project_id="no-usage-proj",
            )))

        assert result["success_count"] == 2

        agg_logs = [r for r in caplog.records if "[tokens] design_spec 합산" in r.message]
        assert len(agg_logs) == 1
        assert "input=0" in agg_logs[0].message
        assert "output=0" in agg_logs[0].message
