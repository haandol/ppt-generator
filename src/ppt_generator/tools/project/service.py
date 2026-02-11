from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ppt_generator.interfaces.schemas import ProjectMetadata

if TYPE_CHECKING:
    from ppt_generator.tools.slides.service import SlidesService

logger = logging.getLogger(__name__)


class ProjectService:
    """파이프라인 결과물의 파일 I/O를 전담하는 서비스."""

    def __init__(self, slides_service: SlidesService) -> None:
        self._slides_service = slides_service

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

    def save_slides_html(self, project_dir: Path, session_id: str, html: str) -> None:
        self._ensure_dir(project_dir)
        (project_dir / "slides.html").write_text(html, encoding="utf-8")
        meta = {"session_id": session_id}
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

        # SlidesService 인메모리 세션 복원
        self._slides_service._sessions[session_id] = html
        logger.info("슬라이드 세션 복원 완료: session_id=%s", session_id)

        return session_id, html

    # --- 유틸 ---

    @staticmethod
    def _ensure_dir(project_dir: Path) -> None:
        project_dir.mkdir(parents=True, exist_ok=True)
