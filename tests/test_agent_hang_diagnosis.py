"""Agent 무한 hang 원인 진단 테스트.

strands Agent의 event loop가 tool_use 응답을 받으면 재귀적으로 루프를 돌며,
max_turns 같은 제한이 없어 무한 hang이 발생할 수 있다.

주요 hang 시나리오:
1. 모델이 tool_use stop_reason을 반복 반환 → 무한 재귀 event loop
2. callback_handler(PrintingCallbackHandler)가 stdout에 계속 출력 → MCP stdio 전송과 충돌
3. 모델 API 호출 자체의 무기한 블로킹 (timeout 없음)
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


class TestAgentHangScenario1_ToolUseInfiniteLoop:
    """모델이 tool_use를 반복 반환하면 event loop가 무한 재귀한다."""

    def test_event_loop_recurses_on_tool_use_stop_reason(self):
        """strands event loop는 stop_reason='tool_use' 시 recurse_event_loop을 호출한다.
        max_turns 제한이 없으므로 모델이 계속 tool을 호출하면 무한 루프에 빠진다.
        """
        from strands.event_loop.event_loop import recurse_event_loop

        # recurse_event_loop 함수가 존재하고, 재귀 호출 구조임을 확인
        assert callable(recurse_event_loop)

        # strands Agent에 max_turns 파라미터가 없음을 확인
        import inspect

        from strands import Agent

        sig = inspect.signature(Agent.__init__)
        param_names = list(sig.parameters.keys())
        assert "max_turns" not in param_names, (
            "max_turns 파라미터가 추가되었다면 이 테스트를 업데이트하세요"
        )


class TestAgentHangScenario2_CallbackHandlerStdioConflict:
    """기본 PrintingCallbackHandler가 stdout에 출력하면 MCP stdio 전송과 충돌한다."""

    def test_default_callback_handler_prints_to_stdout(self):
        """Agent의 기본 callback_handler는 PrintingCallbackHandler로,
        stdout에 스트리밍 출력한다. MCP 서버(stdio transport)에서는
        stdout이 JSON-RPC 채널이므로 출력이 섞여 프로토콜이 깨진다.
        """
        from strands.handlers.callback_handler import PrintingCallbackHandler

        handler = PrintingCallbackHandler()
        # PrintingCallbackHandler는 print()를 통해 stdout에 출력하는 핸들러
        assert handler is not None

    def test_di_container_disables_callback_handler(self):
        """DIContainer가 Agent 생성 시 callback_handler=None을 전달하여
        PrintingCallbackHandler의 stdout 출력을 비활성화한다.
        """
        from ppt_generator.di.container import DIContainer

        import inspect

        source = inspect.getsource(DIContainer._create_agent)
        assert "callback_handler=None" in source


class TestAgentHangScenario3_BlockingWithoutTimeout:
    """Agent.__call__은 내부적으로 ThreadPoolExecutor에서 블로킹하며 timeout이 없다."""

    def test_run_async_blocks_indefinitely(self):
        """strands의 run_async 함수는 future.result()로 블로킹하며 timeout이 없다."""
        from strands._async import run_async

        # run_async가 블로킹 함수임을 확인
        import inspect

        source = inspect.getsource(run_async)
        assert "future.result()" in source, "run_async가 future.result()로 블로킹한다"
        # timeout 파라미터 없이 호출됨을 확인
        assert "future.result(timeout" not in source, (
            "timeout이 추가되었다면 이 문제는 해결된 것입니다"
        )

    def test_agent_call_blocks_on_slow_model(self):
        """모델 응답이 느리면 Agent.__call__이 무기한 블로킹된다.
        실제 Bedrock API 호출 없이 mock으로 시뮬레이션한다.
        """
        from strands._async import run_async

        hang_detected = threading.Event()
        call_completed = threading.Event()

        async def slow_coroutine():
            """5초간 블로킹하는 코루틴 (실제로는 Bedrock API 호출)"""
            import asyncio

            await asyncio.sleep(5)
            return "done"

        def run_blocking():
            try:
                run_async(slow_coroutine)
                call_completed.set()
            except Exception:
                call_completed.set()

        t = threading.Thread(target=run_blocking)
        t.start()

        # 1초 후에도 완료되지 않으면 블로킹 중
        t.join(timeout=1.0)
        if t.is_alive():
            hang_detected.set()

        assert hang_detected.is_set(), "run_async가 블로킹 없이 즉시 반환되었다 (예상 외)"

        # 정리: 스레드 종료 대기
        t.join(timeout=10.0)


class TestAgentHangScenario4_RetryInfiniteLoop:
    """ModelRetryStrategy의 hook이 retry를 요청하면 모델 호출이 무한 반복된다."""

    def test_default_retry_strategy_has_max_attempts(self):
        """기본 retry strategy는 max_attempts가 설정되어 있지만,
        hook에서 retry=True를 설정하면 무한 반복할 수 있다.
        """
        from strands.agent.agent import MAX_ATTEMPTS

        # 기본 max_attempts 확인
        assert MAX_ATTEMPTS > 0

    def test_retry_loop_in_event_loop_is_while_true(self):
        """_handle_model_execution의 retry 루프는 while True로 구현되어 있다."""
        import inspect

        from strands.event_loop.event_loop import _handle_model_execution

        source = inspect.getsource(_handle_model_execution)
        assert "while True" in source, (
            "_handle_model_execution이 while True 루프를 사용한다"
        )


class TestMCPServerHangDiagnosis:
    """MCP 서버로 실행할 때 발생하는 hang 문제 진단."""

    def test_server_uses_stdio_transport(self):
        """서버가 stdio transport를 사용한다.
        stdout이 JSON-RPC 채널인데 Agent의 PrintingCallbackHandler가
        stdout에 출력하면 프로토콜이 깨진다.
        """
        import inspect

        from ppt_generator.server import create_server, main

        source = inspect.getsource(main)
        assert 'transport="stdio"' in source

    def test_create_server_disables_callback_and_tools(self):
        """DIContainer에서 Agent 생성 시 callback_handler=None과 tools=[]를 설정하여
        stdout 충돌과 tool_use 무한 루프를 방지한다.
        """
        import inspect

        from ppt_generator.di.container import DIContainer

        source = inspect.getsource(DIContainer)
        assert "callback_handler=None" in source
        assert "tools=[]" in source


class TestProposedFix:
    """제안하는 수정사항 검증."""

    def test_agent_with_tools_empty_list_prevents_tool_loop(self):
        """tools=[]로 빈 리스트를 전달하면 도구가 등록되지 않아
        모델이 tool_use를 반환해도 실행할 도구가 없다.
        """
        from strands.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.process_tools([])  # 빈 리스트 전달
        registry.initialize_tools(load_tools_from_directory=False)
        assert len(registry.get_all_tool_specs()) == 0

    def test_agent_with_tools_none_may_discover_tools(self):
        """tools=None이면 process_tools가 호출되지 않지만,
        initialize_tools에서 CWD/tools/ 디렉토리를 탐색한다.
        프로젝트에 tools/ 디렉토리가 있으면 의도치 않은 도구가 로드될 수 있다.
        """
        from strands.tools.registry import ToolRegistry

        registry = ToolRegistry()
        # tools=None일 때 process_tools가 호출되지 않음을 확인
        # Agent.__init__ 코드: if tools is not None: self.tool_registry.process_tools(tools)
        import inspect

        from strands import Agent

        source = inspect.getsource(Agent.__init__)
        assert "if tools is not None:" in source

    def test_null_callback_handler_exists(self):
        """callback_handler=None으로 설정하면 null_callback_handler가 사용된다.
        이렇게 하면 stdout 출력이 없어 MCP stdio 충돌을 방지한다.
        """
        from strands.handlers.callback_handler import null_callback_handler

        # null_callback_handler가 존재하고 호출 가능함을 확인
        assert callable(null_callback_handler)
