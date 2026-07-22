#!/usr/bin/env python3
"""원본 PPTX 를 슬라이드별 PNG 로 렌더한다 (LibreOffice + pdftoppm).

사용:
    python render_original.py "<원본.pptx>" <출력_dir> [--dpi 110] [--slides 1,2,3]

soffice --headless --convert-to pdf 로 PDF 를 만든 뒤 pdftoppm 으로 각 페이지를
<출력_dir>/ref-NN.png 로 저장한다. --slides 미지정 시 전체 페이지.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _find_soffice() -> str | None:
    for cand in (
        "soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "libreoffice",
    ):
        if shutil.which(cand) or Path(cand).exists():
            return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("out_dir")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--slides", default="", help="1-based, comma-separated (빈 값=전체)")
    args = ap.parse_args()

    pptx = Path(args.pptx)
    if not pptx.exists():
        print(f"[error] PPTX 없음: {pptx}", file=sys.stderr)
        return 2

    soffice = _find_soffice()
    if soffice is None:
        print("[skip] LibreOffice(soffice) 없음 — 원본 렌더 건너뜀. 좌표 비교만 진행.")
        return 3
    if not shutil.which("pdftoppm"):
        print("[skip] pdftoppm 없음 — 원본 렌더 건너뜀. 좌표 비교만 진행.")
        return 3

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) PPTX → PDF
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx)],
        check=True,
        capture_output=True,
    )
    pdf = out_dir / (pptx.stem + ".pdf")
    if not pdf.exists():
        print(f"[error] PDF 생성 실패: {pdf}", file=sys.stderr)
        return 1

    # 2) PDF → PNG (페이지별)
    pages = [int(s) for s in args.slides.split(",") if s.strip()] if args.slides else None
    if pages:
        for p in pages:
            subprocess.run(
                ["pdftoppm", "-png", "-r", str(args.dpi), "-f", str(p), "-l", str(p),
                 str(pdf), str(out_dir / "ref")],
                check=True,
                capture_output=True,
            )
    else:
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(args.dpi), str(pdf), str(out_dir / "ref")],
            check=True,
            capture_output=True,
        )

    pngs = sorted(out_dir.glob("ref-*.png"))
    for png in pngs:
        print(png)
    print(f"[ok] {len(pngs)}개 PNG → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
