from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

from ppt_generator.interfaces.constants import PPT_GENERATOR_HOME
from dataclasses import replace

from ppt_generator.interfaces.schemas import DesignSpec, PptxImage, PptxSlideSpec, ProjectMetadata
from ppt_generator.tools.project.design_spec_store import DesignSpecStore
from ppt_generator.tools.project.html_store import HtmlStore
from ppt_generator.tools.project.jsonl_store import JsonlStore

logger = logging.getLogger(__name__)

# server.py의 main()에서 설정됨
_log_dir: str | None = None
_log_fmt: str = "%(asctime)s %(name)s %(levelname)s %(message)s"
_active_handlers: dict[str, RotatingFileHandler] = {}


class ProjectService:
    """파이프라인 결과물의 파일 I/O를 전담하는 서비스."""

    SLIDES_DIR = "slides"
    IMAGES_DIR = "slides/images"

    def __init__(self, design_spec_store: DesignSpecStore | None = None) -> None:
        self.design_spec_store = design_spec_store or DesignSpecStore()
        self._jsonl_store = JsonlStore()
        self._html_store = HtmlStore()
        self._metadata_lock = Lock()

    def resolve_project_dir(self, project_id: str = "") -> tuple[str, Path]:
        """project_id → (project_id, project_dir). 빈 값이면 UUID 자동 생성."""
        if not project_id:
            project_id = str(uuid.uuid4())
        project_dir = PPT_GENERATOR_HOME / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        _maybe_add_project_log_handler(project_id)
        return project_id, project_dir

    # --- 아웃라인/스크립트 (JsonlStore 위임) ---

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        self._ensure_dir(project_dir)
        self._jsonl_store.save_outline(project_dir, outline_json)

    def save_script(self, project_dir: Path, script_json: str) -> None:
        self._ensure_dir(project_dir)
        self._jsonl_store.save_script(project_dir, script_json)

    def load_outline(self, project_dir: Path) -> str:
        return self._jsonl_store.load_outline(project_dir)

    def load_outline_slide(self, project_dir: Path, index: int) -> str:
        return self._jsonl_store.load_outline_slide(project_dir, index)

    def load_script(self, project_dir: Path) -> str:
        return self._jsonl_store.load_script(project_dir)

    def load_script_slide(self, project_dir: Path, index: int) -> str:
        return self._jsonl_store.load_script_slide(project_dir, index)

    def load_script_or_outline(self, project_dir: Path) -> str:
        return self._jsonl_store.load_script_or_outline(project_dir)

    def load_script_or_outline_slide(self, project_dir: Path, index: int) -> str:
        return self._jsonl_store.load_script_or_outline_slide(project_dir, index)

    def update_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        self._jsonl_store.update_outline_slide(project_dir, index, slide_json)

    def insert_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        self._jsonl_store.insert_outline_slide(project_dir, index, slide_json)

    def delete_outline_slide(self, project_dir: Path, index: int) -> None:
        self._jsonl_store.delete_outline_slide(project_dir, index)

    # --- HTML/이미지 (HtmlStore 위임) ---

    def save_slides_html(
        self,
        project_dir: Path,
        session_id: str,
        slide_htmls: list[str],
        container_html: str,
    ) -> None:
        self._ensure_dir(project_dir)
        self._html_store.save_slides_html(project_dir, session_id, slide_htmls, container_html)

    def save_slide_images(
        self,
        project_dir: Path,
        slide_index: int,
        images: list[PptxImage],
    ) -> list[str]:
        return self._html_store.save_slide_images(project_dir, slide_index, images)

    def get_slide_image_srcs(
        self,
        project_dir: Path,
        slide_index: int,
        image_count: int,
    ) -> list[str]:
        return self._html_store.get_slide_image_srcs(project_dir, slide_index, image_count)

    def save_single_slide_html(
        self, project_dir: Path, slide_index: int, slide_html: str,
    ) -> Path:
        self._ensure_dir(project_dir)
        return self._html_store.save_single_slide_html(project_dir, slide_index, slide_html)

    def delete_slide_html(self, project_dir: Path, index: int) -> None:
        self._html_store.delete_slide_html(project_dir, index)

    def shift_slide_htmls(self, project_dir: Path, insert_index: int) -> None:
        self._html_store.shift_slide_htmls(project_dir, insert_index)

    # --- 디자인 스펙 (DesignSpecStore 위임) ---

    def save_design_spec(self, project_dir: Path, design_spec: DesignSpec) -> None:
        self._ensure_dir(project_dir)
        self.design_spec_store.save_design_spec(project_dir, design_spec)

    def load_design_spec(self, project_dir: Path) -> DesignSpec:
        return self.design_spec_store.load_design_spec(project_dir)

    def load_design_spec_with_images(self, project_dir: Path) -> DesignSpec:
        """design spec을 로드한 후, 각 이미지의 src로부터 image_bytes를 복원한다."""
        spec = self.load_design_spec(project_dir)
        slides_dir = project_dir / self.SLIDES_DIR
        updated_slides: list[PptxSlideSpec] = []
        for slide in spec.slides:
            new_images: list[PptxImage] = []
            for img in slide.images:
                if img.src:
                    img_path = slides_dir / img.src
                    if img_path.exists():
                        new_images.append(replace(img, image_bytes=img_path.read_bytes()))
                    else:
                        logger.warning("이미지 파일 없음: %s", img_path)
                        new_images.append(img)
                else:
                    new_images.append(img)
            if new_images != list(slide.images):
                updated_slides.append(replace(slide, images=new_images))
            else:
                updated_slides.append(slide)
        return DesignSpec(slides=updated_slides)

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

    # --- 메타데이터/프로젝트 관리 ---

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
            "audience_type": metadata.audience_type,
            "presentation_minutes": metadata.presentation_minutes,
            "source": metadata.source,
        }
        (project_dir / "project.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("project.json 저장 완료: %s", project_dir)

    def update_step(self, project_dir: Path, step_name: str) -> None:
        with self._metadata_lock:
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
            audience_type=data.get("audience_type", "general"),
            presentation_minutes=data.get("presentation_minutes", 15),
            source=data.get("source", "generated"),
        )

    # --- 프로젝트 목록 ---

    def list_projects(self) -> list[dict]:
        """PPT_GENERATOR_HOME 아래 모든 프로젝트 디렉토리를 조회한다."""
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
                "audience_type": data.get("audience_type", "general"),
                "presentation_minutes": data.get("presentation_minutes", 15),
                "source": data.get("source", "generated"),
                "created_at": created_at,
            })

        projects.sort(key=lambda p: p["created_at"], reverse=True)
        return projects

    # --- 유틸 ---

    @staticmethod
    def _ensure_dir(project_dir: Path) -> None:
        project_dir.mkdir(parents=True, exist_ok=True)


def _maybe_add_project_log_handler(project_id: str) -> None:
    """PPT_LOG_DIR 설정 시 프로젝트별 로그 파일 핸들러를 root logger에 추가."""
    if not _log_dir or project_id in _active_handlers:
        return
    d = Path(_log_dir)
    d.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        str(d / f"{project_id}.log"),
        maxBytes=10 * 1024 * 1024, backupCount=2, encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_log_fmt))
    logging.getLogger().addHandler(fh)
    _active_handlers[project_id] = fh
