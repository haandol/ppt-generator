from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ppt_generator.interfaces.constants import PPT_GENERATOR_HOME
from ppt_generator.interfaces.schemas import DesignSpec, PptxSlideSpec, ProjectMetadata
from ppt_generator.tools.project.design_spec_store import DesignSpecStore

logger = logging.getLogger(__name__)


class ProjectService:
    """파이프라인 결과물의 파일 I/O를 전담하는 서비스."""

    def __init__(self, design_spec_store: DesignSpecStore | None = None) -> None:
        self.design_spec_store = design_spec_store or DesignSpecStore()

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

    SLIDES_DIR = "slides"

    @staticmethod
    def _slide_html_filename(index: int) -> str:
        """0-based 인덱스를 slide_01.html 형식 파일명으로 변환."""
        return f"slide_{index + 1:02d}.html"

    def save_slides_html(
        self,
        project_dir: Path,
        session_id: str,
        slide_htmls: list[str],
        container_html: str,
    ) -> None:
        self._ensure_dir(project_dir)
        slides_dir = project_dir / self.SLIDES_DIR
        if slides_dir.exists():
            shutil.rmtree(slides_dir)
        slides_dir.mkdir(parents=True)
        for i, html in enumerate(slide_htmls):
            fname = self._slide_html_filename(i)
            (slides_dir / fname).write_text(html, encoding="utf-8")
        (project_dir / "slides.html").write_text(container_html, encoding="utf-8")
        meta: dict = {"session_id": session_id}
        (project_dir / "slides_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("slides/ 저장 완료 (%d 슬라이드): %s", len(slide_htmls), project_dir)

    def save_single_slide_html(
        self, project_dir: Path, slide_index: int, slide_html: str,
    ) -> Path:
        """단일 슬라이드 HTML을 저장하고 파일 경로를 반환한다."""
        self._ensure_dir(project_dir)
        slides_dir = project_dir / self.SLIDES_DIR
        slides_dir.mkdir(parents=True, exist_ok=True)
        fname = self._slide_html_filename(slide_index)
        path = slides_dir / fname
        path.write_text(slide_html, encoding="utf-8")
        logger.info("단일 슬라이드 HTML 저장: %s", path)
        return path

    # --- 디자인 스펙 위임 메서드 ---

    def save_design_spec(self, project_dir: Path, design_spec: DesignSpec) -> None:
        self._ensure_dir(project_dir)
        self.design_spec_store.save_design_spec(project_dir, design_spec)

    def load_design_spec(self, project_dir: Path) -> DesignSpec:
        return self.design_spec_store.load_design_spec(project_dir)

    def save_design_spec_slide(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None:
        self.design_spec_store.save_design_spec_slide(project_dir, index, slide)

    def load_design_spec_slide(self, project_dir: Path, index: int) -> PptxSlideSpec:
        return self.design_spec_store.load_design_spec_slide(project_dir, index)

    def delete_design_spec_slide(self, project_dir: Path, index: int) -> None:
        self.design_spec_store.delete_design_spec_slide(project_dir, index)

    def insert_design_spec_slide(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None:
        self.design_spec_store.insert_design_spec_slide(project_dir, index, slide)

    def create_design_spec_slide(self, project_dir: Path, index: int, slide: PptxSlideSpec) -> None:
        self.design_spec_store.create_design_spec_slide(project_dir, index, slide)

    def save_design_summary(self, project_dir: Path, summary: dict) -> None:
        self.design_spec_store.save_design_summary(project_dir, summary)

    def load_design_summary(self, project_dir: Path) -> dict | None:
        return self.design_spec_store.load_design_summary(project_dir)

    def get_design_spec_slide_count(self, project_dir: Path) -> int:
        return self.design_spec_store.get_design_spec_slide_count(project_dir)

    # --- 기타 저장/로드 ---

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
            "audience_level": metadata.audience_level,
            "presentation_minutes": metadata.presentation_minutes,
        }
        (project_dir / "project.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("project.json 저장 완료: %s", project_dir)

    def update_step(self, project_dir: Path, step_name: str) -> None:
        metadata = self.load_metadata(project_dir)
        metadata.steps_completed[step_name] = datetime.now(timezone.utc).isoformat()
        self.save_metadata(project_dir, metadata)

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
            audience_level=data.get("audience_level", "general"),
            presentation_minutes=data.get("presentation_minutes", 15),
        )

    def load_outline(self, project_dir: Path) -> str:
        path = project_dir / "outline.json"
        return path.read_text(encoding="utf-8")

    def load_script(self, project_dir: Path) -> str:
        path = project_dir / "script.json"
        return path.read_text(encoding="utf-8")

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
                "audience_level": data.get("audience_level", "general"),
                "presentation_minutes": data.get("presentation_minutes", 15),
                "created_at": created_at,
            })

        # 최신 순 정렬
        projects.sort(key=lambda p: p["created_at"], reverse=True)
        return projects

    # --- 유틸 ---

    @staticmethod
    def _ensure_dir(project_dir: Path) -> None:
        project_dir.mkdir(parents=True, exist_ok=True)
