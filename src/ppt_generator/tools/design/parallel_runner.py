"""디자인 스펙 병렬 생성 러너.

ThreadPoolExecutor 기반 슬라이드 병렬 생성, 토큰 집계, 결과 정렬을 담당한다.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field, replace
from typing import Callable

from strands.types.exceptions import ModelThrottledException

from ppt_generator.interfaces.constants import DESIGN_SPEC_PARALLEL, DESIGN_SPEC_TIMEOUT
from ppt_generator.interfaces.schemas import OutlineResponse
from ppt_generator.interfaces.utils import (
    complexity_to_budget_tokens,
    estimate_slide_complexity,
)
from ppt_generator.tools.design.service import DesignService
from ppt_generator.tools.project.service import ProjectService
from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


@dataclass
class ParallelResult:
    """병렬 생성 결과를 담는 컨테이너."""

    results: list[dict] = field(default_factory=list)
    success_count: int = 0
    error_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0


def run_parallel_generation(
    *,
    outline: OutlineResponse,
    indices: list[int],
    total_slides: int,
    color_theme: str,
    design_summary: dict | None,
    design_service_factory: Callable[..., DesignService],
    project_service: ProjectService,
    project_dir: "Path",  # noqa: F821
    slides_service: SlidesService | None = None,
    report_progress: Callable[[int, str], None] | None = None,
    review_service_factory: Callable | None = None,
    design_doc=None,
    bg_image_policy: str = "gradient",
) -> ParallelResult:
    """슬라이드를 병렬로 생성하고 결과를 반환한다.

    Args:
        outline: 전체 아웃라인
        indices: 생성할 슬라이드 인덱스 목록 (0-based)
        total_slides: 전체 슬라이드 수
        color_theme: 색상 테마
        design_summary: 디자인 요약 dict
        design_service_factory: (slide_type) → DesignService 팩토리
        project_service: 프로젝트 서비스
        project_dir: 프로젝트 디렉토리 경로
        slides_service: HTML 렌더링 서비스 (None이면 HTML 생성 건너뜀)
        report_progress: 진행 보고 콜백 (completed_count, message)

    Returns:
        ParallelResult
    """
    parallel_indices = list(indices)

    if not parallel_indices:
        return ParallelResult()

    result = ParallelResult()
    results_map: dict[int, dict] = {}
    max_workers = min(DESIGN_SPEC_PARALLEL, len(parallel_indices))

    logger.info(
        "병렬 처리 설정: DESIGN_SPEC_PARALLEL=%d, 대상 슬라이드=%d개, max_workers=%d",
        DESIGN_SPEC_PARALLEL,
        len(parallel_indices),
        max_workers,
    )

    active_threads: list[int] = [0]
    peak_threads: list[int] = [0]

    def _generate_slide(idx: int) -> dict:
        thread_name = threading.current_thread().name
        active_threads[0] += 1
        current = active_threads[0]
        if current > peak_threads[0]:
            peak_threads[0] = current
        slide_outline = outline.slides[idx]
        slide_type = slide_outline.slide_type or "content"
        directives = (
            design_doc.directives_for(idx + 1, slide_outline.title)
            if design_doc is not None
            else ""
        )
        complexity = estimate_slide_complexity(slide_outline)
        budget_tokens = complexity_to_budget_tokens(complexity)
        logger.info(
            "slide[%d] 생성 시작 (slide_type=%s, complexity=%d, budget_tokens=%d, thread=%s, 동시실행=%d/%d)",
            idx,
            slide_type,
            complexity,
            budget_tokens,
            thread_name,
            current,
            max_workers,
        )
        t0 = time.monotonic()
        svc = design_service_factory(slide_type, budget_tokens=budget_tokens)
        prev_outline = outline.slides[idx - 1] if idx > 0 else None
        next_outline = (
            outline.slides[idx + 1] if idx + 1 < len(outline.slides) else None
        )
        try:
            spec = svc.generate_single_slide(
                outline.slides[idx],
                design_summary=design_summary,
                slide_index=idx + 1,
                total_slides=total_slides,
                color_theme=color_theme,
                prev_outline=prev_outline,
                next_outline=next_outline,
                design_directives=directives,
            )
            # content 슬라이드는 항상 deck 배경색으로 통일한다. title/closing 은
            # 평소 배경 이미지가 깔리므로 LLM 이 비워두지만, 배경 주입을 끈
            # 경우(bg_image_policy="none")엔 이미지 폴백이 없어 deck 배경색으로
            # 마감해야 한다 (design/0016).
            _enforce_bg = spec.slide_type == "content" or bg_image_policy == "none"
            if (
                design_summary
                and _enforce_bg
                and design_summary.get("background_color")
                and spec.background_color != design_summary["background_color"]
            ):
                logger.info(
                    "slide[%d] 배경색 보정: %s → %s",
                    idx,
                    spec.background_color,
                    design_summary["background_color"],
                )
                spec = replace(
                    spec, background_color=design_summary["background_color"]
                )

            overflow_items: list[dict] = svc.last_overflow

            gen_usage = svc.last_token_usage
            combined_usage = gen_usage
            review_issues: list[dict] = []
            if review_service_factory is not None:
                try:
                    from ppt_generator.interfaces.spec_utils import lint_slide_spec
                    from ppt_generator.tools.design.review_service import (
                        apply_review_and_fix,
                    )

                    # 기계적 린트를 먼저 돌려 LLM 리뷰에 힌트로 전달.
                    # LLM 은 이미 잡힌 위반을 중복 보고하지 않고 시각/의미
                    # 레벨 이슈만 찾는 데 집중하게 된다.
                    # 결정 13b — 단계적 검증.
                    lint_result = lint_slide_spec(spec, stop_on_layer_error=True)

                    def _regenerate(feedback: str) -> tuple:
                        svc_regen = design_service_factory(
                            slide_type, budget_tokens=budget_tokens
                        )
                        new = svc_regen.generate_single_slide(
                            outline.slides[idx],
                            design_summary=design_summary,
                            slide_index=idx + 1,
                            total_slides=total_slides,
                            color_theme=color_theme,
                            prev_outline=prev_outline,
                            next_outline=next_outline,
                            review_feedback=feedback,
                            design_directives=directives,
                        )
                        _enforce = (
                            new.slide_type == "content" or bg_image_policy == "none"
                        )
                        if (
                            design_summary
                            and _enforce
                            and design_summary.get("background_color")
                            and new.background_color
                            != design_summary["background_color"]
                        ):
                            return replace(
                                new, background_color=design_summary["background_color"]
                            ), svc_regen.last_token_usage
                        return new, svc_regen.last_token_usage

                    rr = apply_review_and_fix(
                        spec=spec,
                        slide_index=idx + 1,
                        gen_usage=gen_usage,
                        review_service_factory=review_service_factory,
                        regenerate=_regenerate,
                        lint_result=lint_result,
                    )
                    spec = rr.spec
                    combined_usage = rr.token_usage
                    review_issues = rr.review_issues
                except Exception as exc:
                    logger.warning(
                        "slide[%d] review failed, using original spec: %s", idx, exc
                    )

            project_service.create_design_spec_slide(project_dir, idx, spec)

            html_path_str: str | None = None
            if slides_service is not None:
                html = slides_service.render_single_slide_html(
                    idx, spec, color_theme=color_theme, bg_image_policy=bg_image_policy
                )
                hp = project_service.save_single_slide_html(project_dir, idx, html)
                html_path_str = str(hp)

            elapsed = time.monotonic() - t0
            active_threads[0] -= 1
            logger.info(
                "slide[%d] 생성 완료 (thread=%s, %.1fs)", idx, thread_name, elapsed
            )
            r: dict = {
                "slide_index": idx,
                "status": "success",
                "slide_file": f"slide_{idx + 1:02d}.json",
                "_token_usage": combined_usage,
            }
            if html_path_str:
                r["slide_html_path"] = html_path_str
            if review_issues:
                r["review_issues"] = review_issues
            if overflow_items:
                r["overflow"] = overflow_items
            return r
        except ModelThrottledException as exc:
            elapsed = time.monotonic() - t0
            active_threads[0] -= 1
            logger.warning(
                "slide[%d] Bedrock 쓰로틀링 발생 (thread=%s, %.1fs): %s",
                idx,
                thread_name,
                elapsed,
                exc,
            )
            return {"slide_index": idx, "status": "error", "error": f"throttled: {exc}"}
        except Exception as exc:
            elapsed = time.monotonic() - t0
            active_threads[0] -= 1
            logger.error(
                "slide[%d] 생성 실패 (thread=%s, %.1fs): %s",
                idx,
                thread_name,
                elapsed,
                exc,
            )
            return {"slide_index": idx, "status": "error", "error": str(exc)}

    def _collect_result(res: dict) -> None:
        idx = res["slide_index"]
        usage = res.pop("_token_usage", None)
        if isinstance(usage, dict) and usage:
            result.total_input_tokens += usage.get("inputTokens", 0)
            result.total_output_tokens += usage.get("outputTokens", 0)
            result.total_cache_read_tokens += usage.get("cacheReadInputTokens", 0)
            result.total_cache_write_tokens += usage.get("cacheWriteInputTokens", 0)
        results_map[idx] = res
        if res["status"] == "success":
            result.success_count += 1
        else:
            result.error_count += 1
        completed = result.success_count + result.error_count
        if report_progress:
            report_progress(
                completed,
                f"슬라이드 {completed}/{len(parallel_indices)} "
                f"{'완료' if res['status'] == 'success' else '실패'}",
            )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_generate_slide, i): i for i in parallel_indices
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                _collect_result(future.result(timeout=DESIGN_SPEC_TIMEOUT))
            except TimeoutError:
                logger.error(
                    "slide[%d] 생성 타임아웃 (%ds 초과)", idx, DESIGN_SPEC_TIMEOUT
                )
                _collect_result(
                    {
                        "slide_index": idx,
                        "status": "error",
                        "error": f"timeout after {DESIGN_SPEC_TIMEOUT}s",
                    }
                )

    logger.info(
        "병렬 처리 완료: 최대 동시실행 스레드=%d, 성공=%d, 실패=%d",
        peak_threads[0],
        result.success_count,
        result.error_count,
    )
    total_all = result.total_input_tokens + result.total_output_tokens
    logger.info(
        "[tokens] design_spec 합산: input=%s, output=%s, total=%s, cache_read=%s, cache_write=%s",
        f"{result.total_input_tokens:,}",
        f"{result.total_output_tokens:,}",
        f"{total_all:,}",
        f"{result.total_cache_read_tokens:,}",
        f"{result.total_cache_write_tokens:,}",
    )

    for res in results_map.values():
        res["slide_index"] = res["slide_index"] + 1
    result.results = [results_map[i] for i in sorted(results_map)]
    return result
