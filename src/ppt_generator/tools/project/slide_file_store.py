"""슬라이드 파일 CRUD 공통 로직.

jsonl_store, design_spec_store, html_store 등에서 공유하는
파일명 생성, 정렬, 삭제/삽입/이동/리넘버링 로직을 제공한다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def slide_filename(index: int) -> str:
    """0-based 인덱스를 slide_01.json 형식 파일명으로 변환."""
    return f"slide_{index + 1:02d}.json"


def sorted_slide_files(directory: Path, ext: str = ".json") -> list[Path]:
    """디렉토리 내 slide_*.{ext} 파일을 정렬해서 반환."""
    if not directory.exists():
        return []
    return sorted(directory.glob(f"slide_*{ext}"))


def validate_index(files: list[Path], index: int) -> None:
    """인덱스 범위를 검증한다. 범위 밖이면 IndexError."""
    if index < 0 or index >= len(files):
        raise IndexError(f"유효하지 않은 slide index: {index} (전체 {len(files)}장)")


def delete_slide_file(directory: Path, index: int, ext: str = ".json") -> None:
    """파일 삭제 + 리넘버링."""
    files = sorted_slide_files(directory, ext)
    validate_index(files, index)
    files[index].unlink()
    _renumber_files(directory, ext)


def insert_slide_file(
    directory: Path, index: int, content: str, ext: str = ".json",
) -> None:
    """파일 삽입 (후속 파일 시프트) + 리넘버링."""
    files = sorted_slide_files(directory, ext)
    count = len(files)
    if index < 0 or index > count:
        index = count
    # 뒤에서부터 한 칸씩 밀기
    name_fn = _make_filename_fn(ext)
    for i in range(count - 1, index - 1, -1):
        old_name = directory / name_fn(i)
        new_name = directory / name_fn(i + 1)
        old_name.rename(new_name)
    # 새 파일 작성
    (directory / name_fn(index)).write_text(content, encoding="utf-8")
    if ext == ".json":
        _renumber_slide_index(directory, ext)


def move_slide_file(
    directory: Path, from_idx: int, to_idx: int, ext: str = ".json",
) -> None:
    """파일 이동 + 리넘버링."""
    files = sorted_slide_files(directory, ext)
    count = len(files)
    if from_idx < 0 or from_idx >= count:
        raise IndexError(f"유효하지 않은 from_index: {from_idx} (전체 {count}장)")
    if to_idx < 0 or to_idx >= count:
        raise IndexError(f"유효하지 않은 to_index: {to_idx} (전체 {count}장)")
    if from_idx == to_idx:
        return
    contents = [f.read_text(encoding="utf-8") for f in files]
    item = contents.pop(from_idx)
    contents.insert(to_idx, item)
    name_fn = _make_filename_fn(ext)
    for i, content in enumerate(contents):
        (directory / name_fn(i)).write_text(content, encoding="utf-8")
    if ext == ".json":
        _renumber_slide_index(directory, ext)


def renumber_dir(directory: Path) -> None:
    """디렉토리 내 모든 slide JSON 파일의 slide_index를 파일 순서에 맞게 재번호한다."""
    _renumber_slide_index(directory, ".json")


# --- internal ---


def _make_filename_fn(ext: str):
    """확장자에 맞는 파일명 생성 함수를 반환."""
    if ext == ".html":
        return lambda i: f"slide_{i + 1:02d}.html"
    return lambda i: f"slide_{i + 1:02d}.json"


def _renumber_files(directory: Path, ext: str) -> None:
    """파일명 재번호. JSON이면 slide_index도 갱신."""
    files = sorted_slide_files(directory, ext)
    name_fn = _make_filename_fn(ext)
    # 1) 임시 이름으로 rename (파일명 충돌 방지)
    tmp_pairs: list[tuple[Path, int]] = []
    for i, f in enumerate(files):
        tmp = directory / f"_tmp_{i}{ext}"
        f.rename(tmp)
        tmp_pairs.append((tmp, i))
    # 2) 최종 이름으로 rename
    for tmp, i in tmp_pairs:
        target = directory / name_fn(i)
        if ext == ".json":
            data = json.loads(tmp.read_text(encoding="utf-8"))
            data["slide_index"] = i
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            if tmp.exists():
                tmp.unlink()
        else:
            tmp.rename(target)


def _renumber_slide_index(directory: Path, ext: str) -> None:
    """JSON 파일의 slide_index만 파일 순서에 맞게 갱신 (파일명 변경 없이)."""
    files = sorted_slide_files(directory, ext)
    # 임시 이름으로 rename (충돌 방지)
    tmp_pairs: list[tuple[Path, int]] = []
    for i, f in enumerate(files):
        tmp = directory / f"_tmp_{i}{ext}"
        f.rename(tmp)
        tmp_pairs.append((tmp, i))
    # 최종 이름으로 rename + slide_index 갱신
    name_fn = _make_filename_fn(ext)
    for tmp, i in tmp_pairs:
        data = json.loads(tmp.read_text(encoding="utf-8"))
        data["slide_index"] = i
        target = directory / name_fn(i)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if tmp.exists():
            tmp.unlink()
