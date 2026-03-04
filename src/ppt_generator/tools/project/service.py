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

logger = logging.getLogger(__name__)

# server.py의 main()에서 설정됨
_log_dir: str | None = None
_log_fmt: str = "%(asctime)s %(name)s %(levelname)s %(message)s"
_active_handlers: dict[str, RotatingFileHandler] = {}


class ProjectService:
    """파이프라인 결과물의 파일 I/O를 전담하는 서비스."""

    def __init__(self, design_spec_store: DesignSpecStore | None = None) -> None:
        self.design_spec_store = design_spec_store or DesignSpecStore()
        self._metadata_lock = Lock()

    def resolve_project_dir(self, project_id: str = "") -> tuple[str, Path]:
        """project_id → (project_id, project_dir). 빈 값이면 UUID 자동 생성."""
        if not project_id:
            project_id = str(uuid.uuid4())
        project_dir = PPT_GENERATOR_HOME / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        _maybe_add_project_log_handler(project_id)
        return project_id, project_dir

    # --- 저장 메서드 ---

    def save_outline(self, project_dir: Path, outline_json: str) -> None:
        self._ensure_dir(project_dir)
        data = json.loads(outline_json)
        slides = data["slides"]
        lines = []
        for i, s in enumerate(slides):
            s["slide_index"] = i
            lines.append(json.dumps(s, ensure_ascii=False))
        (project_dir / "outline.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("outline.jsonl 저장 완료: %s", project_dir)

    def save_script(self, project_dir: Path, script_json: str) -> None:
        self._ensure_dir(project_dir)
        data = json.loads(script_json)
        slides = data["slides"]
        lines = []
        for i, s in enumerate(slides):
            s["slide_index"] = i
            lines.append(json.dumps(s, ensure_ascii=False))
        (project_dir / "script.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("script.jsonl 저장 완료: %s", project_dir)

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
            # HTML 파일만 삭제 (images/ 등 서브디렉토리는 보존)
            for f in slides_dir.glob("slide_*.html"):
                f.unlink()
        slides_dir.mkdir(parents=True, exist_ok=True)
        for i, html in enumerate(slide_htmls):
            fname = self._slide_html_filename(i)
            (slides_dir / fname).write_text(html, encoding="utf-8")
        (project_dir / "slides.html").write_text(container_html, encoding="utf-8")
        meta: dict = {"session_id": session_id}
        (project_dir / "slides_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("slides/ 저장 완료 (%d 슬라이드): %s", len(slide_htmls), project_dir)

    IMAGES_DIR = "slides/images"

    @staticmethod
    def _image_filename(slide_index: int, image_index: int) -> str:
        """이미지 파일명 생성: slide_01_img_01.png"""
        return f"slide_{slide_index + 1:02d}_img_{image_index + 1:02d}.png"

    def save_slide_images(
        self,
        project_dir: Path,
        slide_index: int,
        images: list[PptxImage],
    ) -> list[str]:
        """슬라이드의 이미지를 slides/images/ 에 PNG 파일로 저장한다.

        Returns:
            저장된 이미지의 상대경로 리스트 (HTML에서 사용할 경로, e.g. "images/slide_01_img_01.png").
            image_bytes가 비어있는 이미지는 빈 문자열.
        """
        images_dir = project_dir / self.IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        srcs: list[str] = []
        for i, img in enumerate(images):
            if not img.image_bytes:
                srcs.append("")
                continue
            fname = self._image_filename(slide_index, i)
            (images_dir / fname).write_bytes(img.image_bytes)
            srcs.append(f"images/{fname}")
        return srcs

    def get_slide_image_srcs(
        self,
        project_dir: Path,
        slide_index: int,
        image_count: int,
    ) -> list[str]:
        """슬라이드의 이미지 파일 상대경로 리스트를 반환한다.

        파일이 존재하면 상대경로, 없으면 빈 문자열.
        """
        images_dir = project_dir / self.IMAGES_DIR
        srcs: list[str] = []
        for i in range(image_count):
            fname = self._image_filename(slide_index, i)
            if (images_dir / fname).exists():
                srcs.append(f"images/{fname}")
            else:
                srcs.append("")
        return srcs

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

    def delete_slide_html(self, project_dir: Path, index: int) -> None:
        """슬라이드 HTML 파일을 삭제하고 남은 파일을 재번호한다."""
        slides_dir = project_dir / self.SLIDES_DIR
        if not slides_dir.exists():
            return
        files = sorted(slides_dir.glob("slide_*.html"))
        if index < 0 or index >= len(files):
            return
        files[index].unlink()
        remaining = sorted(slides_dir.glob("slide_*.html"))
        for i, f in enumerate(remaining):
            new_name = self._slide_html_filename(i)
            f.rename(slides_dir / new_name)

    def shift_slide_htmls(self, project_dir: Path, insert_index: int) -> None:
        """삽입 위치 이후의 슬라이드 HTML 파일을 한 칸씩 뒤로 밀어낸다."""
        slides_dir = project_dir / self.SLIDES_DIR
        if not slides_dir.exists():
            return
        files = sorted(slides_dir.glob("slide_*.html"))
        count = len(files)
        for i in range(count - 1, insert_index - 1, -1):
            old_name = slides_dir / self._slide_html_filename(i)
            new_name = slides_dir / self._slide_html_filename(i + 1)
            if old_name.exists():
                old_name.rename(new_name)

    # --- 디자인 스펙 위임 메서드 ---

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
            "audience_type": metadata.audience_type,
            "presentation_minutes": metadata.presentation_minutes,
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
        )

    def load_outline(self, project_dir: Path) -> str:
        path = project_dir / "outline.jsonl"
        if path.exists():
            slides = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            return json.dumps({"slides": slides}, ensure_ascii=False)
        # 하위 호환: 기존 outline.json fallback
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
        # 하위 호환: 기존 outline.json fallback
        legacy = project_dir / "outline.json"
        data = json.loads(legacy.read_text(encoding="utf-8"))
        slides = data["slides"]
        if index < 0 or index >= len(slides):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(slides)}장)")
        return json.dumps(slides[index], ensure_ascii=False)

    def load_script(self, project_dir: Path) -> str:
        path = project_dir / "script.jsonl"
        if not path.exists():
            # 하위 호환: 기존 script.json fallback
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
        # 하위 호환: 기존 script.json fallback
        legacy = project_dir / "script.json"
        data = json.loads(legacy.read_text(encoding="utf-8"))
        slides = data["slides"]
        if index < 0 or index >= len(slides):
            raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(slides)}장)")
        return json.dumps(slides[index], ensure_ascii=False)

    # --- 아웃라인/스크립트 JSONL CRUD ---

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

    def _resolve_outline_or_script_path(self, project_dir: Path) -> Path | None:
        """script.jsonl이 있으면 우선 반환, 없으면 outline.jsonl을 반환한다. 둘 다 없으면 None."""
        script_path = project_dir / "script.jsonl"
        if script_path.exists():
            return script_path
        outline_path = project_dir / "outline.jsonl"
        if outline_path.exists():
            return outline_path
        return None

    def update_outline_slide(self, project_dir: Path, index: int, slide_json: str) -> None:
        """아웃라인/스크립트 JSONL에서 특정 슬라이드를 교체한다. 둘 다 존재하면 둘 다 업데이트한다."""
        updated = False
        for fname in ("script.jsonl", "outline.jsonl"):
            path = project_dir / fname
            if not path.exists():
                continue
            lines = self._load_jsonl_lines(path)
            if index < 0 or index >= len(lines):
                raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(lines)}장)")
            # 기존 줄의 speaker_notes 등 보존하면서 새 아웃라인 필드 병합
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
        """아웃라인/스크립트 JSONL에 슬라이드를 삽입한다. 둘 다 존재하면 둘 다 삽입한다."""
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
        """아웃라인/스크립트 JSONL에서 슬라이드를 삭제한다. 둘 다 존재하면 둘 다 삭제한다."""
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

    def load_script_or_outline(self, project_dir: Path) -> str:
        """script.jsonl이 있으면 우선 로드, 없으면 outline.jsonl로 fallback."""
        script_path = project_dir / "script.jsonl"
        if script_path.exists():
            return self.load_script(project_dir)
        # 하위 호환: 기존 script.json fallback
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
                "audience_type": data.get("audience_type", "general"),
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
