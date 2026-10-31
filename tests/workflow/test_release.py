"""게시 결정은 실제 GitHub를 변경하지 않는 대역으로 검증한다."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import release, verify

COMMIT = "a" * 40
REPOSITORY = "fixture/ppt-generator"


@pytest.fixture
def artifacts(tmp_path: Path) -> Path:
    directory = tmp_path / "package"
    directory.mkdir()
    (directory / "ppt_generator-0.8.1.tar.gz").write_bytes(b"verified source")
    (directory / "ppt_generator-0.8.1-py3-none-any.whl").write_bytes(b"verified wheel")
    verify.write_provenance(
        directory,
        "0.8.1",
        {
            "commit": COMMIT,
            "source_sha256": "b" * 64,
            "clean": True,
        },
        python_version="3.13.5",
        uv_version="0.9.2",
        lock_sha256="c" * 64,
    )
    return directory


class GitHubDouble:
    """GitHub의 커밋·실행·태그·산출물 상태를 따로 보관한다."""

    def __init__(self, artifacts: Path) -> None:
        self.artifacts = artifacts
        self.main = COMMIT
        self.tag = None
        self.exists = False
        self.draft = False
        self.prerelease = False
        self.assets: dict[str, bytes] = {}
        self.writes: list[tuple[str, ...]] = []
        self.runs = [
            {
                "id": 1,
                "head_sha": COMMIT,
                "head_branch": "main",
                "event": "push",
                "path": ".github/workflows/ci.yml",
                "status": "completed",
                "conclusion": "success",
                "head_repository": {"full_name": REPOSITORY},
            }
        ]

    def read(self, endpoint: str, **kwargs) -> dict | None:
        if endpoint.endswith("branches/main"):
            return {"commit": {"sha": self.main}}
        if "/actions/workflows/" in endpoint:
            return {"workflow_runs": self.runs}
        if "/git/ref/tags/" in endpoint:
            return {"object": {"type": "commit", "sha": self.tag}} if self.tag else None
        if "/releases/tags/" in endpoint:
            return (
                {
                    "draft": self.draft,
                    "prerelease": self.prerelease,
                    "assets": [{"name": name} for name in self.assets],
                    "html_url": "https://example.test/release",
                }
                if self.exists
                else None
            )
        raise AssertionError(endpoint)

    def run(self, *args: str) -> str:
        if args[:2] == ("repo", "view"):
            return json.dumps({"nameWithOwner": REPOSITORY})
        if args[:2] == ("run", "download"):
            for path in self.artifacts.iterdir():
                shutil.copyfile(path, Path(args[args.index("--dir") + 1]) / path.name)
            return ""
        if args[:2] == ("release", "download"):
            name = args[args.index("--pattern") + 1]
            (Path(args[args.index("--dir") + 1]) / name).write_bytes(self.assets[name])
            return ""
        self.writes.append(args)
        if args[0] == "api":
            self.tag = next(
                arg.removeprefix("sha=") for arg in args if arg.startswith("sha=")
            )
        elif args[:2] in (("release", "create"), ("release", "upload")):
            self.exists = True
            for name in args[3 : args.index("--repo")]:
                path = Path(name)
                self.assets[path.name] = path.read_bytes()
        elif args[:2] == ("release", "edit"):
            self.draft = False
        else:
            raise AssertionError(args)
        return ""


def notes(tmp_path: Path) -> Path:
    path = tmp_path / "notes.md"
    path.write_text("Verified release\n")
    return path


def test_dry_run_downloads_verified_artifacts_without_publishing(
    artifacts: Path, tmp_path: Path
) -> None:
    github = GitHubDouble(artifacts)
    result = release.publish(github, COMMIT, notes(tmp_path), dry_run=True)
    assert result["tag"] == "v0.8.1" and len(result["assets"]) == 4
    assert not github.writes


def test_publish_and_retry_reuse_the_same_tag_and_assets(
    artifacts: Path, tmp_path: Path
) -> None:
    github = GitHubDouble(artifacts)
    first = release.publish(github, COMMIT, notes(tmp_path))
    writes = list(github.writes)
    second = release.publish(github, COMMIT, notes(tmp_path))
    assert first["url"] == second["url"]
    assert github.tag == COMMIT and len(github.assets) == 4
    assert github.writes == writes
    assert second["assets"] == []


@pytest.mark.parametrize(
    "problem", ["main", "tag", "latest-failed", "pull-request", "fork", "prerelease"]
)
def test_wrong_source_or_state_never_publishes(
    artifacts: Path, tmp_path: Path, problem: str
) -> None:
    github = GitHubDouble(artifacts)
    if problem == "main":
        github.main = "b" * 40
    elif problem == "tag":
        github.tag = "b" * 40
    elif problem == "latest-failed":
        github.runs.append({**github.runs[0], "id": 2, "conclusion": "failure"})
    elif problem == "pull-request":
        github.runs[0]["event"] = "pull_request"
    elif problem == "fork":
        github.runs[0]["head_repository"] = {"full_name": "other/repo"}
    else:
        github.tag, github.exists, github.prerelease = COMMIT, True, True
    with pytest.raises(ValueError):
        release.publish(github, COMMIT, notes(tmp_path))
    assert not github.writes


def test_matching_partial_draft_resumes_without_overwriting_assets(
    artifacts: Path, tmp_path: Path
) -> None:
    github = GitHubDouble(artifacts)
    github.tag, github.exists, github.draft = COMMIT, True, True
    first = next(artifacts.glob("*.whl"))
    github.assets[first.name] = first.read_bytes()
    result = release.publish(github, COMMIT, notes(tmp_path))
    assert result["url"] and not github.draft
    upload = next(call for call in github.writes if call[:2] == ("release", "upload"))
    assert first.name not in {Path(arg).name for arg in upload}
    assert not any(call[0] == "api" for call in github.writes)


@pytest.mark.parametrize(
    "problem", ["hash", "path", "incomplete", "dirty", "commit", "checksums"]
)
def test_unverified_artifacts_are_rejected(artifacts: Path, problem: str) -> None:
    path = artifacts / "provenance.json"
    proof = json.loads(path.read_text())
    if problem == "hash":
        next(artifacts.glob("*.whl")).write_bytes(b"tampered")
    elif problem == "path":
        proof["artifacts"]["../outside"] = "a" * 64
    elif problem == "incomplete":
        proof["full_suite"] = False
    elif problem == "dirty":
        proof["clean"] = False
    elif problem == "commit":
        proof["commit"] = "b" * 40
    else:
        (artifacts / "SHA256SUMS").write_text("wrong\n")
    path.write_text(json.dumps(proof, sort_keys=True, indent=2) + "\n")
    if problem != "checksums":
        (artifacts / "SHA256SUMS").write_text(
            "".join(
                f"{verify.digest(file)}  {file.name}\n"
                for file in sorted(artifacts.iterdir())
                if file.name != "SHA256SUMS"
            )
        )
    with pytest.raises(ValueError):
        release.validate_artifacts(artifacts, COMMIT)


def test_conflicting_existing_asset_is_not_overwritten(
    artifacts: Path, tmp_path: Path
) -> None:
    github = GitHubDouble(artifacts)
    github.tag, github.exists = COMMIT, True
    github.assets["ppt_generator-0.8.1.tar.gz"] = b"different release"
    with pytest.raises(ValueError, match="differs"):
        release.publish(github, COMMIT, notes(tmp_path))
    assert not github.writes


def test_version_preparation_is_explicit_and_idempotent(
    workflow_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def lock(command, *, cwd, **kwargs) -> None:
        calls.append(command)
        path = cwd / "uv.lock"
        path.write_text(path.read_text().replace('"0.8.1"', '"0.8.2"'))

    monkeypatch.setattr(release.subprocess, "run", lock)
    assert release.prepare_version(workflow_root, "0.8.2") == "0.8.2"
    assert verify.distribution_version(workflow_root) == "0.8.2"
    assert release.prepare_version(workflow_root, "0.8.2") == "0.8.2"
    assert len(calls) == 1


def test_failed_lock_does_not_modify_version_files(
    workflow_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = {
        path: path.read_bytes() for path in workflow_root.rglob("*") if path.is_file()
    }

    def fail(*args, **kwargs) -> None:
        raise subprocess.CalledProcessError(1, ["uv", "lock"])

    monkeypatch.setattr(release.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        release.prepare_version(workflow_root, "0.8.2")
    assert all(path.read_bytes() == content for path, content in before.items())


def test_concurrent_version_edit_is_preserved(
    workflow_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    concurrent = workflow_root / ".claude-plugin/plugin.json"
    original_project = (workflow_root / "pyproject.toml").read_bytes()

    def lock(command, *, cwd, **kwargs) -> None:
        path = cwd / "uv.lock"
        path.write_text(path.read_text().replace('"0.8.1"', '"0.8.2"'))
        concurrent.write_text('{"version":"0.9.0","user_edit":true}')

    monkeypatch.setattr(release.subprocess, "run", lock)
    with pytest.raises(ValueError, match="changed during preparation"):
        release.prepare_version(workflow_root, "0.8.2")
    assert json.loads(concurrent.read_text())["user_edit"] is True
    assert (workflow_root / "pyproject.toml").read_bytes() == original_project


@pytest.mark.parametrize("code", [401, 403, 404, 500])
def test_only_not_found_is_an_optional_missing_resource(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    def fail(*args, **kwargs) -> None:
        raise subprocess.CalledProcessError(
            1, ["gh"], stderr=f"gh: error (HTTP {code})"
        )

    monkeypatch.setattr(release.subprocess, "check_output", fail)
    github = release.GitHub(Path.cwd())
    if code == 404:
        assert github.read("fixture", optional=True) is None
    else:
        with pytest.raises(subprocess.CalledProcessError):
            github.read("fixture", optional=True)
