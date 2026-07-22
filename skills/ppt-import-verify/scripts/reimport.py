#!/usr/bin/env python3
"""현재 소스 코드로 PPTX 를 (재)임포트해 프로젝트를 생성/갱신한다.

사용:
    uv run python skills/ppt-import-verify/scripts/reimport.py "<원본.pptx>" <project_id>

MCP import_pptx 와 동일한 코드 경로(run_import_pptx)를 직접 호출한다. 임포트 코드를
방금 고쳤을 때, MCP 서버 재시작 없이 고친 코드로 재임포트해 검증하기 위한 용도.
"""

from __future__ import annotations

import argparse


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("project_id")
    args = ap.parse_args()

    from ppt_generator.di.container import DIContainer
    from ppt_generator.tools.pptx_import.controller import run_import_pptx

    c = DIContainer()
    res = run_import_pptx(
        args.pptx,
        args.project_id,
        c.import_service,
        c.project_service,
        c.slides_service,
    )
    print(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
