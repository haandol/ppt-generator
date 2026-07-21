from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

from ppt_generator.interfaces.constants import PPT_GENERATOR_HOME
from ppt_generator.interfaces.schemas import (
    DesignSpec,
    PptxImage,
    PptxSlideSpec,
    ProjectMetadata,
)
from ppt_generator.tools.project.design_spec_store import DesignSpecStore
from ppt_generator.tools.project.html_store import HtmlStore
from ppt_generator.tools.project.image_store import ImageStore
from ppt_generator.tools.project.jsonl_store import JsonlStore

logger = logging.getLogger(__name__)

# server.py의 main()에서 설정됨
_log_dir: str | None = None
_log_fmt: str = "%(asctime)s %(name)s %(levelname)s %(message)s"
_active_handlers: dict[str, RotatingFileHandler] = {}
_PROJECT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class ProjectService:
    """파이프라인 결과물의 파일 I/O를 전담하는 서비스."""

    def __init__(self, design_spec_store: DesignSpecStore | None = None) -> None:
        self.design_spec_store = design_spec_store or DesignSpecStore()
        self._jsonl_store = JsonlStore()
        self._html_store = HtmlStore()
        self._image_store = ImageStore(html_store=self._html_store)
        self._metadata_lock = Lock()

    def resolve_project_dir(self, project_id: str = "") -> tuple[str, Path]:
        """project_id → (project_id, project_dir). 빈 값이면 UUID 자동 생성."""
        if not project_id:
            project_id = str(uuid.uuid4())
        elif _PROJECT_ID_RE.fullmatch(project_id) is None:
            raise ValueError(
                "Invalid project_id. Use 1-128 ASCII letters, numbers, '.', '_', or "
                "'-', starting with a letter or number."
            )
        project_dir = PPT_GENERATOR_HOME / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        _maybe_add_project_log_handler(project_id)
        return project_id, project_dir

    # --- 아웃라인 (JsonlStore 위임) ---

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        self._ensure_dir(project_dir)
        self._jsonl_store.save_outline(project_dir, outline_json)

    def load_outline(self, project_dir: Path) -> str:
        return self._jsonl_store.load_outline(project_dir)

    def load_outline_slide(self, project_dir: Path, index: int) -> str:
        return self._jsonl_store.load_outline_slide(project_dir, index)

    def get_outline_slide_count(self, project_dir: Path) -> int:
        return self._jsonl_store.get_outline_slide_count(project_dir)

    def sync_outline_to_design_spec_count(self, project_dir: Path) -> bool:
        """outline 수를 design_spec 수에 맞춰 placeholder로 채운다."""
        design_spec_count = self.get_design_spec_slide_count(project_dir)
        if design_spec_count == 0:
            return False
        return self._jsonl_store.sync_outline_to_design_spec_count(
            project_dir,
            design_spec_count,
        )

    def update_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        self._jsonl_store.update_outline_slide(project_dir, index, slide_json)

    def insert_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        self._jsonl_store.insert_outline_slide(project_dir, index, slide_json)

    def delete_outline_slide(self, project_dir: Path, index: int) -> None:
        self._jsonl_store.delete_outline_slide(project_dir, index)

    def move_outline_slide(
        self, project_dir: Path, from_index: int, to_index: int
    ) -> None:
        self._jsonl_store.move_outline_slide(project_dir, from_index, to_index)

    def save_outline_slide(
        self, project_dir: Path, index: int, slide_json: str
    ) -> None:
        self._ensure_dir(project_dir)
        self._jsonl_store.save_outline_slide(project_dir, index, slide_json)

    # --- HTML/이미지 (HtmlStore 위임) ---

    def save_slides_html(
        self,
        project_dir: Path,
        session_id: str,
        slide_htmls: list[str],
        container_html: str,
    ) -> None:
        self._ensure_dir(project_dir)
        self._html_store.save_slides_html(
            project_dir, session_id, slide_htmls, container_html
        )

    def save_slide_images(
        self,
        project_dir: Path,
        slide_index: int,
        images: list[PptxImage],
    ) -> list[str]:
        return self._html_store.save_slide_images(project_dir, slide_index, images)

    def save_slide_bg_image(
        self,
        project_dir: Path,
        slide_index: int,
        image_bytes: bytes,
    ) -> str:
        return self._html_store.save_slide_bg_image(
            project_dir, slide_index, image_bytes
        )

    def get_slide_image_srcs(
        self,
        project_dir: Path,
        slide_index: int,
        image_count: int,
    ) -> list[str]:
        return self._html_store.get_slide_image_srcs(
            project_dir, slide_index, image_count
        )

    def sync_image_paths(
        self, project_dir: Path, design_spec: DesignSpec
    ) -> DesignSpec:
        """image_path가 있지만 src가 없는 이미지를 slides/images/에 복사하고 src를 설정한다."""
        return self._image_store.sync_image_paths(
            project_dir,
            design_spec,
            save_slide_fn=self.save_design_spec_slide,
        )

    def save_single_slide_html(
        self,
        project_dir: Path,
        slide_index: int,
        slide_html: str,
    ) -> Path:
        self._ensure_dir(project_dir)
        return self._html_store.save_single_slide_html(
            project_dir, slide_index, slide_html
        )

    def delete_slide_html(self, project_dir: Path, index: int) -> None:
        self._html_store.delete_slide_html(project_dir, index)

    def shift_slide_htmls(self, project_dir: Path, insert_index: int) -> None:
        self._html_store.shift_slide_htmls(project_dir, insert_index)

    def move_slide_html(
        self, project_dir: Path, from_index: int, to_index: int
    ) -> None:
        self._html_store.move_slide_html(project_dir, from_index, to_index)

    def delete_slide_images(
        self, project_dir: Path, index: int, slide_count: int
    ) -> None:
        self._html_store.delete_slide_images(project_dir, index, slide_count)

    def shift_slide_images(
        self, project_dir: Path, insert_index: int, slide_count: int
    ) -> None:
        self._html_store.shift_slide_images(project_dir, insert_index, slide_count)

    def move_slide_images(
        self,
        project_dir: Path,
        from_index: int,
        to_index: int,
        slide_count: int,
    ) -> None:
        self._html_store.move_slide_images(
            project_dir, from_index, to_index, slide_count
        )

    def renumber_design_spec_image_srcs(self, project_dir: Path) -> None:
        """모든 슬라이드의 design spec images[].src를 현재 슬라이드 인덱스에 맞게 재번호한다."""
        from dataclasses import replace as _replace

        spec = self.load_design_spec(project_dir)
        changed = False
        for idx, slide in enumerate(spec.slides):
            new_images: list[PptxImage] = []
            slide_changed = False
            for img_i, img in enumerate(slide.images):
                if not img.src:
                    new_images.append(img)
                    continue
                expected_src = f"images/{self._html_store._image_filename(idx, img_i)}"
                if img.src != expected_src:
                    new_images.append(_replace(img, src=expected_src))
                    slide_changed = True
                else:
                    new_images.append(img)
            if slide_changed:
                updated_slide = _replace(slide, images=new_images)
                self.save_design_spec_slide(project_dir, idx, updated_slide)
                changed = True
        if changed:
            logger.info("design spec image src 재번호 완료: %s", project_dir)

    # --- 디자인 스펙 (DesignSpecStore 위임) ---

    def save_design_spec(self, project_dir: Path, design_spec: DesignSpec) -> None:
        self._ensure_dir(project_dir)
        self.design_spec_store.save_design_spec(project_dir, design_spec)

    def load_design_spec(self, project_dir: Path) -> DesignSpec:
        return self.design_spec_store.load_design_spec(project_dir)

    def load_design_spec_with_images(self, project_dir: Path) -> DesignSpec:
        """design spec을 로드한 후, 각 이미지의 src/image_path로부터 image_bytes를 복원한다."""
        return self._image_store.load_design_spec_with_images(
            project_dir,
            load_spec_fn=self.load_design_spec,
        )

    def save_design_spec_slide(
        self, project_dir: Path, index: int, slide: PptxSlideSpec
    ) -> None:
        self.design_spec_store.save_design_spec_slide(project_dir, index, slide)

    def load_design_spec_slide(self, project_dir: Path, index: int) -> PptxSlideSpec:
        return self.design_spec_store.load_design_spec_slide(project_dir, index)

    def delete_design_spec_slide(self, project_dir: Path, index: int) -> None:
        self.design_spec_store.delete_design_spec_slide(project_dir, index)

    def insert_design_spec_slide(
        self, project_dir: Path, index: int, slide: PptxSlideSpec
    ) -> None:
        self.design_spec_store.insert_design_spec_slide(project_dir, index, slide)

    def move_design_spec_slide(
        self, project_dir: Path, from_index: int, to_index: int
    ) -> None:
        self.design_spec_store.move_design_spec_slide(project_dir, from_index, to_index)

    def create_design_spec_slide(
        self, project_dir: Path, index: int, slide: PptxSlideSpec
    ) -> None:
        self.design_spec_store.create_design_spec_slide(project_dir, index, slide)

    def save_design_summary(self, project_dir: Path, summary: dict) -> None:
        self.design_spec_store.save_design_summary(project_dir, summary)

    def load_design_summary(self, project_dir: Path) -> dict | None:
        """디자인 요약을 로드한다.

        DESIGN.md 가 있으면 거기서 파생한 design_summary 가 정본이다
        (사람이 편집한 의도가 우선). 없으면 design_summary.json 으로 폴백한다.
        """
        doc = self.load_design_doc_md(project_dir)
        if doc is not None and doc.design_summary:
            return doc.design_summary
        return self.design_spec_store.load_design_summary(project_dir)

    # --- DESIGN.md (사람이 편집하는 디자인 의도 단일 소스) ---

    def save_design_doc_md(self, project_dir: Path, text: str) -> None:
        self._ensure_dir(project_dir)
        self.design_spec_store.save_design_doc_md(project_dir, text)

    def load_design_doc_md(self, project_dir: Path):
        """DESIGN.md 를 파싱해 DesignDocMd 로 반환한다. 없으면 None."""
        from ppt_generator.tools.design.design_doc_md import parse_design_doc_md

        raw = self.design_spec_store.load_design_doc_md(project_dir)
        if raw is None:
            return None
        return parse_design_doc_md(raw)

    def design_doc_md_exists(self, project_dir: Path) -> bool:
        return self.design_spec_store.design_doc_md_exists(project_dir)

    def load_bg_image_policy(self, project_dir: Path) -> str:
        """title/closing 배경 자동 주입 정책을 반환한다 ("gradient" | "none").

        DESIGN.md(또는 머신 요약)의 background_image 키에서 파생한다. 값이
        없으면 하위 호환을 위해 "gradient"(자동 주입 켜짐)가 기본이다.
        """
        summary = self.load_design_summary(project_dir)
        policy = (summary or {}).get("background_image")
        return policy if policy in ("gradient", "none") else "gradient"

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
            "presenter_name": metadata.presenter_name,
            "presenter_title": metadata.presenter_title,
            "presenter_org": metadata.presenter_org,
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

    def sync_num_slides(self, project_dir: Path) -> None:
        """project.json의 num_slides를 실제 디자인 스펙 파일 수와 동기화한다."""
        with self._metadata_lock:
            actual_count = self.get_design_spec_slide_count(project_dir)
            metadata = self.load_metadata(project_dir)
            if metadata.num_slides != actual_count:
                metadata.num_slides = actual_count
                self.save_metadata(project_dir, metadata)
                logger.info(
                    "num_slides 동기화: %d → %d", metadata.num_slides, actual_count
                )

    def load_metadata(self, project_dir: Path) -> ProjectMetadata:
        path = project_dir / "project.json"
        if not path.exists():
            if not project_dir.exists():
                raise FileNotFoundError(
                    f"프로젝트 디렉토리가 존재하지 않습니다: {project_dir}"
                )
            return ProjectMetadata(topic="", num_slides=0, steps_completed={})
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectMetadata(
            topic=data.get("topic", ""),
            num_slides=data.get("num_slides", 0),
            steps_completed=data.get("steps_completed", {}),
            audience_type=data.get("audience_type", "general"),
            presentation_minutes=data.get("presentation_minutes", 15),
            source=data.get("source", "generated"),
            presenter_name=data.get("presenter_name", ""),
            presenter_title=data.get("presenter_title", ""),
            presenter_org=data.get("presenter_org", ""),
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
                created_at = datetime.fromtimestamp(
                    created_ts, tz=timezone.utc
                ).isoformat()
            except Exception:
                logger.warning("프로젝트 메타데이터 로드 실패, 건너뜀: %s", child)
                continue

            projects.append(
                {
                    "project_id": child.name,
                    "topic": data.get("topic", ""),
                    "num_slides": data.get("num_slides", 0),
                    "steps_completed": data.get("steps_completed", {}),
                    "audience_type": data.get("audience_type", "general"),
                    "presentation_minutes": data.get("presentation_minutes", 15),
                    "source": data.get("source", "generated"),
                    "created_at": created_at,
                }
            )

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
        maxBytes=10 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(_log_fmt))
    logging.getLogger().addHandler(fh)
    _active_handlers[project_id] = fh
