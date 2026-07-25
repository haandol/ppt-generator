#!/usr/bin/env python3
"""PPTX → PNG 변환 스크립트 (LibreOffice 기반).

LibreOffice로 PPTX를 PDF로 변환한 뒤 pdf2image로 각 페이지를 PNG로 저장합니다.

사전 요구사항:
    - LibreOffice: brew install --cask libreoffice
    - pdf2image: uv pip install pdf2image
    - poppler: brew install poppler

사용법:
    python scripts/pptx_to_png.py /path/to/presentation.pptx
    python scripts/pptx_to_png.py /path/to/presentation.pptx --output-dir ./slides
    python scripts/pptx_to_png.py /path/to/presentation.pptx --dpi 150
"""

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def find_libreoffice() -> str | None:
    """LibreOffice 실행 파일 경로를 찾는다."""
    # macOS
    mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if Path(mac_path).exists():
        return mac_path
    # PATH에 있는 경우
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    return soffice


def pptx_to_png(pptx_path: Path, output_dir: Path, dpi: int = 150) -> list[Path]:
    """LibreOffice로 PPTX→PDF 변환 후 pdf2image로 PNG 생성."""
    if not pptx_path.exists():
        logger.error("파일을 찾을 수 없습니다: %s", pptx_path)
        sys.exit(1)

    soffice = find_libreoffice()
    if not soffice:
        logger.error(
            "LibreOffice를 찾을 수 없습니다. 설치해주세요: brew install --cask libreoffice"
        )
        sys.exit(1)

    try:
        from pdf2image import convert_from_path
    except ImportError:
        logger.error("pdf2image가 필요합니다: uv pip install pdf2image")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) PPTX → PDF (LibreOffice)
    with tempfile.TemporaryDirectory() as tmp_dir:
        logger.info("PPTX → PDF 변환 중 (LibreOffice)...")
        cmd = [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            tmp_dir,
            str(pptx_path.resolve()),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error("LibreOffice 변환 실패: %s", result.stderr)
            sys.exit(1)

        pdf_path = Path(tmp_dir) / (pptx_path.stem + ".pdf")
        if not pdf_path.exists():
            # LibreOffice가 다른 이름으로 생성했을 수 있음
            pdfs = list(Path(tmp_dir).glob("*.pdf"))
            if not pdfs:
                logger.error("PDF 파일이 생성되지 않았습니다.")
                sys.exit(1)
            pdf_path = pdfs[0]

        logger.info("PDF 생성 완료: %s", pdf_path.name)

        # 2) PDF → PNG (pdf2image)
        logger.info("PDF → PNG 변환 중 (DPI=%d)...", dpi)
        images = convert_from_path(str(pdf_path), dpi=dpi)

    max_width, max_height = 1024, 768

    png_files: list[Path] = []
    for idx, image in enumerate(images):
        png_path = output_dir / f"slide_{idx + 1:03d}.png"
        if image.width > max_width or image.height > max_height:
            image.thumbnail((max_width, max_height))
        image.save(str(png_path), "PNG")
        png_files.append(png_path)
        logger.info("  %s (%dx%d)", png_path.name, image.width, image.height)

    logger.info("변환 완료: %d장 → %s", len(png_files), output_dir)
    return png_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PPTX → PNG 변환 (LibreOffice + pdf2image)"
    )
    parser.add_argument("pptx_file", type=Path, help="변환할 PPTX 파일 경로")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="PNG 출력 디렉토리 (기본: PPTX 파일과 같은 디렉토리의 png_pptx/)",
    )
    parser.add_argument(
        "--dpi", type=int, default=150, help="PNG 해상도 DPI (기본: 150)"
    )
    args = parser.parse_args()

    output_dir = args.output_dir or (args.pptx_file.parent / "png_pptx")
    pptx_to_png(args.pptx_file, output_dir, args.dpi)


if __name__ == "__main__":
    main()
