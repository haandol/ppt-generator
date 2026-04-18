"""아웃라인 파일 CRUD를 전담하는 스토어 모듈.

개별 JSON 파일 구조:
  outline/slide_01.json, outline/slide_02.json, ...
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ppt_generator.interfaces.constants import PROJECT_OUTLINE_DIR
from ppt_generator.tools.project.slide_file_store import (
    delete_slide_file,
    insert_slide_file,
    move_slide_file,
    slide_filename,
    sorted_slide_files,
)

logger = logging.getLogger(__name__)


class JsonlStore:
    """아웃라인의 저장/로드/CRUD를 담당한다."""

    # --- 전체 저장/로드 ---

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        data = json.loads(outline_json)
        slides = data["slides"]
        self._save_slides_to_dir(project_dir / PROJECT_OUTLINE_DIR, slides)
        logger.info("outline/ 저장 완료 (%d 슬라이드): %s", len(slides), project_dir)

    @staticmethod
    def _save_slides_to_dir(directory: Path, slides: list[dict]) -> None:
        """슬라이드 리스트를 개별 JSON 파일로 저장한다. 기존 디렉토리는 덮어쓴다."""
        import shutil

        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        for i, s in enumerate(slides):
            s["slide_index"] = i
            fname = slide_filename(i)
            (directory / fname).write_text(
                json.dumps(s, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def load_outline(self, project_dir: Path) -> str:
        slides = self._load_slides_from_dir(project_dir / PROJECT_OUTLINE_DIR)
        if slides is not None:
            return json.dumps({"slides": slides}, ensure_ascii=False)
        raise FileNotFoundError(
            f"outline 디렉토리가 없습니다: {project_dir / PROJECT_OUTLINE_DIR}"
        )

    @staticmethod
    def _load_slides_from_dir(directory: Path) -> list[dict] | None:
        """개별 JSON 파일에서 슬라이드를 로드한다. 디렉토리가 없으면 None."""
        files = sorted_slide_files(directory)
        if not files:
            return None
        return [json.loads(f.read_text(encoding="utf-8")) for f in files]

    # --- 개별 슬라이드 로드 ---

    def load_outline_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드 아웃라인을 인덱스로 로드한다."""
        return self._load_slide_from_dir(project_dir / PROJECT_OUTLINE_DIR, index)

    @staticmethod
    def _load_slide_from_dir(directory: Path, index: int) -> str:
        files = sorted_slide_files(directory)
        if not files:
            raise FileNotFoundError(f"슬라이드 디렉토리가 없습니다: {directory}")
        target = directory / slide_filename(index)
        if target.exists():
            return target.read_text(encoding="utf-8")
        raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(files)}장)")

    def get_outline_slide_count(self, project_dir: Path) -> int:
        """outline의 슬라이드 수를 반환한다. 없으면 0."""
        files = sorted_slide_files(project_dir / PROJECT_OUTLINE_DIR)
        return len(files) if files else 0

    _PLACEHOLDER_OUTLINE: dict = {
        "title": "",
        "content_summary": "",
        "slide_type": "content",
        "component_hint": "bullets",
        "speaker_notes": "",
    }

    def sync_outline_to_design_spec_count(
        self,
        project_dir: Path,
        design_spec_count: int,
    ) -> bool:
        """outline 수를 design_spec 수에 맞춰 placeholder로 채운다."""
        outline_dir = project_dir / PROJECT_OUTLINE_DIR
        files = sorted_slide_files(outline_dir)
        current_count = len(files)

        if current_count == 0:
            outline_dir.mkdir(parents=True, exist_ok=True)
            for i in range(design_spec_count):
                data = {**self._PLACEHOLDER_OUTLINE, "slide_index": i}
                (outline_dir / slide_filename(i)).write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            logger.info(
                "outline 전체 placeholder 생성: %d장, dir=%s",
                design_spec_count,
                outline_dir,
            )
            return True

        if current_count >= design_spec_count:
            return False

        for i in range(current_count, design_spec_count):
            data = {**self._PLACEHOLDER_OUTLINE, "slide_index": i}
            (outline_dir / slide_filename(i)).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        logger.info(
            "outline placeholder 패딩: %d → %d장, dir=%s",
            current_count,
            design_spec_count,
            outline_dir,
        )
        return True

    # --- 개별 슬라이드 CRUD ---

    def save_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        """개별 슬라이드 아웃라인을 저장한다."""
        data = json.loads(slide_json)
        data["slide_index"] = index
        serialized = json.dumps(data, ensure_ascii=False, indent=2)
        fname = slide_filename(index)

        outline_dir = project_dir / PROJECT_OUTLINE_DIR
        outline_dir.mkdir(parents=True, exist_ok=True)
        (outline_dir / fname).write_text(serialized, encoding="utf-8")
        logger.info(
            "슬라이드 아웃라인 저장: index=%d, path=%s", index, outline_dir / fname
        )

    def update_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        """아웃라인에서 특정 슬라이드를 교체한다."""
        directory = project_dir / PROJECT_OUTLINE_DIR
        files = sorted_slide_files(directory)
        if not files:
            logger.warning("outline 파일이 없어 업데이트를 건너뜁니다: %s", project_dir)
            return
        if index < 0 or index >= len(files):
            raise IndexError(
                f"유효하지 않은 slide index: {index} (전체 {len(files)}장)"
            )
        existing = json.loads(files[index].read_text(encoding="utf-8"))
        new_data = json.loads(slide_json)
        existing.update({k: v for k, v in new_data.items() if k != "slide_index"})
        existing["slide_index"] = index
        files[index].write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("슬라이드 업데이트: index=%d, path=%s", index, files[index])

    def insert_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        """아웃라인에 슬라이드를 삽입한다."""
        outline_dir = project_dir / PROJECT_OUTLINE_DIR
        files = sorted_slide_files(outline_dir)
        if not files:
            outline_dir.mkdir(exist_ok=True)
            data = json.loads(slide_json)
            data["slide_index"] = index
            (outline_dir / slide_filename(index)).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("outline 파일이 없어 새 파일 생성: index=%d", index)
            return
        data = json.loads(slide_json)
        data["slide_index"] = index
        content = json.dumps(data, ensure_ascii=False, indent=2)
        insert_slide_file(outline_dir, index, content)
        logger.info("슬라이드 삽입: index=%d, dir=%s", index, outline_dir)

    def delete_outline_slide(self, project_dir: Path, index: int) -> None:
        """아웃라인에서 슬라이드를 삭제한다."""
        directory = project_dir / PROJECT_OUTLINE_DIR
        files = sorted_slide_files(directory)
        if not files:
            logger.warning("outline 파일이 없어 삭제를 건너뜁니다: %s", project_dir)
            return
        delete_slide_file(directory, index)
        logger.info("슬라이드 삭제: index=%d, dir=%s", index, directory)

    # --- 슬라이드 이동 ---

    def move_outline_slide(
        self, project_dir: Path, from_index: int, to_index: int
    ) -> None:
        """아웃라인에서 슬라이드를 from_index → to_index로 이동한다."""
        directory = project_dir / PROJECT_OUTLINE_DIR
        files = sorted_slide_files(directory)
        if not files:
            logger.warning("outline 파일이 없어 이동을 건너뜁니다: %s", project_dir)
            return
        move_slide_file(directory, from_index, to_index)
        logger.info("슬라이드 이동: %d → %d, dir=%s", from_index, to_index, directory)
