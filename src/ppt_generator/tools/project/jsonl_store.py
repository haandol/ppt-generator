"""아웃라인/스크립트 파일 CRUD를 전담하는 스토어 모듈.

개별 JSON 파일 구조 (primary):
  outline/slide_01.json, outline/slide_02.json, ...
  script/slide_01.json, script/slide_02.json, ...

JSONL 구조 (legacy fallback):
  outline.jsonl, script.jsonl

legacy JSON 구조 (oldest fallback):
  outline.json, script.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ppt_generator.interfaces.constants import PROJECT_OUTLINE_DIR, PROJECT_SCRIPT_DIR
from ppt_generator.tools.project.slide_file_store import (
    delete_slide_file,
    insert_slide_file,
    move_slide_file,
    renumber_dir,
    slide_filename,
    sorted_slide_files,
)

logger = logging.getLogger(__name__)


class JsonlStore:
    """아웃라인/스크립트의 저장/로드/CRUD를 담당한다.

    개별 JSON 파일 → JSONL → legacy JSON 순으로 fallback한다.
    """

    # --- 전체 저장/로드 ---

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        data = json.loads(outline_json)
        slides = data["slides"]
        self._save_slides_to_dir(project_dir / PROJECT_OUTLINE_DIR, slides)
        logger.info("outline/ 저장 완료 (%d 슬라이드): %s", len(slides), project_dir)

    def save_script(self, project_dir: Path, script_json: str) -> None:
        data = json.loads(script_json)
        slides = data["slides"]
        self._save_slides_to_dir(project_dir / PROJECT_SCRIPT_DIR, slides)
        logger.info("script/ 저장 완료 (%d 슬라이드): %s", len(slides), project_dir)

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

    def load_script(self, project_dir: Path) -> str:
        slides = self._load_slides_from_dir(project_dir / PROJECT_SCRIPT_DIR)
        if slides is not None:
            return json.dumps({"slides": slides}, ensure_ascii=False)
        raise FileNotFoundError(
            f"script 디렉토리가 없습니다: {project_dir / PROJECT_SCRIPT_DIR}"
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

    def load_script_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드 스크립트를 인덱스로 로드한다."""
        return self._load_slide_from_dir(project_dir / PROJECT_SCRIPT_DIR, index)

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
        """script/outline의 슬라이드 수를 반환한다. 없으면 0."""
        for dir_name in (PROJECT_SCRIPT_DIR, PROJECT_OUTLINE_DIR):
            files = sorted_slide_files(project_dir / dir_name)
            if files:
                return len(files)
        return 0

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

    def load_script_or_outline(self, project_dir: Path) -> str:
        """script 우선, 없으면 outline으로 fallback."""
        if sorted_slide_files(project_dir / PROJECT_SCRIPT_DIR):
            return self.load_script(project_dir)
        return self.load_outline(project_dir)

    def load_script_or_outline_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드를 script 우선, 없으면 outline에서 로드한다."""
        if sorted_slide_files(project_dir / PROJECT_SCRIPT_DIR):
            return self.load_script_slide(project_dir, index)
        return self.load_outline_slide(project_dir, index)

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

        # script/ 디렉토리에 해당 인덱스 파일이 존재하면 동기화
        script_dir = project_dir / PROJECT_SCRIPT_DIR
        script_target = script_dir / fname
        if script_target.exists():
            existing = json.loads(script_target.read_text(encoding="utf-8"))
            existing.update({k: v for k, v in data.items() if k != "slide_index"})
            existing["slide_index"] = index
            script_target.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(
                "슬라이드 아웃라인 → script 동기화: index=%d, path=%s",
                index,
                script_target,
            )

    def update_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        """아웃라인/스크립트에서 특정 슬라이드를 교체한다."""
        updated = False
        for dir_name in (PROJECT_SCRIPT_DIR, PROJECT_OUTLINE_DIR):
            updated |= self._update_slide_in_dir(
                project_dir, dir_name, index, slide_json
            )
        if not updated:
            logger.warning(
                "outline/script 파일이 없어 동기화를 건너뜁니다: %s", project_dir
            )

    def _update_slide_in_dir(
        self, project_dir: Path, dir_name: str, index: int, slide_json: str
    ) -> bool:
        directory = project_dir / dir_name
        files = sorted_slide_files(directory)
        if not files:
            return False
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
        logger.info("슬라이드 업데이트 동기화: index=%d, path=%s", index, files[index])
        return True

    def insert_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        """아웃라인/스크립트에 슬라이드를 삽입한다."""
        inserted = False
        for dir_name in (PROJECT_SCRIPT_DIR, PROJECT_OUTLINE_DIR):
            inserted |= self._insert_slide_in_dir(
                project_dir, dir_name, index, slide_json
            )
        if not inserted:
            outline_dir = project_dir / PROJECT_OUTLINE_DIR
            outline_dir.mkdir(exist_ok=True)
            data = json.loads(slide_json)
            data["slide_index"] = index
            (outline_dir / slide_filename(index)).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(
                "outline/script 파일이 없어 outline 디렉토리에 새 파일 생성: index=%d",
                index,
            )

    def _insert_slide_in_dir(
        self, project_dir: Path, dir_name: str, index: int, slide_json: str
    ) -> bool:
        directory = project_dir / dir_name
        files = sorted_slide_files(directory)
        if not files:
            return False
        data = json.loads(slide_json)
        data["slide_index"] = index
        content = json.dumps(data, ensure_ascii=False, indent=2)
        insert_slide_file(directory, index, content)
        logger.info("슬라이드 삽입 동기화: index=%d, dir=%s", index, directory)
        return True

    def delete_outline_slide(self, project_dir: Path, index: int) -> None:
        """아웃라인/스크립트에서 슬라이드를 삭제한다."""
        deleted = False
        for dir_name in (PROJECT_SCRIPT_DIR, PROJECT_OUTLINE_DIR):
            deleted |= self._delete_slide_in_dir(project_dir, dir_name, index)
        if not deleted:
            logger.warning(
                "outline/script 파일이 없어 동기화를 건너뜁니다: %s", project_dir
            )

    def _delete_slide_in_dir(
        self, project_dir: Path, dir_name: str, index: int
    ) -> bool:
        directory = project_dir / dir_name
        files = sorted_slide_files(directory)
        if not files:
            return False
        delete_slide_file(directory, index)
        logger.info("슬라이드 삭제 동기화: index=%d, dir=%s", index, directory)
        return True

    # --- 슬라이드 이동 ---

    def move_outline_slide(
        self, project_dir: Path, from_index: int, to_index: int
    ) -> None:
        """아웃라인/스크립트에서 슬라이드를 from_index → to_index로 이동한다."""
        moved = False
        for dir_name in (PROJECT_SCRIPT_DIR, PROJECT_OUTLINE_DIR):
            moved |= self._move_slide_in_dir(
                project_dir, dir_name, from_index, to_index
            )
        if not moved:
            logger.warning(
                "outline/script 파일이 없어 이동을 건너뜁니다: %s", project_dir
            )

    def _move_slide_in_dir(
        self, project_dir: Path, dir_name: str, from_idx: int, to_idx: int
    ) -> bool:
        directory = project_dir / dir_name
        files = sorted_slide_files(directory)
        if not files:
            return False
        move_slide_file(directory, from_idx, to_idx)
        logger.info(
            "슬라이드 이동 동기화: %d → %d, dir=%s", from_idx, to_idx, directory
        )
        return True
