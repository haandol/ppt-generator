"""실패·입력 변경·누락 패키지를 성공한 검증으로 기록하지 않는지 검사한다."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import verify


def test_failed_step_keeps_output_and_exit_status(tmp_path: Path) -> None:
    runner = verify.Runner(tmp_path, tmp_path / "run", dict(os.environ))
    with pytest.raises(RuntimeError, match=r"failed \(7\)"):
        runner.run(
            "failing",
            [sys.executable, "-c", "print('failure evidence'); raise SystemExit(7)"],
        )
    assert runner.steps[0]["exit_code"] == 7
    assert (tmp_path / "run/logs/failing.log").read_text().strip() == "failure evidence"


def test_timeout_is_recorded_without_a_real_sleep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = verify.Runner(tmp_path, tmp_path / "run", {})

    def timeout(*args, **kwargs) -> None:
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(verify.subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        runner.run("timeout", ["fixture"])
    assert runner.steps[0]["exit_code"] == 124


def test_version_mismatch_fails_before_checks(
    workflow_root: Path, tmp_path: Path
) -> None:
    (workflow_root / ".claude-plugin/plugin.json").write_text('{"version":"0.8.2"}')
    output = tmp_path / "run"
    assert verify.verify(workflow_root, output, 2) == 1
    result = json.loads((output / "result.json").read_text())
    assert not result["passed"] and not result["steps"]
    assert "versions differ" in result["error"]
    assert not (output / "dist/provenance.json").exists()


@pytest.mark.parametrize("change", ["content", "executable"])
def test_snapshot_detects_input_changes(
    workflow_root: Path, workflow_environment, change: str
) -> None:
    before = verify.source_snapshot(workflow_root)
    path = workflow_root / "src/ppt_generator/__init__.py"
    if change == "content":
        path.write_text("changed\n")
    else:
        path.chmod(path.stat().st_mode ^ 0o111)
    after = verify.source_snapshot(workflow_root)
    assert before["commit"] == after["commit"]
    assert before["source_sha256"] != after["source_sha256"]


def test_source_archive_rejects_unverified_local_review_files(
    workflow_root: Path,
    workflow_environment,
    tmp_path: Path,
) -> None:
    snapshot = verify.source_snapshot(workflow_root)
    private = workflow_root / ".adr-review/local-notes.md"
    private.parent.mkdir()
    private.write_text("local review evidence")
    archive_path = tmp_path / "source.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in workflow_root.rglob("*"):
            if path.is_file():
                archive.add(
                    path,
                    arcname=f"ppt_generator-0.8.1/{path.relative_to(workflow_root)}",
                )
    with pytest.raises(ValueError, match="Unverified file in source archive"):
        verify.verify_sdist_sources(archive_path, "0.8.1", snapshot)


def test_staging_contains_only_verified_source_files(
    workflow_root: Path, workflow_environment
) -> None:
    snapshot = verify.source_snapshot(workflow_root)
    private = workflow_root / "docs/reviews/local.html"
    private.parent.mkdir(parents=True)
    private.write_text("untracked local output")
    with verify.staged_sources(workflow_root, snapshot) as staging:
        assert not (staging / "docs/reviews/local.html").exists()
        assert (staging / "src/ppt_generator/__init__.py").read_bytes() == (
            workflow_root / "src/ppt_generator/__init__.py"
        ).read_bytes()
        assert {
            str(path.relative_to(staging))
            for path in staging.rglob("*")
            if path.is_file()
        } == set(snapshot["files"])


def test_ambient_selection_cannot_turn_partial_tests_into_full_verification(
    workflow_root: Path,
    workflow_environment,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k one_test_only")
    monkeypatch.setenv("PYTEST_PLUGINS", "unrelated_plugin")
    observed = {}

    def stop(self, *args, **kwargs) -> None:
        observed.update(self.env)
        raise RuntimeError("stop after reading the process environment")

    monkeypatch.setattr(verify.Runner, "run", stop)
    assert verify.verify(workflow_root, tmp_path / "run", 2) == 1
    assert "PYTEST_ADDOPTS" not in observed and "PYTEST_PLUGINS" not in observed
    assert observed["UV_PROJECT_ENVIRONMENT"] == str(workflow_root / ".venv")
    assert os.environ["PYTEST_ADDOPTS"] == "-k one_test_only"


@pytest.mark.parametrize("failure", [None, "tests", "source-change", "wheel-mismatch"])
def test_verification_records_only_complete_unchanged_runs(
    workflow_root: Path,
    workflow_environment,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    executed = []

    def run(self, name: str, command: list[str], **kwargs) -> None:
        executed.append(name)
        self.steps.append({"name": name, "exit_code": 0})
        if name == failure:
            raise RuntimeError("injected test failure")
        if name == "build":
            dist = self.output / "dist"
            dist.mkdir()
            with tarfile.open(dist / "ppt_generator-0.8.1.tar.gz", "w:gz") as archive:
                for path in workflow_root.rglob("*"):
                    if path.is_file():
                        archive.add(
                            path,
                            arcname=f"ppt_generator-0.8.1/{path.relative_to(workflow_root)}",
                        )
            source = (workflow_root / "src/ppt_generator/__init__.py").read_bytes()
            with zipfile.ZipFile(
                dist / "ppt_generator-0.8.1-py3-none-any.whl", "w"
            ) as archive:
                archive.writestr(
                    "ppt_generator/__init__.py",
                    b"wrong" if failure == "wheel-mismatch" else source,
                )
        if name == "package-smoke" and failure == "source-change":
            (workflow_root / "src/ppt_generator/__init__.py").write_text(
                "changed after tests"
            )

    monkeypatch.setattr(verify.Runner, "run", run)
    output = tmp_path / "run"
    assert verify.verify(workflow_root, output, 2) == (0 if failure is None else 1)
    result = json.loads((output / "result.json").read_text())
    assert result["passed"] == (failure is None)
    assert (output / "dist/provenance.json").exists() == (failure is None)
    if failure == "tests":
        assert "build" not in executed
    if failure is None:
        proof = result["provenance"]
        assert proof["commit"] == "a" * 40
        assert proof["full_suite"] and proof["clean"]
        assert len(proof["artifacts"]) == 2
