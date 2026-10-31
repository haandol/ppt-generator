"""CI의 실제 버전 읽기 코드가 설치할 고정값을 전달하는지 확인한다."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


def test_ci_exports_the_committed_uv_version(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    version = (root / ".uv-version").read_text()
    output = _execute_version_step(root, tmp_path, version)
    assert output.returncode == 0, output.stderr
    assert (tmp_path / "github-output").read_text() == f"version={version.strip()}\n"


@pytest.mark.parametrize("version", ["", "0.13.6\nother=value", "$(arbitrary-command)"])
def test_invalid_ci_version_does_not_write_an_output(
    tmp_path: Path, version: str
) -> None:
    root = Path(__file__).resolve().parents[2]
    output = _execute_version_step(root, tmp_path, version)
    assert output.returncode != 0
    assert not (tmp_path / "github-output").exists()


def _execute_version_step(
    root: Path, directory: Path, version: str
) -> subprocess.CompletedProcess[str]:
    workflow = (root / ".github/workflows/ci.yml").read_text()
    step = re.search(
        r"- name: Read pinned uv version\n(?P<step>.*?)\n      - uses: astral-sh/setup-uv@",
        workflow,
        re.S,
    )
    assert step is not None
    assert "id: uv" in step.group("step")
    assert "version: ${{ steps.uv.outputs.version }}" in workflow
    script = re.search(
        r"python3 - <<'PY'\n(?P<code>.*?)\n          PY", step.group("step"), re.S
    )
    assert script is not None
    (directory / ".uv-version").write_text(version)
    env = dict(os.environ, GITHUB_OUTPUT=str(directory / "github-output"))
    return subprocess.run(
        [sys.executable, "-c", dedent(script.group("code"))],
        cwd=directory,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
