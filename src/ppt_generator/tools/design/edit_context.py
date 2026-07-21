"""슬라이드 편집 prepare/ingest 상관관계와 원자 커밋 지원."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Any

_CONTEXT_VERSION = 1
_RECEIPT_DIR = ".edit_receipts"
_TOKEN_SECRET = secrets.token_bytes(32)
_LOCK_GUARD = Lock()
_PROJECT_LOCKS: dict[Path, Lock] = {}


def project_revision(project_dir: Path) -> str:
    """프로젝트 파일 내용으로 안정적인 revision 해시를 계산한다."""
    digest = hashlib.sha256()
    if not project_dir.exists():
        return digest.hexdigest()
    for path in sorted(p for p in project_dir.rglob("*") if p.is_file()):
        relative = path.relative_to(project_dir)
        if relative.parts and relative.parts[0] == _RECEIPT_DIR:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True)
class SlideEditContext:
    """prepare에서 고정한 슬라이드 편집 의도."""

    project_id: str
    action: str
    requested_slide_index: int
    target_index: int
    original_slide_count: int
    outline: dict[str, Any]
    color_theme: str
    revision: str
    operation_id: str = ""
    version: int = _CONTEXT_VERSION

    def to_token(self) -> str:
        """서버만 발급할 수 있는 URL-safe 서명 토큰으로 직렬화한다."""
        payload = asdict(self)
        payload["operation_id"] = _operation_id(payload)
        signature = _sign_payload(payload)
        raw = _canonical_json({"payload": payload, "signature": signature}).encode(
            "utf-8"
        )
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @classmethod
    def from_token(cls, token: str) -> "SlideEditContext":
        """토큰의 서버 서명과 operation id를 검증해 역직렬화한다."""
        try:
            padding = "=" * (-len(token) % 4)
            data = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
        except Exception as exc:
            raise ValueError("Invalid edit_context token") from exc
        if not isinstance(data, dict):
            raise ValueError("Invalid edit_context payload")
        payload = data.get("payload")
        signature = data.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature, str):
            raise ValueError("Invalid edit_context payload")
        if not hmac.compare_digest(signature, _sign_payload(payload)):
            raise ValueError("edit_context signature check failed")
        expected = _operation_id(payload)
        if payload.get("operation_id") != expected:
            raise ValueError("edit_context integrity check failed")
        try:
            context = cls(**payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid edit_context payload") from exc
        if context.version != _CONTEXT_VERSION:
            raise ValueError(f"Unsupported edit_context version: {context.version}")
        if context.action not in {"add", "update"}:
            raise ValueError(f"Invalid edit_context action: {context.action}")
        return context


def project_edit_lock(project_dir: Path) -> Lock:
    """같은 프로젝트의 편집 커밋을 프로세스 내에서 직렬화한다."""
    key = project_dir.resolve()
    with _LOCK_GUARD:
        return _PROJECT_LOCKS.setdefault(key, Lock())


class ProjectSnapshot:
    """편집 중 실패 시 프로젝트 디렉토리를 이전 상태로 복원한다."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir
        self._temp_dir = Path(tempfile.mkdtemp(prefix="ppt-edit-"))
        self._backup_dir = self._temp_dir / "project"
        shutil.copytree(project_dir, self._backup_dir)
        self._committed = False

    def commit(self) -> None:
        self._committed = True

    def __enter__(self) -> "ProjectSnapshot":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if exc_type is not None and not self._committed:
                shutil.rmtree(self._project_dir, ignore_errors=True)
                shutil.copytree(self._backup_dir, self._project_dir)
        finally:
            shutil.rmtree(self._temp_dir, ignore_errors=True)


def load_receipt(project_dir: Path, operation_id: str) -> dict[str, Any] | None:
    """성공한 동일 편집의 이전 결과를 읽는다."""
    path = _receipt_path(project_dir, operation_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    result = data.get("result")
    return result if isinstance(result, dict) else None


def save_receipt(project_dir: Path, operation_id: str, result: dict[str, Any]) -> None:
    """성공 결과를 원자적으로 기록한다."""
    path = _receipt_path(project_dir, operation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps({"result": result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _receipt_path(project_dir: Path, operation_id: str) -> Path:
    if not operation_id or any(c not in "0123456789abcdef" for c in operation_id):
        raise ValueError("Invalid edit operation id")
    return project_dir / _RECEIPT_DIR / f"{operation_id}.json"


def _operation_id(payload: dict[str, Any]) -> str:
    normalized = dict(payload)
    normalized.pop("operation_id", None)
    return hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()


def _sign_payload(payload: dict[str, Any]) -> str:
    return hmac.new(
        _TOKEN_SECRET,
        _canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
