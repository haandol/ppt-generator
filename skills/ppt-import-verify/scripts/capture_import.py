#!/usr/bin/env python3
"""임포트된 프로젝트의 슬라이드 HTML 을 PNG 로 캡처한다.

사용:
    python capture_import.py <project_id|절대경로> [--slides 1,2,3] [--iter 0]

프로젝트의 VisualQAService.capture_screenshots 를 재사용한다. MCP capture_slides 와 달리
현재 소스 코드로 직접 실행하므로, 코드를 방금 고친 뒤 검증할 때 안전하다.
`uv run python skills/ppt-import-verify/scripts/capture_import.py ...` 로 실행하는 것을 권장.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _project_dir(pid: str) -> Path:
    p = Path(pid)
    if p.is_absolute() and p.exists():
        return p
    return Path.home() / ".ppt-generator" / pid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", help="project_id 또는 프로젝트 절대경로")
    ap.add_argument(
        "--slides", default="", help="1-based, comma-separated (빈 값=전체)"
    )
    ap.add_argument("--iter", type=int, default=0, help="스크린샷 버전(iteration)")
    args = ap.parse_args()

    from ppt_generator.tools.visual_qa.service import VisualQAService

    project_dir = _project_dir(args.project)
    if not (project_dir / "slides.html").exists():
        print(f"[error] slides.html 없음: {project_dir}")
        return 2

    if args.slides:
        indices = [int(s) - 1 for s in args.slides.split(",") if s.strip()]
    else:
        n = len(list((project_dir / "slides").glob("slide_*.html")))
        indices = list(range(n))

    svc = VisualQAService()
    shots = svc.capture_screenshots(project_dir, indices, args.iter)
    for idx in sorted(shots):
        print(f"slide {idx + 1}: {shots[idx]}")
    print(f"[ok] {len(shots)}개 캡처 → {project_dir / 'screenshots'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
