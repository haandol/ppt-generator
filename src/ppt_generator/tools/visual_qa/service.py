"""Visual QA 서비스.

Playwright 스크린샷 + Claude Vision 분석 + 자동 수정 로직을 담당한다.

흐름:
  1. HTML export (전체 슬라이드)
  2. 스크린샷 캡처 (전체 한번에, ThreadPoolExecutor 병렬)
  3. LLM 분석 (전체 병렬, asyncio.gather)
  4. 이슈 있는 슬라이드만 LLM 수정 (병렬, asyncio.gather)
  5. 수정된 슬라이드만 HTML 재렌더링 → 다음 반복
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Awaitable, Callable

from ppt_generator.interfaces.constants import (
    SCREENSHOT_TIMEOUT,
    VISUAL_QA_PHASE_TIMEOUT,
)
from ppt_generator.interfaces.llm_output_models import SlideSpecOutput, VisualQAOutput
from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils import validate_slide_spec
from ppt_generator.interfaces.spec_utils.serializer import slide_spec_to_json
from ppt_generator.interfaces.utils import log_token_usage
from ppt_generator.tools.visual_qa.models import SlideQAResult, VisualQAResult
from ppt_generator.tools.visual_qa.screenshot import capture_screenshots

logger = logging.getLogger(__name__)


class VisualQAService:
    """Playwright 스크린샷 + LLM 분석으로 슬라이드 시각적 품질을 검사한다."""

    def __init__(
        self,
        analysis_agent_factory: Callable[[], Any],
        fix_agent_factory: Callable[[], Any],
    ) -> None:
        self._analysis_agent_factory = analysis_agent_factory
        self._fix_agent_factory = fix_agent_factory
        self._token_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Phase 1: 스크린샷 캡처 (위임)
    # ------------------------------------------------------------------

    @staticmethod
    def capture_screenshots(
        project_dir: Path,
        indices: list[int],
        iteration: int = 0,
    ) -> dict[int, Path]:
        """Playwright headless Chromium으로 슬라이드 스크린샷을 캡처한다."""
        return capture_screenshots(project_dir, indices, iteration)

    # ------------------------------------------------------------------
    # Phase 2: 스크린샷 분석 (개별)
    # ------------------------------------------------------------------

    def analyze_screenshot(
        self,
        png_path: Path,
        slide_index: int,
        design_spec: PptxSlideSpec,
    ) -> VisualQAOutput:
        """Claude Vision으로 스크린샷을 분석하여 시각적 이슈를 감지한다."""
        spec_json = slide_spec_to_json(design_spec)
        image_b64 = base64.b64encode(png_path.read_bytes()).decode()

        logger.info(
            "분석 시작: slide_index=%d (thread=%s)",
            slide_index,
            threading.current_thread().name,
        )
        agent = self._analysis_agent_factory()
        prompt = (
            f"다음은 슬라이드 {slide_index + 1}의 스크린샷과 디자인 스펙입니다.\n\n"
            f"<design_spec>\n{spec_json}\n</design_spec>\n\n"
            "위 스크린샷을 분석하여 시각적 이슈를 감지해주세요."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": "png",
                            "source": {"bytes": base64.b64decode(image_b64)},
                        },
                    },
                    {"text": prompt},
                ],
            },
        ]

        result = agent(messages, structured_output_model=VisualQAOutput)
        usage = log_token_usage(result, f"visual_qa_analysis[{slide_index}]")
        self._accumulate_tokens(usage)
        logger.info(
            "분석 완료: slide_index=%d (thread=%s)",
            slide_index,
            threading.current_thread().name,
        )

        return result.structured_output

    # ------------------------------------------------------------------
    # Phase 3: 디자인 스펙 수정 (개별)
    # ------------------------------------------------------------------

    def fix_design_spec(
        self,
        png_path: Path,
        current_spec: PptxSlideSpec,
        issues: list[dict],
    ) -> PptxSlideSpec | None:
        """LLM에게 현재 스펙 + 스크린샷 + 이슈 목록을 주고 수정된 스펙을 생성한다."""
        spec_json = slide_spec_to_json(current_spec)
        issues_json = json.dumps(issues, ensure_ascii=False, indent=2)
        image_b64 = base64.b64encode(png_path.read_bytes()).decode()

        agent = self._fix_agent_factory()
        prompt = (
            "다음 슬라이드 디자인 스펙에서 시각적 이슈를 수정해주세요.\n\n"
            f"<current_design_spec>\n{spec_json}\n</current_design_spec>\n\n"
            f"<detected_issues>\n{issues_json}\n</detected_issues>\n\n"
            "위 이슈를 수정한 전체 디자인 스펙 JSON을 출력해주세요."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "image": {
                            "format": "png",
                            "source": {"bytes": base64.b64decode(image_b64)},
                        },
                    },
                    {"text": prompt},
                ],
            },
        ]

        try:
            result = agent(messages, structured_output_model=SlideSpecOutput)
            usage = log_token_usage(result, "visual_qa_fix")
            self._accumulate_tokens(usage)
            output: SlideSpecOutput = result.structured_output
            spec = output.to_dataclass()
            restore = {}
            if current_spec.images:
                restore["images"] = current_spec.images
            if current_spec.slide_type != "content":
                restore["slide_type"] = current_spec.slide_type
            if restore:
                spec = replace(spec, **restore)
            return validate_slide_spec(spec)
        except Exception:
            logger.exception("디자인 스펙 수정 실패")
            return None

    # ------------------------------------------------------------------
    # Heartbeat helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_with_heartbeat(
        coro: asyncio.coroutines,
        report_progress: Callable[[int, int, str], Awaitable[None]] | None,
        progress: int,
        total: int,
        message: str,
        interval: float = 15.0,
    ):
        """coro 실행 중 interval 간격으로 progress heartbeat를 보낸다."""
        if report_progress is None:
            return await coro

        done = asyncio.Event()

        async def _heartbeat() -> None:
            while not done.is_set():
                try:
                    await report_progress(progress, total, message)
                except Exception:
                    logger.debug("heartbeat progress report 실패", exc_info=True)
                try:
                    await asyncio.wait_for(done.wait(), timeout=interval)
                except TimeoutError:
                    pass

        heartbeat_task = asyncio.create_task(_heartbeat())
        try:
            return await coro
        finally:
            done.set()
            await heartbeat_task

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def run_qa(
        self,
        project_dir: Path,
        indices: list[int],
        max_iterations: int,
        load_spec: Callable[[Path, int], PptxSlideSpec],
        save_spec: Callable[[Path, int, PptxSlideSpec], None],
        render_html: Callable[[int, PptxSlideSpec], str],
        save_html: Callable[[Path, int, str], Path],
        report_progress: Callable[[int, int, str], Awaitable[None]] | None = None,
    ) -> VisualQAResult:
        """Visual QA 메인 오케스트레이션."""
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cache_read_tokens = 0
        self._total_cache_write_tokens = 0

        screenshots_dir = project_dir / "screenshots"
        per_slide: dict[int, SlideQAResult] = {
            idx: SlideQAResult(slide_index=idx, status="pending") for idx in indices
        }
        pending_indices = list(indices)
        ever_fixed: set[int] = set()

        iterations_used = 0
        for iteration in range(max_iterations):
            if not pending_indices:
                break
            iterations_used = iteration + 1

            # ── Phase 1: 스크린샷 캡처 ──
            logger.info(
                "iteration %d: 스크린샷 캡처 %d슬라이드",
                iteration,
                len(pending_indices),
            )
            try:
                screenshots = await self._run_with_heartbeat(
                    asyncio.wait_for(
                        asyncio.to_thread(
                            self.capture_screenshots,
                            project_dir,
                            pending_indices,
                            iteration,
                        ),
                        timeout=SCREENSHOT_TIMEOUT * len(pending_indices),
                    ),
                    report_progress=report_progress,
                    progress=iteration,
                    total=max_iterations,
                    message=f"iteration {iteration}: 스크린샷 캡처 중...",
                )
            except TimeoutError:
                logger.error("iteration %d: 스크린샷 캡처 phase 타임아웃", iteration)
                for idx in pending_indices:
                    per_slide[idx].status = "error"
                break

            # ── Phase 2: LLM 분석 (전체 병렬) ──
            logger.info(
                "iteration %d: 병렬 분석 시작 %d슬라이드",
                iteration,
                len(pending_indices),
            )

            async def _analyze_one(idx: int) -> tuple[int, VisualQAOutput | None]:
                png_path = screenshots.get(idx)
                if png_path is None:
                    per_slide[idx].status = "error"
                    return idx, None
                spec = load_spec(project_dir, idx)
                try:
                    analysis = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.analyze_screenshot,
                            png_path,
                            idx,
                            spec,
                        ),
                        timeout=VISUAL_QA_PHASE_TIMEOUT,
                    )
                    return idx, analysis
                except TimeoutError:
                    logger.error(
                        "분석 타임아웃: slide_index=%d (%ds 초과)",
                        idx,
                        VISUAL_QA_PHASE_TIMEOUT,
                    )
                    per_slide[idx].status = "error"
                    return idx, None
                except Exception:
                    logger.exception("분석 실패: slide_index=%d", idx)
                    per_slide[idx].status = "error"
                    return idx, None

            analysis_results = await self._run_with_heartbeat(
                asyncio.gather(
                    *[_analyze_one(idx) for idx in pending_indices],
                ),
                report_progress=report_progress,
                progress=iteration,
                total=max_iterations,
                message=f"iteration {iteration}: LLM 분석 중...",
            )

            # 분석 결과 분류
            slides_to_fix: list[tuple[int, list[dict]]] = []
            for idx, analysis in analysis_results:
                if analysis is None:
                    continue
                per_slide[idx].iterations = iteration + 1
                if not analysis.has_issues:
                    per_slide[idx].status = "fixed" if idx in ever_fixed else "pass"
                else:
                    issue_types = [i.issue_type for i in analysis.issues]
                    per_slide[idx].issues_found = issue_types
                    slides_to_fix.append(
                        (idx, [i.model_dump() for i in analysis.issues])
                    )

            if not slides_to_fix:
                break

            # ── Phase 3: LLM 수정 (이슈 있는 슬라이드만, 병렬) ──
            logger.info(
                "iteration %d: 병렬 수정 시작 %d슬라이드", iteration, len(slides_to_fix)
            )

            async def _fix_one(
                idx: int, issues_dicts: list[dict]
            ) -> tuple[int, PptxSlideSpec | None]:
                png_path = screenshots[idx]
                spec = load_spec(project_dir, idx)
                try:
                    fixed = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.fix_design_spec,
                            png_path,
                            spec,
                            issues_dicts,
                        ),
                        timeout=VISUAL_QA_PHASE_TIMEOUT,
                    )
                except TimeoutError:
                    logger.error(
                        "수정 타임아웃: slide_index=%d (%ds 초과)",
                        idx,
                        VISUAL_QA_PHASE_TIMEOUT,
                    )
                    fixed = None
                return idx, fixed

            fix_results = await self._run_with_heartbeat(
                asyncio.gather(
                    *[_fix_one(idx, issues) for idx, issues in slides_to_fix],
                ),
                report_progress=report_progress,
                progress=iteration,
                total=max_iterations,
                message=f"iteration {iteration}: LLM 수정 중...",
            )

            # ── Phase 4: 수정된 슬라이드 저장 + HTML 재렌더링 ──
            next_pending: list[int] = []
            for idx, fixed_spec in fix_results:
                if fixed_spec is not None:
                    save_spec(project_dir, idx, fixed_spec)
                    html = render_html(idx, fixed_spec)
                    save_html(project_dir, idx, html)
                    ever_fixed.add(idx)
                    per_slide[idx].status = "fixed"
                    next_pending.append(idx)
                else:
                    per_slide[idx].status = "unfixed"

            pending_indices = next_pending

            if report_progress is not None:
                await report_progress(
                    iteration + 1,
                    max_iterations,
                    f"iteration {iteration + 1}/{max_iterations} 완료 "
                    f"(pass={sum(1 for r in per_slide.values() if r.status == 'pass')}, "
                    f"fixed={sum(1 for r in per_slide.values() if r.status == 'fixed')}, "
                    f"pending={len(next_pending)})",
                )

        result_list = sorted(per_slide.values(), key=lambda r: r.slide_index)
        slides_with_issues = sum(1 for r in result_list if r.issues_found)
        slides_fixed = sum(1 for r in result_list if r.status == "fixed")

        return VisualQAResult(
            slides_analyzed=len(indices),
            slides_with_issues=slides_with_issues,
            slides_fixed=slides_fixed,
            iterations_used=iterations_used,
            screenshots_dir=str(screenshots_dir),
            per_slide=result_list,
            total_input_tokens=self._total_input_tokens,
            total_output_tokens=self._total_output_tokens,
            total_cache_read_tokens=self._total_cache_read_tokens,
            total_cache_write_tokens=self._total_cache_write_tokens,
        )

    def _accumulate_tokens(self, usage: dict[str, int]) -> None:
        with self._token_lock:
            self._total_input_tokens = getattr(
                self, "_total_input_tokens", 0
            ) + usage.get("inputTokens", 0)
            self._total_output_tokens = getattr(
                self, "_total_output_tokens", 0
            ) + usage.get("outputTokens", 0)
            self._total_cache_read_tokens = getattr(
                self, "_total_cache_read_tokens", 0
            ) + usage.get("cacheReadInputTokens", 0)
            self._total_cache_write_tokens = getattr(
                self, "_total_cache_write_tokens", 0
            ) + usage.get("cacheWriteInputTokens", 0)
