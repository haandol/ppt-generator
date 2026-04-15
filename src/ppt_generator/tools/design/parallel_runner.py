"""디자인 스펙 병렬 생성 러너.

ThreadPoolExecutor 기반 슬라이드 병렬 생성, 토큰 집계, 결과 정렬을 담당한다.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from typing import Callable

from strands.types.exceptions import ModelThrottledException

from ppt_generator.interfaces.constants import DESIGN_SPEC_PARALLEL
from ppt_generator.interfaces.schemas import OutlineResponse
from ppt_generator.interfaces.utils import (
    complexity_to_thinking_effort,
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
    design_service_factory: Callable[[str, str], DesignService],
    project_service: ProjectService,
    project_dir: "Path",  # noqa: F821
    slides_service: SlidesService | None = None,
    report_progress: Callable[[int, str], None] | None = None,
    review_service_factory: Callable | None = None,
) -> ParallelResult:
    """슬라이드를 병렬로 생성하고 결과를 반환한다.

    Args:
        outline: 전체 아웃라인
        indices: 생성할 슬라이드 인덱스 목록 (0-based)
        total_slides: 전체 슬라이드 수
        color_theme: 색상 테마
        design_summary: 디자인 요약 dict
        design_service_factory: (effort, slide_type) → DesignService 팩토리
        project_service: 프로젝트 서비스
        project_dir: 프로젝트 디렉토리 경로
        slides_service: HTML 렌더링 서비스 (None이면 HTML 생성 건너뜀)
        report_progress: 진행 보고 콜백 (completed_count, message)

    Returns:
        ParallelResult
    """
    # 복잡도 내림차순 스케줄링
    parallel_indices = sorted(
        indices,
        key=lambda i: estimate_slide_complexity(outline.slides[i]),
        reverse=True,
    )

    if not parallel_indices:
        return ParallelResult()

    # 캐시 워밍업: content 슬라이드를 effort별로 1개씩 먼저 생성하여
    # Bedrock prompt cache를 만든 뒤 나머지를 병렬 처리한다.
    # additionalModelRequestFields(thinking effort)가 다르면 캐시 키가 달라지므로
    # effort별로 각각 워밍업해야 cache hit를 극대화할 수 있다.
    warmup_indices: list[int] = []
    content_indices = [
        i
        for i in parallel_indices
        if (outline.slides[i].slide_type or "content") == "content"
    ]
    if len(content_indices) >= 2:
        # effort별로 가장 단순한 content 슬라이드 1개씩 선택
        effort_to_candidates: dict[str, list[int]] = {}
        for i in content_indices:
            effort = complexity_to_thinking_effort(
                estimate_slide_complexity(outline.slides[i])
            )
            effort_to_candidates.setdefault(effort, []).append(i)
        for effort, candidates in effort_to_candidates.items():
            if len(candidates) >= 2:
                # 복잡도 내림차순이므로 마지막이 가장 단순
                warmup_indices.append(candidates[-1])

    result = ParallelResult()
    results_map: dict[int, dict] = {}
    max_workers = min(DESIGN_SPEC_PARALLEL, len(parallel_indices))

    logger.info(
        "병렬 처리 설정: DESIGN_SPEC_PARALLEL=%d, 대상 슬라이드=%d개, max_workers=%d, cache_warmup=slides%s",
        DESIGN_SPEC_PARALLEL,
        len(parallel_indices),
        max_workers,
        warmup_indices if warmup_indices else "[]",
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
        complexity = estimate_slide_complexity(slide_outline)
        effort = complexity_to_thinking_effort(complexity)
        slide_type = slide_outline.slide_type or "content"
        logger.info(
            "slide[%d] 생성 시작 (complexity=%d, effort=%s, slide_type=%s, thread=%s, 동시실행=%d/%d)",
            idx,
            complexity,
            effort,
            slide_type,
            thread_name,
            current,
            max_workers,
        )
        t0 = time.monotonic()
        svc = design_service_factory(effort, slide_type)
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
            )
            # content 슬라이드의 배경색을 design_summary 값으로 강제 보정
            if (
                design_summary
                and spec.slide_type == "content"
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

            # --- Collect overflow content ---
            overflow_items: list[dict] = svc.last_overflow

            # --- Design review step ---
            gen_usage = svc.last_token_usage
            combined_usage = gen_usage
            review_issues: list[dict] = []
            if review_service_factory is not None:
                try:
                    from ppt_generator.tools.design.review_service import (
                        apply_review_and_fix,
                    )

                    def _regenerate(feedback: str) -> tuple:
                        svc_regen = design_service_factory(effort, slide_type)
                        new = svc_regen.generate_single_slide(
                            outline.slides[idx],
                            design_summary=design_summary,
                            slide_index=idx + 1,
                            total_slides=total_slides,
                            color_theme=color_theme,
                            prev_outline=prev_outline,
                            next_outline=next_outline,
                            review_feedback=feedback,
                        )
                        if (
                            design_summary
                            and new.slide_type == "content"
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
                    idx, spec, color_theme=color_theme
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

    # 캐시 워밍업: effort별 content 슬라이드를 순차 실행하여 캐시 준비
    warmup_set = set(warmup_indices)
    if warmup_indices:
        logger.info(
            "cache warmup: slides%s 먼저 생성하여 effort별 prompt cache 준비",
            warmup_indices,
        )
        for wi in warmup_indices:
            _collect_result(_generate_slide(wi))
        remaining_indices = [i for i in parallel_indices if i not in warmup_set]
    else:
        remaining_indices = parallel_indices

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(_generate_slide, i): i for i in remaining_indices
        }
        for future in as_completed(future_to_idx):
            _collect_result(future.result())

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

    # 결과를 인덱스 순서로 정렬, 외부 노출 시 1-based로 변환
    for res in results_map.values():
        res["slide_index"] = res["slide_index"] + 1
    result.results = [results_map[i] for i in sorted(results_map)]
    return result
