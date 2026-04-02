"""슬라이드 추가/삭제/이동 시 이미지 파일 및 design spec src 동기화 테스트.

이미지 파일명은 슬라이드 번호에 의존 (slide_01_img_01.png)하므로,
슬라이드 번호 변경 시 이미지 파일 재번호 + design spec src 업데이트가 필요하다.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ppt_generator.interfaces.constants import PROJECT_IMAGES_DIR
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxImage,
    PptxParagraph,
    PptxSlideSpec,
    PptxTextBox,
    PptxTextRun,
)
from ppt_generator.tools.project.html_store import HtmlStore
from ppt_generator.tools.project.service import ProjectService


def _make_slide_spec(title: str, *, image_src: str = "") -> PptxSlideSpec:
    images = []
    if image_src:
        images = [PptxImage(left_px=100, top_px=100, width_px=500, height_px=300, src=image_src)]
    return PptxSlideSpec(
        background_color="#1a1a2e",
        textboxes=[
            PptxTextBox(
                left_px=40, top_px=40, width_px=600, height_px=60,
                paragraphs=[
                    PptxParagraph(runs=[PptxTextRun(text=title, font_size_pt=32, bold=True)]),
                ],
            ),
        ],
        shapes=[],
        images=images,
        speaker_notes="",
    )


def _setup_project_with_images(
    tmp_path: Path, num_slides: int, *, slides_with_images: list[int] | None = None,
) -> tuple[ProjectService, Path]:
    """이미지가 있는 슬라이드를 포함하는 프로젝트 생성.

    Args:
        slides_with_images: 이미지를 포함할 슬라이드 인덱스 목록 (0-based).
            None이면 모든 슬라이드에 이미지 포함.
    """
    if slides_with_images is None:
        slides_with_images = list(range(num_slides))

    svc = ProjectService()
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # project.json
    meta = {"topic": "테스트", "num_slides": num_slides, "steps_completed": {}}
    (project_dir / "project.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8",
    )

    # outline
    outline_data = json.dumps(
        {"slides": [
            {
                "title": f"슬라이드 {i + 1}",
                "content_summary": f"내용 {i + 1}",
                "component_hint": "bullets",
                "speaker_notes": "",
                "slide_type": "content",
            }
            for i in range(num_slides)
        ]},
        ensure_ascii=False,
    )
    svc.save_outline(project_dir, outline_data)

    # design_spec + images
    images_dir = project_dir / PROJECT_IMAGES_DIR
    images_dir.mkdir(parents=True, exist_ok=True)

    slides: list[PptxSlideSpec] = []
    for i in range(num_slides):
        if i in slides_with_images:
            img_src = f"images/slide_{i + 1:02d}_img_01.png"
            spec = _make_slide_spec(f"슬라이드 {i + 1}", image_src=img_src)
            # 실제 이미지 파일 생성
            (images_dir / f"slide_{i + 1:02d}_img_01.png").write_bytes(
                f"PNG_DATA_SLIDE_{i + 1}".encode(),
            )
        else:
            spec = _make_slide_spec(f"슬라이드 {i + 1}")
        slides.append(spec)

    svc.save_design_spec(project_dir, DesignSpec(slides=slides))

    # slides/ HTML
    slides_dir = project_dir / "slides"
    slides_dir.mkdir(exist_ok=True)
    for i in range(num_slides):
        (slides_dir / f"slide_{i + 1:02d}.html").write_text(
            f"<div>slide {i + 1}</div>", encoding="utf-8",
        )

    return svc, project_dir


# ============================================================
# HtmlStore 이미지 파일 삭제 테스트
# ============================================================

class TestHtmlStoreDeleteSlideImages:
    """슬라이드 삭제 시 이미지 파일 삭제 + 재번호 테스트."""

    def test_delete_first_slide_renumbers_images(self, tmp_path: Path) -> None:
        """첫 슬라이드 삭제 → 나머지 이미지 파일이 재번호되어야 함."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.delete_slide_images(project_dir, 0, 3)

        # slide_01_img_01.png 삭제, slide_02→01, slide_03→02
        assert not (images_dir / "slide_03_img_01.png").exists()
        assert (images_dir / "slide_01_img_01.png").exists()
        assert (images_dir / "slide_02_img_01.png").exists()
        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"

    def test_delete_middle_slide_renumbers_images(self, tmp_path: Path) -> None:
        """중간 슬라이드 삭제 → 이후 이미지 파일이 재번호되어야 함."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.delete_slide_images(project_dir, 1, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"
        assert not (images_dir / "slide_03_img_01.png").exists()

    def test_delete_last_slide_removes_images(self, tmp_path: Path) -> None:
        """마지막 슬라이드 삭제 → 해당 이미지만 삭제, 나머지 유지."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.delete_slide_images(project_dir, 2, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"
        assert not (images_dir / "slide_03_img_01.png").exists()

    def test_delete_slide_without_images(self, tmp_path: Path) -> None:
        """이미지 없는 슬라이드 삭제 시에도 나머지 이미지가 올바르게 재번호."""
        svc, project_dir = _setup_project_with_images(
            tmp_path, 3, slides_with_images=[0, 2],
        )
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        # 슬라이드 1 (이미지 없음)을 삭제
        store.delete_slide_images(project_dir, 1, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"
        assert not (images_dir / "slide_03_img_01.png").exists()


# ============================================================
# HtmlStore 이미지 파일 시프트 테스트
# ============================================================

class TestHtmlStoreShiftSlideImages:
    """슬라이드 추가 시 이미지 파일 시프트 테스트."""

    def test_shift_at_beginning(self, tmp_path: Path) -> None:
        """맨 앞에 삽입 → 모든 이미지가 한 칸씩 뒤로 밀림."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.shift_slide_images(project_dir, 0, 3)

        assert not (images_dir / "slide_01_img_01.png").exists()
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert (images_dir / "slide_03_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"
        assert (images_dir / "slide_04_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"

    def test_shift_at_middle(self, tmp_path: Path) -> None:
        """중간에 삽입 → 삽입 위치 이후 이미지만 한 칸 뒤로."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.shift_slide_images(project_dir, 1, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert not (images_dir / "slide_02_img_01.png").exists()
        assert (images_dir / "slide_03_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"
        assert (images_dir / "slide_04_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"

    def test_shift_at_end(self, tmp_path: Path) -> None:
        """맨 뒤에 삽입 → 기존 이미지 유지."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.shift_slide_images(project_dir, 3, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"
        assert (images_dir / "slide_03_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"


# ============================================================
# HtmlStore 이미지 파일 이동 테스트
# ============================================================

class TestHtmlStoreMoveSlideImages:
    """슬라이드 이동 시 이미지 파일 재배치 테스트."""

    def test_move_last_to_first(self, tmp_path: Path) -> None:
        """마지막 슬라이드를 첫 번째로 이동."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.move_slide_images(project_dir, 2, 0, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert (images_dir / "slide_03_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"

    def test_move_first_to_last(self, tmp_path: Path) -> None:
        """첫 번째 슬라이드를 마지막으로 이동."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.move_slide_images(project_dir, 0, 2, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"
        assert (images_dir / "slide_03_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"

    def test_move_same_position(self, tmp_path: Path) -> None:
        """같은 위치로 이동 → 변화 없음."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.move_slide_images(project_dir, 1, 1, 3)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_2"
        assert (images_dir / "slide_03_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"

    def test_move_with_mixed_images(self, tmp_path: Path) -> None:
        """일부 슬라이드만 이미지가 있을 때 이동."""
        svc, project_dir = _setup_project_with_images(
            tmp_path, 4, slides_with_images=[0, 2],
        )
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        # slide 3 (이미지 있음)을 slide 1로 이동: [3, 1, 2, 4]
        store.move_slide_images(project_dir, 2, 0, 4)

        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_3"
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"PNG_DATA_SLIDE_1"
        assert not (images_dir / "slide_03_img_01.png").exists()
        assert not (images_dir / "slide_04_img_01.png").exists()


# ============================================================
# Design spec src 업데이트 테스트
# ============================================================

class TestDesignSpecImageSrcUpdate:
    """슬라이드 번호 변경 후 design spec images[].src 업데이트 테스트."""

    def test_delete_updates_src_in_remaining_slides(self, tmp_path: Path) -> None:
        """슬라이드 삭제 후 남은 슬라이드의 src가 새 인덱스에 맞게 업데이트."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)

        # 첫 슬라이드 삭제
        svc.delete_slide_images(project_dir, 0, 3)
        svc.delete_design_spec_slide(project_dir, 0)
        svc.renumber_design_spec_image_srcs(project_dir)

        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 2
        assert spec.slides[0].images[0].src == "images/slide_01_img_01.png"
        assert spec.slides[1].images[0].src == "images/slide_02_img_01.png"

    def test_shift_updates_src_in_shifted_slides(self, tmp_path: Path) -> None:
        """슬라이드 추가(시프트) 후 시프트된 슬라이드의 src가 업데이트."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)

        svc.shift_slide_images(project_dir, 0, 3)
        # 새 슬라이드를 삽입 (이미지 없음)
        new_spec = _make_slide_spec("새 슬라이드")
        svc.insert_design_spec_slide(project_dir, 0, new_spec)
        svc.renumber_design_spec_image_srcs(project_dir)

        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 4
        assert len(spec.slides[0].images) == 0
        assert spec.slides[1].images[0].src == "images/slide_02_img_01.png"
        assert spec.slides[2].images[0].src == "images/slide_03_img_01.png"
        assert spec.slides[3].images[0].src == "images/slide_04_img_01.png"

    def test_move_updates_src_in_all_slides(self, tmp_path: Path) -> None:
        """슬라이드 이동 후 모든 슬라이드의 src가 새 인덱스에 맞게 업데이트."""
        svc, project_dir = _setup_project_with_images(tmp_path, 3)

        svc.move_slide_images(project_dir, 2, 0, 3)
        svc.move_design_spec_slide(project_dir, 2, 0)
        svc.renumber_design_spec_image_srcs(project_dir)

        spec = svc.load_design_spec(project_dir)
        assert len(spec.slides) == 3
        assert spec.slides[0].images[0].src == "images/slide_01_img_01.png"
        assert spec.slides[1].images[0].src == "images/slide_02_img_01.png"
        assert spec.slides[2].images[0].src == "images/slide_03_img_01.png"


# ============================================================
# 다중 이미지 테스트
# ============================================================

class TestMultipleImagesPerSlide:
    """슬라이드당 여러 이미지가 있을 때의 동기화 테스트."""

    def _setup_multi_image_project(self, tmp_path: Path) -> tuple[ProjectService, Path]:
        svc = ProjectService()
        project_dir = tmp_path / "multi-img"
        project_dir.mkdir()

        meta = {"topic": "테스트", "num_slides": 2, "steps_completed": {}}
        (project_dir / "project.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8",
        )

        outline_data = json.dumps(
            {"slides": [
                {"title": f"슬라이드 {i+1}", "content_summary": f"내용 {i+1}",
                 "component_hint": "bullets", "speaker_notes": "", "slide_type": "content"}
                for i in range(2)
            ]},
            ensure_ascii=False,
        )
        svc.save_outline(project_dir, outline_data)

        images_dir = project_dir / PROJECT_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)

        # slide 1: 2 images, slide 2: 1 image
        (images_dir / "slide_01_img_01.png").write_bytes(b"S1_IMG1")
        (images_dir / "slide_01_img_02.png").write_bytes(b"S1_IMG2")
        (images_dir / "slide_02_img_01.png").write_bytes(b"S2_IMG1")

        slide1 = _make_slide_spec("슬라이드 1")
        slide1 = replace(slide1, images=[
            PptxImage(left_px=10, top_px=10, width_px=100, height_px=100, src="images/slide_01_img_01.png"),
            PptxImage(left_px=200, top_px=10, width_px=100, height_px=100, src="images/slide_01_img_02.png"),
        ])
        slide2 = _make_slide_spec("슬라이드 2")
        slide2 = replace(slide2, images=[
            PptxImage(left_px=10, top_px=10, width_px=100, height_px=100, src="images/slide_02_img_01.png"),
        ])

        svc.save_design_spec(project_dir, DesignSpec(slides=[slide1, slide2]))

        slides_dir = project_dir / "slides"
        slides_dir.mkdir(exist_ok=True)
        for i in range(2):
            (slides_dir / f"slide_{i + 1:02d}.html").write_text(f"<div>slide {i+1}</div>", encoding="utf-8")

        return svc, project_dir

    def test_delete_slide_with_multiple_images(self, tmp_path: Path) -> None:
        """2개 이미지를 가진 슬라이드 삭제 시 모든 이미지가 처리됨."""
        svc, project_dir = self._setup_multi_image_project(tmp_path)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        store.delete_slide_images(project_dir, 0, 2)

        # slide_01_img_01, slide_01_img_02 삭제
        # slide_02_img_01 → slide_01_img_01
        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"S2_IMG1"
        assert not (images_dir / "slide_01_img_02.png").exists()
        assert not (images_dir / "slide_02_img_01.png").exists()

    def test_move_slide_with_multiple_images(self, tmp_path: Path) -> None:
        """2개 이미지를 가진 슬라이드를 이동하면 모든 이미지가 재배치."""
        svc, project_dir = self._setup_multi_image_project(tmp_path)
        images_dir = project_dir / PROJECT_IMAGES_DIR
        store = HtmlStore()

        # slide 1 (2 images) → slide 2 위치로 이동
        store.move_slide_images(project_dir, 0, 1, 2)

        # 원래 slide 2 → slide 1, 원래 slide 1 → slide 2
        assert (images_dir / "slide_01_img_01.png").read_bytes() == b"S2_IMG1"
        assert not (images_dir / "slide_01_img_02.png").exists()
        assert (images_dir / "slide_02_img_01.png").read_bytes() == b"S1_IMG1"
        assert (images_dir / "slide_02_img_02.png").read_bytes() == b"S1_IMG2"
