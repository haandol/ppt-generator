"""임시 경로의 별칭과 실제 wheel 추출 경계를 확인한다."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.package_smoke import extract_wheel


def test_wheel_extracts_through_a_symlinked_temporary_parent(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    wheel = tmp_path / "fixture.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("ppt_generator/__init__.py", "fixture")
    root = extract_wheel(wheel, alias)
    assert root == actual.resolve()
    assert (actual / "ppt_generator/__init__.py").read_text() == "fixture"


@pytest.mark.parametrize("member", ["../escaped.py", "/absolute.py"])
def test_invalid_member_is_rejected_before_any_extraction(
    tmp_path: Path, member: str
) -> None:
    wheel = tmp_path / "fixture.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("safe.py", "safe")
        archive.writestr(member, "outside")
    directory = tmp_path / "unpacked"
    directory.mkdir()
    with pytest.raises(ValueError, match="Invalid wheel member"):
        extract_wheel(wheel, directory)
    assert not list(directory.iterdir())
    assert not (tmp_path / "escaped.py").exists()
