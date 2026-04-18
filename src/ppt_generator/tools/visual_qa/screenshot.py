"""슬라이드 스크린샷 캡처 모듈 (Chrome DevTools Protocol)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

from ppt_generator.interfaces.constants import (
    CDP_DEBUG_PORT,
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
    """Chrome DevTools Protocol로 슬라이드 스크린샷을 캡처한다."""
    if not _is_chrome_running(CDP_DEBUG_PORT):
        raise RuntimeError(
            f"Chrome이 디버깅 포트 {CDP_DEBUG_PORT}에서 실행되고 있지 않습니다.\n"
            f"Chrome을 다음과 같이 실행해주세요:\n"
            f"  chrome --remote-debugging-port={CDP_DEBUG_PORT} --headless=new"
        )

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
            _cdp_capture_single(html_file, png_path)
            logger.info("스크린샷 캡처: %s", png_path)
            return idx, png_path
        except Exception:
            logger.exception("스크린샷 캡처 실패: slide_index=%d", idx)
            return idx, None

    logger.info(
        "CDP 스크린샷 캡처 시작: %d슬라이드 (workers=%d)",
        len(indices),
        VISUAL_QA_PARALLEL,
    )
    with ThreadPoolExecutor(max_workers=VISUAL_QA_PARALLEL) as pool:
        futures = [(idx, pool.submit(_capture_one, idx)) for idx in indices]
        for idx, future in futures:
            try:
                _, path = future.result(timeout=SCREENSHOT_TIMEOUT)
            except TimeoutError:
                logger.error(
                    "스크린샷 타임아웃: slide_index=%d (%ds 초과)",
                    idx,
                    SCREENSHOT_TIMEOUT,
                )
                path = None
            if path is not None:
                results[idx] = path
    logger.info("스크린샷 캡처 완료: %d/%d 성공", len(results), len(indices))
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_chrome_running(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        return sock.connect_ex(("localhost", port)) == 0


def _cdp_http(path: str, method: str = "GET") -> dict | list:
    url = f"http://localhost:{CDP_DEBUG_PORT}{path}"
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _cdp_capture_single(html_file: Path, png_path: Path) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            new_loop.run_until_complete(_cdp_capture_async(html_file, png_path))
        finally:
            new_loop.close()
    else:
        asyncio.run(_cdp_capture_async(html_file, png_path))


async def _cdp_capture_async(html_file: Path, png_path: Path) -> None:
    import websockets

    file_url = f"file://{html_file.resolve()}"
    target = _cdp_http(f"/json/new?{file_url}", method="PUT")
    ws_url = target["webSocketDebuggerUrl"]
    target_id = target["id"]

    try:
        async with websockets.connect(ws_url, close_timeout=5) as ws:
            req_id = 0

            async def send_cmd(method: str, params: dict | None = None) -> dict:
                nonlocal req_id
                req_id += 1
                await ws.send(
                    json.dumps({"id": req_id, "method": method, "params": params or {}})
                )
                while True:
                    msg = json.loads(
                        await asyncio.wait_for(ws.recv(), timeout=SCREENSHOT_TIMEOUT)
                    )
                    if msg.get("id") == req_id:
                        if "error" in msg:
                            raise RuntimeError(
                                f"CDP {method}: {msg['error'].get('message')}"
                            )
                        return msg.get("result", {})

            await send_cmd("Page.enable")
            await send_cmd(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": VISUAL_QA_VIEWPORT_WIDTH,
                    "height": VISUAL_QA_VIEWPORT_HEIGHT,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            await send_cmd("Page.navigate", {"url": file_url})

            deadline = asyncio.get_event_loop().time() + SCREENSHOT_TIMEOUT
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 5.0))
                    event = json.loads(raw)
                    if event.get("method") == "Page.loadEventFired":
                        break
                except asyncio.TimeoutError:
                    break

            await asyncio.sleep(0.3)

            result = await send_cmd(
                "Page.captureScreenshot",
                {"format": "png", "fromSurface": True},
            )
            png_bytes = base64.b64decode(result["data"])
            png_path.parent.mkdir(parents=True, exist_ok=True)
            png_path.write_bytes(png_bytes)
    finally:
        try:
            _cdp_http(f"/json/close/{target_id}", method="GET")
        except Exception:
            pass
