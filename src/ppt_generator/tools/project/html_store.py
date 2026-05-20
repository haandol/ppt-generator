"""슬라이드 HTML 파일 및 이미지 파일 관리를 전담하는 스토어 모듈."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ppt_generator.interfaces.constants import PROJECT_IMAGES_DIR, PROJECT_SLIDES_DIR
from ppt_generator.interfaces.schemas import PptxImage

logger = logging.getLogger(__name__)


class HtmlStore:
    """슬라이드 HTML 파일과 이미지 파일의 저장/삭제/재번호를 담당한다."""

    @staticmethod
    def _slide_html_filename(index: int) -> str:
        """0-based 인덱스를 slide_01.html 형식 파일명으로 변환."""
        return f"slide_{index + 1:02d}.html"

    @staticmethod
    def _image_filename(slide_index: int, image_index: int) -> str:
        """이미지 파일명 생성: slide_01_img_01.png"""
        return f"slide_{slide_index + 1:02d}_img_{image_index + 1:02d}.png"

    @staticmethod
    def _bg_image_filename(slide_index: int) -> str:
        """배경 이미지 파일명 생성: slide_01_bg.png"""
        return f"slide_{slide_index + 1:02d}_bg.png"

    def save_slide_bg_image(
        self,
        project_dir: Path,
        slide_index: int,
        image_bytes: bytes,
    ) -> str:
        """슬라이드 배경 이미지를 slides/images/에 PNG로 저장하고 상대경로를 반환."""
        if not image_bytes:
            return ""
        images_dir = project_dir / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        fname = self._bg_image_filename(slide_index)
        (images_dir / fname).write_bytes(image_bytes)
        return f"images/{fname}"

    def save_slides_html(
        self,
        project_dir: Path,
        session_id: str,
        slide_htmls: list[str],
        container_html: str,
    ) -> None:
        slides_dir = project_dir / PROJECT_SLIDES_DIR
        if slides_dir.exists():
            for f in slides_dir.glob("slide_*.html"):
                f.unlink()
        slides_dir.mkdir(parents=True, exist_ok=True)
        for i, html in enumerate(slide_htmls):
            fname = self._slide_html_filename(i)
            (slides_dir / fname).write_text(html, encoding="utf-8")
        (project_dir / "slides.html").write_text(container_html, encoding="utf-8")
        meta: dict = {"session_id": session_id}
        (project_dir / "slides_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            "slides/ 저장 완료 (%d 슬라이드): %s", len(slide_htmls), project_dir
        )

    def save_slide_images(
        self,
        project_dir: Path,
        slide_index: int,
        images: list[PptxImage],
    ) -> list[str]:
        """슬라이드의 이미지를 slides/images/ 에 PNG 파일로 저장한다.

        Returns:
            저장된 이미지의 상대경로 리스트 (HTML에서 사용할 경로).
        """
        images_dir = project_dir / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        srcs: list[str] = []
        for i, img in enumerate(images):
            if not img.image_bytes:
                srcs.append("")
                continue
            fname = self._image_filename(slide_index, i)
            (images_dir / fname).write_bytes(img.image_bytes)
            srcs.append(f"images/{fname}")
        return srcs

    def get_slide_image_srcs(
        self,
        project_dir: Path,
        slide_index: int,
        image_count: int,
    ) -> list[str]:
        """슬라이드의 이미지 파일 상대경로 리스트를 반환한다."""
        images_dir = project_dir / PROJECT_IMAGES_DIR
        srcs: list[str] = []
        for i in range(image_count):
            fname = self._image_filename(slide_index, i)
            if (images_dir / fname).exists():
                srcs.append(f"images/{fname}")
            else:
                srcs.append("")
        return srcs

    def save_single_slide_html(
        self,
        project_dir: Path,
        slide_index: int,
        slide_html: str,
    ) -> Path:
        """단일 슬라이드 HTML을 저장하고 파일 경로를 반환한다."""
        slides_dir = project_dir / PROJECT_SLIDES_DIR
        slides_dir.mkdir(parents=True, exist_ok=True)
        fname = self._slide_html_filename(slide_index)
        path = slides_dir / fname
        path.write_text(slide_html, encoding="utf-8")
        logger.info("단일 슬라이드 HTML 저장: %s", path)
        return path

    def move_slide_html(
        self, project_dir: Path, from_index: int, to_index: int
    ) -> None:
        """슬라이드 HTML 파일을 from_index → to_index로 이동하고 재번호한다."""
        slides_dir = project_dir / PROJECT_SLIDES_DIR
        if not slides_dir.exists():
            return
        files = sorted(slides_dir.glob("slide_*.html"))
        count = len(files)
        if from_index < 0 or from_index >= count or to_index < 0 or to_index >= count:
            return
        if from_index == to_index:
            return
        # 내용 읽기
        contents = [f.read_text(encoding="utf-8") for f in files]
        item = contents.pop(from_index)
        contents.insert(to_index, item)
        # 전체 재작성
        for i, content in enumerate(contents):
            (slides_dir / self._slide_html_filename(i)).write_text(
                content, encoding="utf-8"
            )

    def delete_slide_html(self, project_dir: Path, index: int) -> None:
        """슬라이드 HTML 파일을 삭제하고 남은 파일을 재번호한다."""
        slides_dir = project_dir / PROJECT_SLIDES_DIR
        if not slides_dir.exists():
            return
        files = sorted(slides_dir.glob("slide_*.html"))
        if index < 0 or index >= len(files):
            return
        files[index].unlink()
        remaining = sorted(slides_dir.glob("slide_*.html"))
        for i, f in enumerate(remaining):
            new_name = self._slide_html_filename(i)
            f.rename(slides_dir / new_name)

    def shift_slide_htmls(self, project_dir: Path, insert_index: int) -> None:
        """삽입 위치 이후의 슬라이드 HTML 파일을 한 칸씩 뒤로 밀어낸다."""
        slides_dir = project_dir / PROJECT_SLIDES_DIR
        if not slides_dir.exists():
            return
        files = sorted(slides_dir.glob("slide_*.html"))
        count = len(files)
        for i in range(count - 1, insert_index - 1, -1):
            old_name = slides_dir / self._slide_html_filename(i)
            new_name = slides_dir / self._slide_html_filename(i + 1)
            if old_name.exists():
                old_name.rename(new_name)

    # --- 이미지 파일 재번호/시프트/이동 ---

    def _collect_slide_images(
        self,
        images_dir: Path,
        slide_index: int,
    ) -> list[tuple[str, bytes]]:
        """특정 슬라이드의 이미지 파일들을 (파일명, 바이트) 리스트로 수집한다."""
        prefix = f"slide_{slide_index + 1:02d}_img_"
        result: list[tuple[str, bytes]] = []
        if not images_dir.exists():
            return result
        for f in sorted(images_dir.glob(f"{prefix}*")):
            result.append((f.name, f.read_bytes()))
        return result

    def _write_slide_images(
        self,
        images_dir: Path,
        slide_index: int,
        image_data: list[tuple[str, bytes]],
    ) -> None:
        """수집한 이미지 데이터를 새 슬라이드 인덱스로 재작성한다."""
        for img_idx, (_old_name, data) in enumerate(image_data):
            fname = self._image_filename(slide_index, img_idx)
            (images_dir / fname).write_bytes(data)

    def delete_slide_images(
        self,
        project_dir: Path,
        index: int,
        slide_count: int,
    ) -> None:
        """슬라이드 이미지 파일을 삭제하고 남은 파일을 재번호한다."""
        images_dir = project_dir / PROJECT_IMAGES_DIR
        if not images_dir.exists():
            return

        # 1) 삭제 대상 슬라이드의 이미지 삭제
        for f in sorted(images_dir.glob(f"slide_{index + 1:02d}_img_*")):
            f.unlink()

        # 2) 삭제 위치 이후 슬라이드들의 이미지를 수집
        collected: list[tuple[int, list[tuple[str, bytes]]]] = []
        for i in range(index + 1, slide_count):
            imgs = self._collect_slide_images(images_dir, i)
            if imgs:
                collected.append((i, imgs))
                for f in sorted(images_dir.glob(f"slide_{i + 1:02d}_img_*")):
                    f.unlink()

        # 3) 한 칸 앞으로 재작성
        for old_idx, imgs in collected:
            self._write_slide_images(images_dir, old_idx - 1, imgs)

    def shift_slide_images(
        self,
        project_dir: Path,
        insert_index: int,
        slide_count: int,
    ) -> None:
        """삽입 위치 이후의 슬라이드 이미지 파일을 한 칸씩 뒤로 밀어낸다."""
        images_dir = project_dir / PROJECT_IMAGES_DIR
        if not images_dir.exists():
            return

        # 뒤에서부터 한 칸씩 뒤로 밀기
        for i in range(slide_count - 1, insert_index - 1, -1):
            imgs = self._collect_slide_images(images_dir, i)
            if imgs:
                for f in sorted(images_dir.glob(f"slide_{i + 1:02d}_img_*")):
                    f.unlink()
                self._write_slide_images(images_dir, i + 1, imgs)

    def move_slide_images(
        self,
        project_dir: Path,
        from_index: int,
        to_index: int,
        slide_count: int,
    ) -> None:
        """슬라이드 이미지를 from_index → to_index로 이동하고 재번호한다."""
        images_dir = project_dir / PROJECT_IMAGES_DIR
        if not images_dir.exists():
            return
        if from_index == to_index:
            return

        # 모든 슬라이드의 이미지를 수집
        all_images: list[list[tuple[str, bytes]]] = []
        for i in range(slide_count):
            all_images.append(self._collect_slide_images(images_dir, i))

        # 리스트에서 이동
        item = all_images.pop(from_index)
        all_images.insert(to_index, item)

        # 기존 이미지 파일 전부 삭제 후 재작성
        for f in sorted(images_dir.glob("slide_*_img_*")):
            f.unlink()
        for i, imgs in enumerate(all_images):
            if imgs:
                self._write_slide_images(images_dir, i, imgs)
