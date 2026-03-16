"""디자인 스펙 파일 CRUD를 전담하는 저장소."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ppt_generator.interfaces.schemas import DesignSpec, PptxSlideSpec
from ppt_generator.interfaces.spec_utils import parse_slide_spec_json, slide_spec_to_json

logger = logging.getLogger(__name__)

DESIGN_SPEC_DIR = "design_spec"


class DesignSpecStore:
    """디자인 스펙 파일 I/O를 전담하는 저장소."""

    @staticmethod
    def _slide_filename(index: int) -> str:
        """0-based 인덱스를 slide_01.json 형식 파일명으로 변환."""
        return f"slide_{index + 1:02d}.json"

    @staticmethod
    def _design_spec_dir(project_dir: Path) -> Path:
        return project_dir / DESIGN_SPEC_DIR

    # --- 전체 디자인 스펙 저장/로드 ---

    def save_design_spec(self, project_dir: Path, design_spec: DesignSpec) -> None:
        spec_dir = self._design_spec_dir(project_dir)
        if spec_dir.exists():
            import shutil
            shutil.rmtree(spec_dir)
        spec_dir.mkdir(parents=True)
        for i, slide in enumerate(design_spec.slides):
            fname = self._slide_filename(i)
            (spec_dir / fname).write_text(slide_spec_to_json(slide), encoding="utf-8")
        logger.info("design_spec/ 저장 완료 (%d 슬라이드): %s", len(design_spec.slides), spec_dir)

    def load_design_spec(self, project_dir: Path) -> DesignSpec:
        spec_dir = self._design_spec_dir(project_dir)
        if not spec_dir.exists():
            raise FileNotFoundError(f"디자인 스펙 디렉토리가 존재하지 않습니다: {spec_dir}")
        files = sorted(spec_dir.glob("slide_*.json"))
        if not files:
            raise FileNotFoundError(f"디자인 스펙 슬라이드 파일이 없습니다: {spec_dir}")
        slides: list[PptxSlideSpec] = []
        for f in files:
            slides.append(parse_slide_spec_json(f.read_text(encoding="utf-8")))
        return DesignSpec(slides=slides)

    # --- 개별 슬라이드 CRUD ---

    def save_design_spec_slide(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None:
        """개별 슬라이드를 해당 인덱스 파일에 덮어쓴다."""
        spec_dir = self._design_spec_dir(project_dir)
        fname = self._slide_filename(index)
        path = spec_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"슬라이드 파일이 존재하지 않습니다: {path}")
        path.write_text(slide_spec_to_json(slide), encoding="utf-8")

    def load_design_spec_slide(self, project_dir: Path, index: int) -> PptxSlideSpec:
        """개별 슬라이드를 인덱스로 로드한다."""
        spec_dir = self._design_spec_dir(project_dir)
        fname = self._slide_filename(index)
        path = spec_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"슬라이드 파일이 존재하지 않습니다: {path}")
        return parse_slide_spec_json(path.read_text(encoding="utf-8"))

    def delete_design_spec_slide(self, project_dir: Path, index: int) -> None:
        """슬라이드를 삭제하고 남은 파일을 재번호한다."""
        spec_dir = self._design_spec_dir(project_dir)
        files = sorted(spec_dir.glob("slide_*.json"))
        if index < 0 or index >= len(files):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(files)}장)")
        files[index].unlink()
        # 재번호
        remaining = sorted(spec_dir.glob("slide_*.json"))
        for i, f in enumerate(remaining):
            new_name = self._slide_filename(i)
            f.rename(spec_dir / new_name)

    def insert_design_spec_slide(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None:
        """슬라이드를 삽입하고 파일을 재번호한다."""
        spec_dir = self._design_spec_dir(project_dir)
        if not spec_dir.exists():
            raise FileNotFoundError(f"디자인 스펙 디렉토리가 존재하지 않습니다: {spec_dir}")
        files = sorted(spec_dir.glob("slide_*.json"))
        count = len(files)
        # index 클램핑
        if index < 0 or index > count:
            index = count
        # 뒤에서부터 한 칸씩 밀기
        for i in range(count - 1, index - 1, -1):
            old_name = spec_dir / self._slide_filename(i)
            new_name = spec_dir / self._slide_filename(i + 1)
            old_name.rename(new_name)
        # 새 파일 작성
        (spec_dir / self._slide_filename(index)).write_text(
            slide_spec_to_json(slide), encoding="utf-8"
        )

    def move_design_spec_slide(self, project_dir: Path, from_index: int, to_index: int) -> None:
        """슬라이드를 from_index → to_index로 이동하고 파일을 재번호한다."""
        spec_dir = self._design_spec_dir(project_dir)
        files = sorted(spec_dir.glob("slide_*.json"))
        count = len(files)
        if from_index < 0 or from_index >= count:
            raise IndexError(f"유효하지 않은 from_index: {from_index} (전체 {count}장)")
        if to_index < 0 or to_index >= count:
            raise IndexError(f"유효하지 않은 to_index: {to_index} (전체 {count}장)")
        if from_index == to_index:
            return
        # 내용 읽기
        contents = [f.read_text(encoding="utf-8") for f in files]
        item = contents.pop(from_index)
        contents.insert(to_index, item)
        # 전체 재작성
        for i, content in enumerate(contents):
            (spec_dir / self._slide_filename(i)).write_text(content, encoding="utf-8")

    def create_design_spec_slide(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None:
        """개별 슬라이드를 해당 인덱스 파일에 저장한다 (파일 유무 무관)."""
        spec_dir = self._design_spec_dir(project_dir)
        spec_dir.mkdir(parents=True, exist_ok=True)
        fname = self._slide_filename(index)
        (spec_dir / fname).write_text(slide_spec_to_json(slide), encoding="utf-8")

    # --- 디자인 요약 ---

    def save_design_summary(self, project_dir: Path, summary: dict) -> None:
        """디자인 요약을 design_spec/design_summary.json에 저장한다."""
        spec_dir = self._design_spec_dir(project_dir)
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "design_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_design_summary(self, project_dir: Path) -> dict | None:
        """디자인 요약을 로드한다. 파일이 없으면 None을 반환한다."""
        path = self._design_spec_dir(project_dir) / "design_summary.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_design_spec_slide_count(self, project_dir: Path) -> int:
        """디자인 스펙의 슬라이드 수를 반환한다."""
        spec_dir = self._design_spec_dir(project_dir)
        if not spec_dir.exists():
            return 0
        return len(list(spec_dir.glob("slide_*.json")))
