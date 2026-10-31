"""슬라이드 파일 재번호화가 내용과 파일 종류를 보존하는지 검사한다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ppt_generator.tools.project.slide_file_store import (
    delete_slide_file,
    insert_slide_file,
    move_slide_file,
    renumber_dir,
)


def test_renumber_fills_gaps_and_preserves_outline_fields(tmp_path: Path) -> None:
    for index, title in [(2, "첫 장"), (5, "다음 장")]:
        (tmp_path / f"slide_{index:02d}.json").write_text(
            json.dumps({"slide_index": 99, "title": title, "source_refs": ["근거"]}),
            encoding="utf-8",
        )
    (tmp_path / "design_summary.json").write_text('{"theme": "dark"}', encoding="utf-8")
    renumber_dir(tmp_path)
    files = sorted(tmp_path.glob("slide_*.json"))
    assert [path.name for path in files] == ["slide_01.json", "slide_02.json"]
    assert [json.loads(path.read_text()) for path in files] == [
        {"slide_index": 0, "title": "첫 장", "source_refs": ["근거"]},
        {"slide_index": 1, "title": "다음 장", "source_refs": ["근거"]},
    ]
    assert (tmp_path / "design_summary.json").read_text() == '{"theme": "dark"}'
    assert not list(tmp_path.glob("_tmp_*"))


@pytest.mark.parametrize("extension", [".json", ".html"])
def test_insert_move_delete_keep_slide_contents(tmp_path: Path, extension: str) -> None:
    def content(title: str) -> str:
        return (
            json.dumps({"title": title})
            if extension == ".json"
            else f"<p>{title}</p>\n"
        )

    for index, title in enumerate(["A", "B", "C"], 1):
        (tmp_path / f"slide_{index:02d}{extension}").write_text(content(title))
    insert_slide_file(tmp_path, 1, content("추가"), extension)
    move_slide_file(tmp_path, 3, 0, extension)
    delete_slide_file(tmp_path, 2, extension)

    files = sorted(tmp_path.glob(f"slide_*{extension}"))
    assert [path.name for path in files] == [
        f"slide_{i:02d}{extension}" for i in range(1, 4)
    ]
    values = [path.read_text() for path in files]
    if extension == ".json":
        assert [json.loads(value) for value in values] == [
            {"title": title, "slide_index": index}
            for index, title in enumerate(["C", "A", "B"])
        ]
    else:
        assert values == [content(title) for title in ["C", "A", "B"]]
    assert not list(tmp_path.glob("_tmp_*"))
