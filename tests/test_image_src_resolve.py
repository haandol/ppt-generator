"""이미지 src에 'images/' prefix가 없을 때의 resolve_image_bytes 및 renumber 테스트.

LLM이 design spec을 생성할 때 src를 'slide_01_img_01.png' (images/ prefix 누락)으로
설정할 수 있다. 이 경우에도 image_bytes가 올바르게 복원되어야 한다.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ppt_generator.interfaces.constants import PROJECT_IMAGES_DIR, PROJECT_SLIDES_DIR
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxImage,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.project.image_store import ImageStore
from ppt_generator.tools.project.service import ProjectService


def _make_slide_spec(
    title: str, *, images: list[PptxImage] | None = None
) -> PptxSlideSpec:
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=[
            PptxTextBox(
                left_px=40,
                top_px=40,
                width_px=600,
                height_px=60,
                paragraphs=[
                    PptxParagraph(
                        runs=[PptxTextRun(text=title, font_size_pt=32, bold=True)]
                    ),
                ],
            ),
        ],
        shapes=[],
        images=images or [],
        speaker_notes="",
    )


def _setup_project(
    tmp_path: Path, slides: list[PptxSlideSpec]
) -> tuple[ProjectService, Path]:
    """이미지 파일이 slides/images/ 에 있는 프로젝트를 생성."""
    svc = ProjectService()
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    meta = {"topic": "테스트", "num_slides": len(slides), "steps_completed": {}}
    (project_dir / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    outline_data = json.dumps(
        {
            "slides": [
                {
                    "title": f"슬라이드 {i + 1}",
                    "content_summary": f"내용 {i + 1}",
                    "component_hint": "bullets",
                    "speaker_notes": "",
                    "slide_type": "content",
                }
                for i in range(len(slides))
            ]
        },
        ensure_ascii=False,
    )
    svc.save_outline(project_dir, outline_data)
    svc.save_design_spec(project_dir, DesignSpec(slides=slides))

    return svc, project_dir


# ============================================================
# resolve_image_bytes: images/ prefix 누락 시 fallback
# ============================================================


class TestResolveImageBytesMissingPrefix:
    """src에 'images/' prefix가 없을 때 resolve_image_bytes가 fallback으로 찾아야 함."""

    def test_src_without_images_prefix_resolves(self, tmp_path: Path) -> None:
        """src='slide_01_img_01.png' → slides/images/slide_01_img_01.png에서 바이트 복원."""
        images_dir = tmp_path / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True)
        (images_dir / "slide_01_img_01.png").write_bytes(b"PNG_DATA")

        slides_dir = tmp_path / PROJECT_SLIDES_DIR

        img = PptxImage(
            left_px=0,
            top_px=0,
            width_px=100,
            height_px=100,
            src="slide_01_img_01.png",
        )

        result = ImageStore.resolve_image_bytes(img, slides_dir)
        assert result.image_bytes == b"PNG_DATA"

    def test_src_with_images_prefix_still_works(self, tmp_path: Path) -> None:
        """src='images/slide_01_img_01.png' → 기존 경로로 정상 복원."""
        images_dir = tmp_path / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True)
        (images_dir / "slide_01_img_01.png").write_bytes(b"PNG_DATA")

        slides_dir = tmp_path / PROJECT_SLIDES_DIR

        img = PptxImage(
            left_px=0,
            top_px=0,
            width_px=100,
            height_px=100,
            src="images/slide_01_img_01.png",
        )

        result = ImageStore.resolve_image_bytes(img, slides_dir)
        assert result.image_bytes == b"PNG_DATA"

    def test_src_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """파일이 없는 경우 빈 바이트 반환."""
        slides_dir = tmp_path / PROJECT_SLIDES_DIR
        slides_dir.mkdir(parents=True)

        img = PptxImage(
            left_px=0,
            top_px=0,
            width_px=100,
            height_px=100,
            src="nonexistent.png",
        )

        result = ImageStore.resolve_image_bytes(img, slides_dir)
        assert result.image_bytes == b""


# ============================================================
# load_design_spec_with_images: prefix 누락된 src 처리
# ============================================================


class TestLoadDesignSpecWithImagesMissingPrefix:
    """load_design_spec_with_images가 src에 images/ prefix 없는 경우에도 동작."""

    def test_loads_images_without_prefix(self, tmp_path: Path) -> None:
        """design spec의 src가 'slide_01_img_01.png'이어도 image_bytes 복원."""
        img = PptxImage(
            left_px=0,
            top_px=0,
            width_px=1280,
            height_px=720,
            src="slide_01_img_01.png",
        )
        slide = _make_slide_spec("타이틀", images=[img])
        svc, project_dir = _setup_project(tmp_path, [slide])

        images_dir = project_dir / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "slide_01_img_01.png").write_bytes(b"BG_IMAGE_DATA")

        loaded = svc.load_design_spec_with_images(project_dir)
        assert loaded.slides[0].images[0].image_bytes == b"BG_IMAGE_DATA"

    def test_loads_images_with_prefix(self, tmp_path: Path) -> None:
        """정상적인 src 'images/slide_01_img_01.png'도 여전히 동작."""
        img = PptxImage(
            left_px=0,
            top_px=0,
            width_px=1280,
            height_px=720,
            src="images/slide_01_img_01.png",
        )
        slide = _make_slide_spec("타이틀", images=[img])
        svc, project_dir = _setup_project(tmp_path, [slide])

        images_dir = project_dir / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "slide_01_img_01.png").write_bytes(b"BG_IMAGE_DATA")

        loaded = svc.load_design_spec_with_images(project_dir)
        assert loaded.slides[0].images[0].image_bytes == b"BG_IMAGE_DATA"

    def test_multiple_slides_mixed_prefix(self, tmp_path: Path) -> None:
        """여러 슬라이드에서 prefix 있는/없는 src가 혼재해도 모두 복원."""
        img1 = PptxImage(
            left_px=0,
            top_px=0,
            width_px=1280,
            height_px=720,
            src="slide_01_img_01.png",  # prefix 없음
        )
        img2 = PptxImage(
            left_px=760,
            top_px=184,
            width_px=360,
            height_px=360,
            src="images/slide_02_img_01.png",  # prefix 있음
        )
        slide1 = _make_slide_spec("슬라이드 1", images=[img1])
        slide2 = _make_slide_spec("슬라이드 2", images=[img2])
        svc, project_dir = _setup_project(tmp_path, [slide1, slide2])

        images_dir = project_dir / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "slide_01_img_01.png").write_bytes(b"IMG1_DATA")
        (images_dir / "slide_02_img_01.png").write_bytes(b"IMG2_DATA")

        loaded = svc.load_design_spec_with_images(project_dir)
        assert loaded.slides[0].images[0].image_bytes == b"IMG1_DATA"
        assert loaded.slides[1].images[0].image_bytes == b"IMG2_DATA"


# ============================================================
# renumber_design_spec_image_srcs: prefix 교정
# ============================================================


class TestRenumberFixesPrefix:
    """renumber_design_spec_image_srcs가 prefix 없는 src를 올바르게 교정."""

    def test_renumber_adds_prefix(self, tmp_path: Path) -> None:
        """src='slide_01_img_01.png' → 'images/slide_01_img_01.png' 으로 교정."""
        img = PptxImage(
            left_px=0,
            top_px=0,
            width_px=1280,
            height_px=720,
            src="slide_01_img_01.png",
        )
        slide = _make_slide_spec("타이틀", images=[img])
        svc, project_dir = _setup_project(tmp_path, [slide])

        svc.renumber_design_spec_image_srcs(project_dir)

        spec = svc.load_design_spec(project_dir)
        assert spec.slides[0].images[0].src == "images/slide_01_img_01.png"

    def test_renumber_preserves_correct_prefix(self, tmp_path: Path) -> None:
        """이미 올바른 src는 변경하지 않음."""
        img = PptxImage(
            left_px=0,
            top_px=0,
            width_px=1280,
            height_px=720,
            src="images/slide_01_img_01.png",
        )
        slide = _make_slide_spec("타이틀", images=[img])
        svc, project_dir = _setup_project(tmp_path, [slide])

        svc.renumber_design_spec_image_srcs(project_dir)

        spec = svc.load_design_spec(project_dir)
        assert spec.slides[0].images[0].src == "images/slide_01_img_01.png"
