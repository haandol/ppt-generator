"""Playwright 기반 슬라이드 스크린샷 캡처 모듈."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from playwright.sync_api import sync_playwright

from ppt_generator.interfaces.constants import (
    SCREENSHOT_TIMEOUT,
    VISUAL_QA_PARALLEL,
    VISUAL_QA_VIEWPORT_HEIGHT,
    VISUAL_QA_VIEWPORT_WIDTH,
)

logger = logging.getLogger(__name__)


def capture_screenshots(
    project_dir: Path,
    indices: list[int],
    iteration: int = 0,
) -> dict[int, Path]:
    """Playwright headless Chromium으로 슬라이드 스크린샷을 캡처한다."""

    screenshots_dir = project_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    slides_dir = project_dir / "slides"

    results: dict[int, Path] = {}

    def _capture_one(idx: int) -> tuple[int, Path | None]:
        html_file = slides_dir / f"slide_{idx + 1:02d}.html"
        if not html_file.exists():
            logger.warning("슬라이드 HTML 파일 없음: %s", html_file)
            return idx, None
        png_path = screenshots_dir / f"slide_{idx + 1:02d}_v{iteration}.png"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={
                        "width": VISUAL_QA_VIEWPORT_WIDTH,
                        "height": VISUAL_QA_VIEWPORT_HEIGHT,
                    },
                )
                page.goto(f"file://{html_file.resolve()}")
                page.wait_for_load_state("networkidle")
                page.screenshot(path=str(png_path))
                browser.close()
            logger.info("스크린샷 캡처: %s", png_path)
            return idx, png_path
        except Exception as exc:
            if "executable doesn't exist" in str(exc).lower():
                raise RuntimeError(
                    "Chromium 브라우저가 설치되지 않았습니다.\n"
                    "설치: playwright install chromium"
                ) from exc
            logger.exception("스크린샷 캡처 실패: slide_index=%d", idx)
            return idx, None

    logger.info(
        "스크린샷 캡처 시작: %d슬라이드 (workers=%d)", len(indices), VISUAL_QA_PARALLEL
    )
    with ThreadPoolExecutor(max_workers=VISUAL_QA_PARALLEL) as pool:
        futures = [(idx, pool.submit(_capture_one, idx)) for idx in indices]
        for idx, future in futures:
            try:
                _, path = future.result(timeout=SCREENSHOT_TIMEOUT)
            except TimeoutError:
                logger.error(
                    "스크린샷 캡처 타임아웃: slide_index=%d (%ds 초과)",
                    idx,
                    SCREENSHOT_TIMEOUT,
                )
                path = None
            if path is not None:
                results[idx] = path
    logger.info("스크린샷 캡처 완료: %d/%d 성공", len(results), len(indices))

    return results
