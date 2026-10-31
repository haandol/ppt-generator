"""실제 파일을 사용하는 검증·릴리스 명령 테스트 자료."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify


@pytest.fixture
def workflow_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / "src/ppt_generator").mkdir(parents=True)
    (root / "src/ppt_generator/__init__.py").write_text('"""Fixture package."""\n')
    (root / "pyproject.toml").write_text(
        '[project]\nname = "ppt-generator"\nversion = "0.8.1"\n'
    )
    (root / "uv.lock").write_text(
        '[[package]]\nname = "ppt-generator"\nversion = "0.8.1"\n'
    )
    (root / ".claude-plugin/plugin.json").write_text(
        '{"name":"ppt-generator","version":"0.8.1"}\n'
    )
    (root / ".claude-plugin/marketplace.json").write_text(
        json.dumps(
            {
                "metadata": {"version": "0.8.1"},
                "plugins": [{"name": "ppt-generator", "version": "0.8.1"}],
            }
        )
    )
    (root / ".python-version").write_text("3.13.5\n")
    (root / ".uv-version").write_text("0.9.2\n")
    return root


@pytest.fixture
def workflow_environment(workflow_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    files = [
        str(path.relative_to(workflow_root))
        for path in workflow_root.rglob("*")
        if path.is_file()
    ]

    def git(root: Path, *args: str) -> str:
        if args[0] == "rev-parse":
            return "a" * 40
        if args[0] == "show":
            return "1700000000"
        if args[0] == "status":
            return ""
        raise AssertionError(args)

    def output(command: list[str], **kwargs) -> str | bytes:
        if command[:2] == ["git", "ls-files"]:
            return ("\0".join(reversed(files)) + "\0").encode()
        if command == ["uv", "--version"]:
            return "uv 0.9.2\n"
        if command[:3] == ["uv", "run", "--no-sync"]:
            return "3.13.5\n"
        raise AssertionError(command)

    monkeypatch.setattr(verify, "git", git)
    monkeypatch.setattr(verify.subprocess, "check_output", output)
