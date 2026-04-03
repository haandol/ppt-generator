"""이미지 동기화 및 바이트 복원을 전담하는 스토어 모듈."""

from __future__ import annotations

import logging
import shutil
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

from ppt_generator.interfaces.constants import PROJECT_IMAGES_DIR, PROJECT_SLIDES_DIR
from ppt_generator.interfaces.protocols import LoadDesignSpecFn, SaveSlideFn
from ppt_generator.interfaces.schemas import DesignSpec, PptxImage, PptxSlideSpec
from ppt_generator.tools.project.html_store import HtmlStore

logger = logging.getLogger(__name__)

_IMAGE_URL_TIMEOUT = 30  # seconds


def _download_image(url: str) -> bytes:
    """외부 URL에서 이미지를 다운로드한다."""
    import httpx

    resp = httpx.get(url, timeout=_IMAGE_URL_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def _is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")


def _guess_ext_from_url(url: str) -> str:
    """URL에서 이미지 확장자를 추측한다. 기본값 .png."""
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"):
        if path.endswith(ext):
            return ext
    return ".png"


class ImageStore:
    """이미지 경로 동기화 및 바이트 복원을 담당한다."""

    def __init__(self, html_store: HtmlStore | None = None) -> None:
        self._html_store = html_store or HtmlStore()

    def sync_image_paths(
        self,
        project_dir: Path,
        design_spec: DesignSpec,
        save_slide_fn: SaveSlideFn,
    ) -> DesignSpec:
        """image_path가 있지만 src가 없는 이미지를 slides/images/에 복사하고 src를 설정한다.

        로컬 파일과 외부 URL 모두 지원한다. 변경된 슬라이드는 save_slide_fn으로 저장한다.
        """
        updated_slides: list[PptxSlideSpec] = []
        changed = False
        for idx, slide in enumerate(design_spec.slides):
            new_images: list[PptxImage] = []
            slide_changed = False
            for img_i, img in enumerate(slide.images):
                if img.image_path and not img.src:
                    resolved = self._sync_single_image(project_dir, idx, img_i, img)
                    if resolved is not img:
                        slide_changed = True
                    new_images.append(resolved)
                else:
                    new_images.append(img)
            if slide_changed:
                updated_slide = replace(slide, images=new_images)
                updated_slides.append(updated_slide)
                save_slide_fn(project_dir, idx, updated_slide)
                changed = True
            else:
                updated_slides.append(slide)
        if changed:
            return DesignSpec(slides=updated_slides)
        return design_spec

    def _sync_single_image(
        self,
        project_dir: Path,
        slide_idx: int,
        img_idx: int,
        img: PptxImage,
    ) -> PptxImage:
        """단일 이미지의 image_path를 slides/images/에 동기화한다."""
        images_dir = project_dir / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        fname = self._html_store._image_filename(slide_idx, img_idx)

        if _is_url(img.image_path):
            ext = _guess_ext_from_url(img.image_path)
            if ext != ".png":
                fname = fname.rsplit(".", 1)[0] + ext
            dest = images_dir / fname
            if not dest.exists():
                try:
                    data = _download_image(img.image_path)
                    dest.write_bytes(data)
                    logger.info("이미지 다운로드: %s → %s", img.image_path, dest)
                except Exception:
                    logger.warning(
                        "이미지 다운로드 실패: %s", img.image_path, exc_info=True
                    )
                    return img
            return replace(img, src=f"images/{fname}")

        # 로컬 파일
        abs_path = Path(img.image_path)
        if not abs_path.exists():
            logger.warning("image_path 파일 없음: %s", abs_path)
            return img
        ext = abs_path.suffix.lower()
        if ext and ext != ".png":
            fname = fname.rsplit(".", 1)[0] + ext
        dest = images_dir / fname
        if not dest.exists():
            shutil.copy2(str(abs_path), str(dest))
            logger.info("이미지 복사: %s → %s", abs_path, dest)
        return replace(img, src=f"images/{fname}")

    @staticmethod
    def resolve_image_bytes(img: PptxImage, slides_dir: Path) -> PptxImage:
        """이미지 바이트를 src 또는 image_path로부터 복원한다."""
        if img.src:
            img_path = slides_dir / img.src
            if img_path.exists():
                return replace(img, image_bytes=img_path.read_bytes())
            # LLM이 src를 'images/' prefix 없이 생성한 경우 fallback
            if not img.src.startswith("images/"):
                fallback_path = slides_dir / "images" / img.src
                if fallback_path.exists():
                    return replace(img, image_bytes=fallback_path.read_bytes())
            logger.warning("이미지 파일 없음 (src): %s", img_path)
        if img.image_path:
            if _is_url(img.image_path):
                try:
                    data = _download_image(img.image_path)
                    return replace(img, image_bytes=data)
                except Exception:
                    logger.warning(
                        "이미지 다운로드 실패: %s", img.image_path, exc_info=True
                    )
            else:
                abs_path = Path(img.image_path)
                if abs_path.exists():
                    return replace(img, image_bytes=abs_path.read_bytes())
                logger.warning("이미지 파일 없음 (image_path): %s", abs_path)
        return img

    def load_design_spec_with_images(
        self,
        project_dir: Path,
        load_spec_fn: LoadDesignSpecFn,
    ) -> DesignSpec:
        """design spec을 로드한 후, 각 이미지의 src/image_path로부터 image_bytes를 복원한다."""
        spec = load_spec_fn(project_dir)
        slides_dir = project_dir / PROJECT_SLIDES_DIR
        updated_slides: list[PptxSlideSpec] = []
        for slide in spec.slides:
            new_images = [
                self.resolve_image_bytes(img, slides_dir) for img in slide.images
            ]
            if new_images != list(slide.images):
                updated_slides.append(replace(slide, images=new_images))
            else:
                updated_slides.append(slide)
        return DesignSpec(slides=updated_slides)
