"""아웃라인/스크립트 JSONL 파일 CRUD를 전담하는 스토어 모듈."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class JsonlStore:
    """아웃라인/스크립트 JSONL 파일의 저장/로드/CRUD를 담당한다."""

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        data = json.loads(outline_json)
        slides = data["slides"]
        lines = []
        for i, s in enumerate(slides):
            s["slide_index"] = i
            lines.append(json.dumps(s, ensure_ascii=False))
        (project_dir / "outline.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("outline.jsonl 저장 완료: %s", project_dir)

    def save_script(self, project_dir: Path, script_json: str) -> None:
        data = json.loads(script_json)
        slides = data["slides"]
        lines = []
        for i, s in enumerate(slides):
            s["slide_index"] = i
            lines.append(json.dumps(s, ensure_ascii=False))
        (project_dir / "script.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("script.jsonl 저장 완료: %s", project_dir)

    def load_outline(self, project_dir: Path) -> str:
        path = project_dir / "outline.jsonl"
        if path.exists():
            slides = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            return json.dumps({"slides": slides}, ensure_ascii=False)
        legacy = project_dir / "outline.json"
        return legacy.read_text(encoding="utf-8")

    def load_outline_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드 아웃라인을 인덱스로 로드한다."""
        path = project_dir / "outline.jsonl"
        if path.exists():
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if index < 0 or index >= len(lines):
                raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
            return lines[index]
        legacy = project_dir / "outline.json"
        data = json.loads(legacy.read_text(encoding="utf-8"))
        slides = data["slides"]
        if index < 0 or index >= len(slides):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(slides)}장)")
        return json.dumps(slides[index], ensure_ascii=False)

    def load_script(self, project_dir: Path) -> str:
        path = project_dir / "script.jsonl"
        if not path.exists():
            legacy = project_dir / "script.json"
            return legacy.read_text(encoding="utf-8")
        slides = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return json.dumps({"slides": slides}, ensure_ascii=False)

    def load_script_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드 스크립트를 인덱스로 로드한다."""
        path = project_dir / "script.jsonl"
        if path.exists():
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if index < 0 or index >= len(lines):
                raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
            return lines[index]
        legacy = project_dir / "script.json"
        data = json.loads(legacy.read_text(encoding="utf-8"))
        slides = data["slides"]
        if index < 0 or index >= len(slides):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(slides)}장)")
        return json.dumps(slides[index], ensure_ascii=False)

    def load_script_or_outline(self, project_dir: Path) -> str:
        """script.jsonl이 있으면 우선 로드, 없으면 outline.jsonl로 fallback."""
        script_path = project_dir / "script.jsonl"
        if script_path.exists():
            return self.load_script(project_dir)
        legacy = project_dir / "script.json"
        if legacy.exists():
            return legacy.read_text(encoding="utf-8")
        return self.load_outline(project_dir)

    def load_script_or_outline_slide(self, project_dir: Path, index: int) -> str:
        """개별 슬라이드를 script.jsonl 우선, 없으면 outline.jsonl에서 로드한다."""
        script_path = project_dir / "script.jsonl"
        if script_path.exists():
            return self.load_script_slide(project_dir, index)
        return self.load_outline_slide(project_dir, index)

    # --- JSONL CRUD ---

    def _load_jsonl_lines(self, path: Path) -> list[str]:
        """JSONL 파일의 비어있지 않은 줄들을 리스트로 반환한다."""
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _save_jsonl_lines(self, path: Path, lines: list[str]) -> None:
        """줄 리스트를 JSONL 파일로 저장한다. slide_index를 줄 순서에 맞게 재번호한다."""
        renumbered = []
        for i, line in enumerate(lines):
            data = json.loads(line)
            data["slide_index"] = i
            renumbered.append(json.dumps(data, ensure_ascii=False))
        path.write_text("\n".join(renumbered) + "\n", encoding="utf-8")

    def update_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        """아웃라인/스크립트 JSONL에서 특정 슬라이드를 교체한다."""
        updated = False
        for fname in ("script.jsonl", "outline.jsonl"):
            path = project_dir / fname
            if not path.exists():
                continue
            lines = self._load_jsonl_lines(path)
            if index < 0 or index >= len(lines):
                raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
            existing = json.loads(lines[index])
            new_data = json.loads(slide_json)
            existing.update({k: v for k, v in new_data.items() if k != "slide_index"})
            lines[index] = json.dumps(existing, ensure_ascii=False)
            self._save_jsonl_lines(path, lines)
            logger.info("슬라이드 업데이트 동기화: index=%d, path=%s", index, path)
            updated = True
        if not updated:
            logger.warning("outline/script JSONL이 없어 동기화를 건너뜁니다: %s", project_dir)

    def insert_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        """아웃라인/스크립트 JSONL에 슬라이드를 삽입한다."""
        inserted = False
        for fname in ("script.jsonl", "outline.jsonl"):
            path = project_dir / fname
            if not path.exists():
                continue
            lines = self._load_jsonl_lines(path)
            new_line = json.dumps(json.loads(slide_json), ensure_ascii=False)
            lines.insert(index, new_line)
            self._save_jsonl_lines(path, lines)
            logger.info("슬라이드 삽입 동기화: index=%d, path=%s", index, path)
            inserted = True
        if not inserted:
            logger.warning("outline/script JSONL이 없어 동기화를 건너뜁니다: %s", project_dir)

    def delete_outline_slide(self, project_dir: Path, index: int) -> None:
        """아웃라인/스크립트 JSONL에서 슬라이드를 삭제한다."""
        deleted = False
        for fname in ("script.jsonl", "outline.jsonl"):
            path = project_dir / fname
            if not path.exists():
                continue
            lines = self._load_jsonl_lines(path)
            if index < 0 or index >= len(lines):
                raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
            lines.pop(index)
            self._save_jsonl_lines(path, lines)
            logger.info("슬라이드 삭제 동기화: index=%d, path=%s", index, path)
            deleted = True
        if not deleted:
            logger.warning("outline/script JSONL이 없어 동기화를 건너뜁니다: %s", project_dir)
