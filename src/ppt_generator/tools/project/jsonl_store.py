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
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

OUTLINE_DIR = "outline"
SCRIPT_DIR = "script"


class JsonlStore:
    """아웃라인/스크립트의 저장/로드/CRUD를 담당한다.

    개별 JSON 파일 → JSONL → legacy JSON 순으로 fallback한다.
    """

    # --- 파일명 유틸 ---

    @staticmethod
    def _slide_filename(index: int) -> str:
        """0-based 인덱스를 slide_01.json 형식 파일명으로 변환."""
        return f"slide_{index + 1:02d}.json"

    @staticmethod
    def _sorted_slide_files(directory: Path) -> list[Path]:
        """디렉토리 내 slide_*.json 파일을 정렬해서 반환."""
        if not directory.exists():
            return []
        return sorted(directory.glob("slide_*.json"))

    # --- 전체 저장/로드 ---

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        data = json.loads(outline_json)
        slides = data["slides"]
        self._save_slides_to_dir(project_dir / OUTLINE_DIR, slides)
        logger.info("outline/ 저장 완료 (%d 슬라이드): %s", len(slides), project_dir)

    def save_script(self, project_dir: Path, script_json: str) -> None:
        data = json.loads(script_json)
        slides = data["slides"]
        self._save_slides_to_dir(project_dir / SCRIPT_DIR, slides)
        logger.info("script/ 저장 완료 (%d 슬라이드): %s", len(slides), project_dir)

    def _save_slides_to_dir(self, directory: Path, slides: list[dict]) -> None:
        """슬라이드 리스트를 개별 JSON 파일로 저장한다. 기존 디렉토리는 덮어쓴다."""
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        for i, s in enumerate(slides):
            s["slide_index"] = i
            fname = self._slide_filename(i)
            (directory / fname).write_text(
                json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8",
            )

    def load_outline(self, project_dir: Path) -> str:
        slides = self._load_slides_from_dir(project_dir / OUTLINE_DIR)
        if slides is not None:
            return json.dumps({"slides": slides}, ensure_ascii=False)
        # fallback: JSONL
        jsonl = project_dir / "outline.jsonl"
        if jsonl.exists():
            lines = [json.loads(ln) for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            return json.dumps({"slides": lines}, ensure_ascii=False)
        # fallback: legacy JSON
        legacy = project_dir / "outline.json"
        return legacy.read_text(encoding="utf-8")

    def load_script(self, project_dir: Path) -> str:
        slides = self._load_slides_from_dir(project_dir / SCRIPT_DIR)
        if slides is not None:
            return json.dumps({"slides": slides}, ensure_ascii=False)
        # fallback: JSONL
        jsonl = project_dir / "script.jsonl"
        if jsonl.exists():
            lines = [json.loads(ln) for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            return json.dumps({"slides": lines}, ensure_ascii=False)
        # fallback: legacy JSON
        legacy = project_dir / "script.json"
        return legacy.read_text(encoding="utf-8")

    def _load_slides_from_dir(self, directory: Path) -> list[dict] | None:
        """개별 JSON 파일에서 슬라이드를 로드한다. 디렉토리가 없으면 None."""
        files = self._sorted_slide_files(directory)
        if not files:
            return None
        return [json.loads(f.read_text(encoding="utf-8")) for f in files]

    # --- 개별 슬라이드 로드 ---

    def load_outline_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드 아웃라인을 인덱스로 로드한다."""
        return self._load_slide_from_dir_or_fallback(
            project_dir, OUTLINE_DIR, "outline.jsonl", "outline.json", index,
        )

    def load_script_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드 스크립트를 인덱스로 로드한다."""
        return self._load_slide_from_dir_or_fallback(
            project_dir, SCRIPT_DIR, "script.jsonl", "script.json", index,
        )

    def _load_slide_from_dir_or_fallback(
        self, project_dir: Path, dir_name: str, jsonl_name: str, legacy_name: str, index: int,
    ) -> str:
        # 1) 개별 파일 (파일명 기반 인덱스 접근 — sparse 지원)
        directory = project_dir / dir_name
        files = self._sorted_slide_files(directory)
        if files:
            target = directory / self._slide_filename(index)
            if target.exists():
                return target.read_text(encoding="utf-8")
            # 디렉토리에 파일이 있지만 해당 인덱스가 없음
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(files)}장)")
        # 2) JSONL fallback
        jsonl = project_dir / jsonl_name
        if jsonl.exists():
            lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if index < 0 or index >= len(lines):
                raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
            return lines[index]
        # 3) legacy JSON fallback
        legacy = project_dir / legacy_name
        data = json.loads(legacy.read_text(encoding="utf-8"))
        slides = data["slides"]
        if index < 0 or index >= len(slides):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(slides)}장)")
        return json.dumps(slides[index], ensure_ascii=False)

    def load_script_or_outline(self, project_dir: Path) -> str:
        """script 우선, 없으면 outline으로 fallback."""
        # script 개별 파일
        if self._sorted_slide_files(project_dir / SCRIPT_DIR):
            return self.load_script(project_dir)
        # script JSONL
        if (project_dir / "script.jsonl").exists():
            return self.load_script(project_dir)
        # script legacy JSON
        if (project_dir / "script.json").exists():
            return self.load_script(project_dir)
        return self.load_outline(project_dir)

    def load_script_or_outline_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드를 script 우선, 없으면 outline에서 로드한다."""
        # script 개별 파일
        if self._sorted_slide_files(project_dir / SCRIPT_DIR):
            return self.load_script_slide(project_dir, index)
        # script JSONL
        if (project_dir / "script.jsonl").exists():
            return self.load_script_slide(project_dir, index)
        return self.load_outline_slide(project_dir, index)

    # --- 개별 슬라이드 CRUD ---

    def save_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        """개별 슬라이드 아웃라인을 저장한다. 파일이 없으면 새로 생성한다.

        outline/ 디렉토리에 저장하고, script/ 디렉토리에 해당 인덱스 파일이 존재하면
        동일한 내용으로 덮어써서 source of truth를 동기화한다.
        """
        data = json.loads(slide_json)
        data["slide_index"] = index
        serialized = json.dumps(data, ensure_ascii=False, indent=2)
        fname = self._slide_filename(index)

        # outline/ 저장
        outline_dir = project_dir / OUTLINE_DIR
        outline_dir.mkdir(parents=True, exist_ok=True)
        (outline_dir / fname).write_text(serialized, encoding="utf-8")
        logger.info("슬라이드 아웃라인 저장: index=%d, path=%s", index, outline_dir / fname)

        # script/ 디렉토리에 해당 인덱스 파일이 존재하면 동기화
        script_dir = project_dir / SCRIPT_DIR
        script_target = script_dir / fname
        if script_target.exists():
            existing = json.loads(script_target.read_text(encoding="utf-8"))
            existing.update({k: v for k, v in data.items() if k != "slide_index"})
            existing["slide_index"] = index
            script_target.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            logger.info("슬라이드 아웃라인 → script 동기화: index=%d, path=%s", index, script_target)

    def update_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        """아웃라인/스크립트에서 특정 슬라이드를 교체한다."""
        updated = False
        for dir_name, jsonl_name in ((SCRIPT_DIR, "script.jsonl"), (OUTLINE_DIR, "outline.jsonl")):
            updated |= self._update_slide_in_dir(project_dir, dir_name, index, slide_json)
            updated |= self._update_slide_in_jsonl(project_dir, jsonl_name, index, slide_json)
        if not updated:
            logger.warning("outline/script 파일이 없어 동기화를 건너뜁니다: %s", project_dir)

    def _update_slide_in_dir(self, project_dir: Path, dir_name: str, index: int, slide_json: str) -> bool:
        directory = project_dir / dir_name
        files = self._sorted_slide_files(directory)
        if not files:
            return False
        if index < 0 or index >= len(files):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(files)}장)")
        existing = json.loads(files[index].read_text(encoding="utf-8"))
        new_data = json.loads(slide_json)
        existing.update({k: v for k, v in new_data.items() if k != "slide_index"})
        existing["slide_index"] = index
        files[index].write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("슬라이드 업데이트 동기화: index=%d, path=%s", index, files[index])
        return True

    def _update_slide_in_jsonl(self, project_dir: Path, jsonl_name: str, index: int, slide_json: str) -> bool:
        path = project_dir / jsonl_name
        if not path.exists():
            return False
        lines = self._load_jsonl_lines(path)
        if index < 0 or index >= len(lines):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
        existing = json.loads(lines[index])
        new_data = json.loads(slide_json)
        existing.update({k: v for k, v in new_data.items() if k != "slide_index"})
        lines[index] = json.dumps(existing, ensure_ascii=False)
        self._save_jsonl_lines(path, lines)
        logger.info("슬라이드 업데이트 동기화 (JSONL): index=%d, path=%s", index, path)
        return True

    def insert_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        """아웃라인/스크립트에 슬라이드를 삽입한다."""
        inserted = False
        for dir_name, jsonl_name in ((SCRIPT_DIR, "script.jsonl"), (OUTLINE_DIR, "outline.jsonl")):
            inserted |= self._insert_slide_in_dir(project_dir, dir_name, index, slide_json)
            inserted |= self._insert_slide_in_jsonl(project_dir, jsonl_name, index, slide_json)
        if not inserted:
            # outline/script이 전혀 없는 프로젝트(imported 등)에서도 outline 파일을 생성
            outline_dir = project_dir / OUTLINE_DIR
            outline_dir.mkdir(exist_ok=True)
            data = json.loads(slide_json)
            data["slide_index"] = index
            (outline_dir / self._slide_filename(index)).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            logger.info("outline/script 파일이 없어 outline 디렉토리에 새 파일 생성: index=%d", index)

    def _insert_slide_in_dir(self, project_dir: Path, dir_name: str, index: int, slide_json: str) -> bool:
        directory = project_dir / dir_name
        files = self._sorted_slide_files(directory)
        if not files:
            return False
        count = len(files)
        if index < 0 or index > count:
            index = count
        # 뒤에서부터 한 칸씩 밀기
        for i in range(count - 1, index - 1, -1):
            old_name = directory / self._slide_filename(i)
            new_name = directory / self._slide_filename(i + 1)
            old_name.rename(new_name)
        # 새 파일 작성
        data = json.loads(slide_json)
        data["slide_index"] = index
        (directory / self._slide_filename(index)).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        # slide_index 재번호
        self._renumber_dir(directory)
        logger.info("슬라이드 삽입 동기화: index=%d, dir=%s", index, directory)
        return True

    def _insert_slide_in_jsonl(self, project_dir: Path, jsonl_name: str, index: int, slide_json: str) -> bool:
        path = project_dir / jsonl_name
        if not path.exists():
            return False
        lines = self._load_jsonl_lines(path)
        new_line = json.dumps(json.loads(slide_json), ensure_ascii=False)
        lines.insert(index, new_line)
        self._save_jsonl_lines(path, lines)
        logger.info("슬라이드 삽입 동기화 (JSONL): index=%d, path=%s", index, path)
        return True

    def delete_outline_slide(self, project_dir: Path, index: int) -> None:
        """아웃라인/스크립트에서 슬라이드를 삭제한다."""
        deleted = False
        for dir_name, jsonl_name in ((SCRIPT_DIR, "script.jsonl"), (OUTLINE_DIR, "outline.jsonl")):
            deleted |= self._delete_slide_in_dir(project_dir, dir_name, index)
            deleted |= self._delete_slide_in_jsonl(project_dir, jsonl_name, index)
        if not deleted:
            logger.warning("outline/script 파일이 없어 동기화를 건너뜁니다: %s", project_dir)

    def _delete_slide_in_dir(self, project_dir: Path, dir_name: str, index: int) -> bool:
        directory = project_dir / dir_name
        files = self._sorted_slide_files(directory)
        if not files:
            return False
        if index < 0 or index >= len(files):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(files)}장)")
        files[index].unlink()
        self._renumber_dir(directory)
        logger.info("슬라이드 삭제 동기화: index=%d, dir=%s", index, directory)
        return True

    def _delete_slide_in_jsonl(self, project_dir: Path, jsonl_name: str, index: int) -> bool:
        path = project_dir / jsonl_name
        if not path.exists():
            return False
        lines = self._load_jsonl_lines(path)
        if index < 0 or index >= len(lines):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
        lines.pop(index)
        self._save_jsonl_lines(path, lines)
        logger.info("슬라이드 삭제 동기화 (JSONL): index=%d, path=%s", index, path)
        return True

    # --- 슬라이드 이동 ---

    def move_outline_slide(self, project_dir: Path, from_index: int, to_index: int) -> None:
        """아웃라인/스크립트에서 슬라이드를 from_index → to_index로 이동한다."""
        moved = False
        for dir_name, jsonl_name in ((SCRIPT_DIR, "script.jsonl"), (OUTLINE_DIR, "outline.jsonl")):
            moved |= self._move_slide_in_dir(project_dir, dir_name, from_index, to_index)
            moved |= self._move_slide_in_jsonl(project_dir, jsonl_name, from_index, to_index)
        if not moved:
            logger.warning("outline/script 파일이 없어 이동을 건너뜁니다: %s", project_dir)

    def _move_slide_in_dir(self, project_dir: Path, dir_name: str, from_idx: int, to_idx: int) -> bool:
        directory = project_dir / dir_name
        files = self._sorted_slide_files(directory)
        if not files:
            return False
        count = len(files)
        if from_idx < 0 or from_idx >= count:
            raise IndexError(f"유효하지 않은 from_index: {from_idx} (전체 {count}장)")
        if to_idx < 0 or to_idx >= count:
            raise IndexError(f"유효하지 않은 to_index: {to_idx} (전체 {count}장)")
        if from_idx == to_idx:
            return True
        # 내용 읽기
        contents = [f.read_text(encoding="utf-8") for f in files]
        item = contents.pop(from_idx)
        contents.insert(to_idx, item)
        # 전체 재작성 + slide_index 갱신
        for i, content in enumerate(contents):
            data = json.loads(content)
            data["slide_index"] = i
            (directory / self._slide_filename(i)).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
            )
        logger.info("슬라이드 이동 동기화: %d → %d, dir=%s", from_idx, to_idx, directory)
        return True

    def _move_slide_in_jsonl(self, project_dir: Path, jsonl_name: str, from_idx: int, to_idx: int) -> bool:
        path = project_dir / jsonl_name
        if not path.exists():
            return False
        lines = self._load_jsonl_lines(path)
        count = len(lines)
        if from_idx < 0 or from_idx >= count:
            raise IndexError(f"유효하지 않은 from_index: {from_idx} (전체 {count}장)")
        if to_idx < 0 or to_idx >= count:
            raise IndexError(f"유효하지 않은 to_index: {to_idx} (전체 {count}장)")
        if from_idx == to_idx:
            return True
        item = lines.pop(from_idx)
        lines.insert(to_idx, item)
        self._save_jsonl_lines(path, lines)
        logger.info("슬라이드 이동 동기화 (JSONL): %d → %d, path=%s", from_idx, to_idx, path)
        return True

    # --- 내부 유틸 ---

    def _renumber_dir(self, directory: Path) -> None:
        """디렉토리 내 모든 slide 파일의 slide_index를 파일 순서에 맞게 재번호한다."""
        files = self._sorted_slide_files(directory)
        # 1) 임시 이름으로 rename (파일명 충돌 방지)
        tmp_pairs: list[tuple[Path, int]] = []
        for i, f in enumerate(files):
            tmp = directory / f"_tmp_{i}.json"
            f.rename(tmp)
            tmp_pairs.append((tmp, i))
        # 2) 최종 이름으로 rename + slide_index 갱신
        for tmp, i in tmp_pairs:
            data = json.loads(tmp.read_text(encoding="utf-8"))
            data["slide_index"] = i
            target = directory / self._slide_filename(i)
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            if tmp.exists():
                tmp.unlink()

    @staticmethod
    def _load_jsonl_lines(path: Path) -> list[str]:
        """JSONL 파일의 비어있지 않은 줄들을 리스트로 반환한다."""
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _save_jsonl_lines(path: Path, lines: list[str]) -> None:
        """줄 리스트를 JSONL 파일로 저장한다. slide_index를 줄 순서에 맞게 재번호한다."""
        renumbered = []
        for i, line in enumerate(lines):
            data = json.loads(line)
            data["slide_index"] = i
            renumbered.append(json.dumps(data, ensure_ascii=False))
        path.write_text("\n".join(renumbered) + "\n", encoding="utf-8")
