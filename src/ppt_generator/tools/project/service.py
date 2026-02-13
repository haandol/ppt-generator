from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ppt_generator.interfaces.constants import PPT_GENERATOR_HOME
from ppt_generator.interfaces.schemas import DesignSpec, PptxSlideSpec, ProjectMetadata
from ppt_generator.interfaces.spec_utils import parse_slide_spec_json, slide_spec_to_json

logger = logging.getLogger(__name__)


class ProjectService:
    """파이프라인 결과물의 파일 I/O를 전담하는 서비스."""

    def __init__(self) -> None:
        pass

    def resolve_project_dir(self, project_id: str = "") -> tuple[str, Path]:
        """project_id → (project_id, project_dir). 빈 값이면 UUID 자동 생성."""
        if not project_id:
            project_id = str(uuid.uuid4())
        project_dir = PPT_GENERATOR_HOME / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_id, project_dir

    # --- 저장 메서드 ---

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        self._ensure_dir(project_dir)
        (project_dir / "outline.json").write_text(outline_json, encoding="utf-8")
        logger.info("outline.json 저장 완료: %s", project_dir)

    def save_script(self, project_dir: Path, script_json: str) -> None:
        self._ensure_dir(project_dir)
        (project_dir / "script.json").write_text(script_json, encoding="utf-8")
        logger.info("script.json 저장 완료: %s", project_dir)

    def save_slides_html(
        self,
        project_dir: Path,
        session_id: str,
        html: str,
    ) -> None:
        self._ensure_dir(project_dir)
        (project_dir / "slides.html").write_text(html, encoding="utf-8")
        meta: dict = {"session_id": session_id}
        (project_dir / "slides_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("slides.html 저장 완료: %s", project_dir)

    # --- 디자인 스펙 상수/헬퍼 ---

    DESIGN_SPEC_DIR = "design_spec"

    @staticmethod
    def _slide_filename(index: int) -> str:
        """0-based 인덱스를 slide_01.json 형식 파일명으로 변환."""
        return f"slide_{index + 1:02d}.json"

    def _design_spec_dir(self, project_dir: Path) -> Path:
        return project_dir / self.DESIGN_SPEC_DIR

    # --- 디자인 스펙 저장/로드 (전체) ---

    def save_design_spec(self, project_dir: Path, design_spec: DesignSpec) -> None:
        self._ensure_dir(project_dir)
        spec_dir = self._design_spec_dir(project_dir)
        if spec_dir.exists():
            shutil.rmtree(spec_dir)
        spec_dir.mkdir(parents=True)
        for i, slide in enumerate(design_spec.slides):
            fname = self._slide_filename(i)
            (spec_dir / fname).write_text(slide_spec_to_json(slide), encoding="utf-8")
        logger.info("design_spec/ 저장 완료 (%d 슬라이드): %s", len(design_spec.slides), spec_dir)

    def save_pptx(self, project_dir: Path, pptx_path: str) -> None:
        self._ensure_dir(project_dir)
        src = Path(pptx_path)
        dest = project_dir / "presentation.pptx"
        shutil.copy2(str(src), str(dest))
        logger.info("presentation.pptx 저장 완료: %s", dest)

    def save_metadata(self, project_dir: Path, metadata: ProjectMetadata) -> None:
        self._ensure_dir(project_dir)
        data = {
            "topic": metadata.topic,
            "num_slides": metadata.num_slides,
            "steps_completed": metadata.steps_completed,
        }
        (project_dir / "project.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("project.json 저장 완료: %s", project_dir)

    def update_step(self, project_dir: Path, step_name: str) -> None:
        metadata = self.load_metadata(project_dir)
        metadata.steps_completed[step_name] = datetime.now(timezone.utc).isoformat()
        self.save_metadata(project_dir, metadata)

    # --- 로드 메서드 ---

    def load_metadata(self, project_dir: Path) -> ProjectMetadata:
        path = project_dir / "project.json"
        if not path.exists():
            if not project_dir.exists():
                raise FileNotFoundError(f"프로젝트 디렉토리가 존재하지 않습니다: {project_dir}")
            return ProjectMetadata(topic="", num_slides=0, steps_completed={})
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectMetadata(
            topic=data.get("topic", ""),
            num_slides=data.get("num_slides", 0),
            steps_completed=data.get("steps_completed", {}),
        )

    def load_outline(self, project_dir: Path) -> str:
        path = project_dir / "outline.json"
        return path.read_text(encoding="utf-8")

    def load_script(self, project_dir: Path) -> str:
        path = project_dir / "script.json"
        return path.read_text(encoding="utf-8")

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

    # --- 디자인 스펙 개별 슬라이드 CRUD ---

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

    def get_design_spec_slide_count(self, project_dir: Path) -> int:
        """디자인 스펙의 슬라이드 수를 반환한다."""
        spec_dir = self._design_spec_dir(project_dir)
        if not spec_dir.exists():
            return 0
        return len(list(spec_dir.glob("slide_*.json")))

    # --- 프로젝트 목록 ---

    def list_projects(self) -> list[dict]:
        """PPT_GENERATOR_HOME 아래 모든 프로젝트 디렉토리를 조회한다.

        Returns:
            project.json이 존재하는 프로젝트 목록. 각 항목은
            project_id, topic, num_slides, steps_completed, created_at 키를 포함한다.
            created_at 기준 내림차순(최신 순) 정렬.
        """
        home = PPT_GENERATOR_HOME
        if not home.exists():
            home.mkdir(parents=True, exist_ok=True)
            return []

        projects: list[dict] = []
        for child in home.iterdir():
            if not child.is_dir():
                continue
            meta_path = child / "project.json"
            if not meta_path.exists():
                continue
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                # 디렉토리의 생성 시간을 created_at으로 사용 (Linux fallback: mtime)
                stat = child.stat()
                created_ts = getattr(stat, "st_birthtime", stat.st_mtime)
                created_at = datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
            except Exception:
                logger.warning("프로젝트 메타데이터 로드 실패, 건너뜀: %s", child)
                continue

            projects.append({
                "project_id": child.name,
                "topic": data.get("topic", ""),
                "num_slides": data.get("num_slides", 0),
                "steps_completed": data.get("steps_completed", {}),
                "created_at": created_at,
            })

        # 최신 순 정렬
        projects.sort(key=lambda p: p["created_at"], reverse=True)
        return projects

    # --- 유틸 ---

    @staticmethod
    def _ensure_dir(project_dir: Path) -> None:
        project_dir.mkdir(parents=True, exist_ok=True)
