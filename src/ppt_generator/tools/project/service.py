from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ppt_generator.interfaces.constants import PPT_GENERATOR_HOME
from ppt_generator.interfaces.schemas import ProjectMetadata

if TYPE_CHECKING:
    from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


class ProjectService:
    """파이프라인 결과물의 파일 I/O를 전담하는 서비스."""

    def __init__(self, slides_service: SlidesService) -> None:
        self._slides_service = slides_service

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

    def save_images(self, project_dir: Path, images_json: str) -> None:
        self._ensure_dir(project_dir)
        images_dir = project_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        data = json.loads(images_json)
        remapped_images: list[dict] = []

        for img in data.get("images", []):
            slide_index = img["slide_index"]
            src_path = Path(img["image_path"])
            dest_filename = f"slide_{slide_index}{src_path.suffix}"
            dest_path = images_dir / dest_filename

            if src_path.exists():
                shutil.copy2(str(src_path), str(dest_path))
                logger.info("이미지 복사: %s → %s", src_path, dest_path)
            else:
                logger.warning("이미지 원본 파일 없음, 건너뜀: %s", src_path)
                continue

            remapped_images.append({
                "slide_index": slide_index,
                "image_path": str(dest_path),
            })

        remapped_json = json.dumps({"images": remapped_images}, ensure_ascii=False, indent=2)
        (project_dir / "images.json").write_text(remapped_json, encoding="utf-8")
        logger.info("images.json 저장 완료 (%d개): %s", len(remapped_images), project_dir)

    def save_images_meta(self, project_dir: Path, images_json: str) -> None:
        """이미지 메타데이터(images.json)만 저장. 파일 복사는 하지 않음."""
        self._ensure_dir(project_dir)
        (project_dir / "images.json").write_text(images_json, encoding="utf-8")

    def save_slides_html(
        self,
        project_dir: Path,
        session_id: str,
        html: str,
        image_paths: dict[int, str] | None = None,
    ) -> None:
        self._ensure_dir(project_dir)
        (project_dir / "slides.html").write_text(html, encoding="utf-8")
        meta: dict = {"session_id": session_id}
        if image_paths:
            meta["image_paths"] = {str(k): v for k, v in image_paths.items()}
        (project_dir / "slides_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("slides.html 저장 완료: %s", project_dir)

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

    def load_images(self, project_dir: Path) -> str:
        path = project_dir / "images.json"
        return path.read_text(encoding="utf-8")

    def load_slides_html(self, project_dir: Path) -> tuple[str, str]:
        html = (project_dir / "slides.html").read_text(encoding="utf-8")
        meta = json.loads((project_dir / "slides_meta.json").read_text(encoding="utf-8"))
        session_id = meta["session_id"]
        image_paths: dict[int, str] = {
            int(k): v for k, v in meta.get("image_paths", {}).items()
        }

        # SlidesService 인메모리 세션 복원
        self._slides_service._sessions[session_id] = (html, image_paths)
        logger.info("슬라이드 세션 복원 완료: session_id=%s", session_id)

        return session_id, html

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
