"""명시한 버전 준비와 성공한 main CI 산출물의 GitHub 릴리스 게시."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path

if __package__:
    from .verify import ROOT, digest, distribution_version
else:
    from verify import ROOT, digest, distribution_version


def valid_version(value: str) -> str:
    """게시 버전을 모호한 ref가 아닌 숫자 세 부분으로 제한한다."""
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value):
        raise ValueError(f"Expected an exact MAJOR.MINOR.PATCH version: {value}")
    return value


def _write_version_file(path: Path, content: bytes) -> None:
    """같은 디렉토리에서 완성한 파일로 교체해 부분 쓰기를 피한다."""
    stream = tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=".version-", delete=False
    )
    pending = Path(stream.name)
    try:
        with stream:
            stream.write(content)
        pending.chmod(path.stat().st_mode & 0o777)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def prepare_version(root: Path, target: str) -> str:
    """버전을 한 번 지정해 반복 실행 시 다시 증가시키지 않고 네 파일을 동기화한다."""
    valid_version(target)
    current = distribution_version(root)
    if target == current:
        return target
    if tuple(map(int, target.split("."))) <= tuple(map(int, current.split("."))):
        raise ValueError(
            "The target must be the current version or a newer exact version"
        )
    names = [
        "pyproject.toml",
        "uv.lock",
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
    ]
    before = {name: (root / name).read_bytes() for name in names}
    replacements = {}
    project = before["pyproject.toml"].decode()
    pattern = r'(?ms)(^\[project\]\s*\n.*?^version\s*=\s*")[^"]+("[^\n]*$)'
    project, count = re.subn(
        pattern, lambda match: match[1] + target + match[2], project, count=1
    )
    if count != 1 or tomllib.loads(project)["project"]["version"] != target:
        raise ValueError("Could not locate the project version")
    replacements["pyproject.toml"] = project.encode()
    for name, expected in [
        (".claude-plugin/plugin.json", 1),
        (".claude-plugin/marketplace.json", 2),
    ]:
        text, count = re.subn(
            r'("version"\s*:\s*")[^"]*(")',
            lambda match: match[1] + target + match[2],
            before[name].decode(),
        )
        if count != expected:
            raise ValueError(f"Unexpected version fields in {name}")
        json.loads(text)
        replacements[name] = text.encode()
    with tempfile.TemporaryDirectory(prefix="ppt-version-") as temporary:
        staging = Path(temporary)
        for name, content in before.items():
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(replacements.get(name, content))
        subprocess.run(["uv", "lock", "--quiet"], cwd=staging, check=True, timeout=120)
        distribution_version(staging)
        replacements["uv.lock"] = (staging / "uv.lock").read_bytes()
    if any((root / name).read_bytes() != content for name, content in before.items()):
        raise ValueError("Version files changed during preparation; no update applied")
    written = []
    try:
        for name, content in replacements.items():
            if (root / name).read_bytes() != before[name]:
                raise ValueError(f"Version file changed concurrently: {name}")
            _write_version_file(root / name, content)
            written.append(name)
    except (OSError, ValueError):
        for name in written:
            if (root / name).read_bytes() == replacements[name]:
                _write_version_file(root / name, before[name])
        raise
    return target


class GitHub:
    """명시적 argv로 gh를 실행하고 조회 실패를 구분한다."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, *args: str) -> str:
        return subprocess.check_output(
            ["gh", *args], cwd=self.root, text=True, stderr=subprocess.PIPE
        )

    def read(self, endpoint: str, *, optional: bool = False) -> dict | None:
        try:
            return json.loads(self.run("api", endpoint))
        except subprocess.CalledProcessError as exc:
            if optional and "(HTTP 404)" in (exc.stderr or ""):
                return None
            raise


def successful_run(runs: list[dict], commit: str, repository: str) -> dict:
    """정확한 main push·워크플로·커밋의 최신 실행만 게시 근거로 선택한다."""
    candidates = [
        run
        for run in runs
        if run.get("head_sha") == commit
        and run.get("head_branch") == "main"
        and run.get("event") == "push"
        and run.get("path", "").split("@")[0] == ".github/workflows/ci.yml"
        and run.get("head_repository", {}).get("full_name") == repository
    ]
    if not candidates:
        raise ValueError("No main push CI run exists for this commit")
    latest = max(candidates, key=lambda run: (run["id"], run.get("run_attempt", 1)))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise ValueError("The latest CI run for this commit has not succeeded")
    return latest


def validate_artifacts(directory: Path, commit: str) -> tuple[str, list[Path]]:
    """CI에서 받은 패키지의 완료 상태·커밋·파일명·내용 해시를 검증한다."""
    proof = json.loads((directory / "provenance.json").read_text())
    if proof.get("schema_version") != 1 or proof.get("commit") != commit:
        raise ValueError("Artifact provenance does not match the requested commit")
    if any(proof.get(key) is not True for key in ("passed", "full_suite", "clean")):
        raise ValueError(
            "Only a complete successful verification of a clean source is publishable"
        )
    version = valid_version(proof["version"])
    expected = {
        f"ppt_generator-{version}.tar.gz",
        f"ppt_generator-{version}-py3-none-any.whl",
    }
    if set(proof.get("artifacts", {})) != expected:
        raise ValueError("Unexpected distribution filenames")
    files = []
    for name in sorted(expected | {"provenance.json", "SHA256SUMS"}):
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing or indirect release artifact: {name}")
        if name in expected and digest(path) != proof["artifacts"][name]:
            raise ValueError(f"Artifact hash mismatch: {name}")
        files.append(path)
    checksums = "".join(
        f"{digest(path)}  {path.name}\n" for path in files if path.name != "SHA256SUMS"
    )
    if (directory / "SHA256SUMS").read_text() != checksums:
        raise ValueError("SHA256SUMS does not match the verified artifacts")
    return version, files


def tag_commit(github: GitHub, repository: str, tag: str) -> str | None:
    """lightweight/annotated tag를 실제 커밋까지 해석한다."""
    ref = github.read(f"repos/{repository}/git/ref/tags/{tag}", optional=True)
    if ref is None:
        return None
    obj = ref["object"]
    for _ in range(10):
        if obj["type"] == "commit":
            return obj["sha"]
        if obj["type"] != "tag":
            break
        obj = github.read(f"repos/{repository}/git/tags/{obj['sha']}")["object"]
    raise ValueError("Release tag does not resolve to a commit")


def publish(github: GitHub, commit: str, notes: Path, *, dry_run: bool = False) -> dict:
    """통과한 CI 산출물을 재빌드 없이 게시하고 재시도 시 기존 결과를 확인한다."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("--commit must be a full commit SHA")
    if not notes.is_file():
        raise ValueError("--notes-file must exist")
    repository = json.loads(github.run("repo", "view", "--json", "nameWithOwner"))[
        "nameWithOwner"
    ]
    if github.read(f"repos/{repository}/branches/main")["commit"]["sha"] != commit:
        raise ValueError("The requested commit is not the current remote main commit")
    runs = github.read(
        f"repos/{repository}/actions/workflows/ci.yml/runs?head_sha={commit}&branch=main&event=push&per_page=100"
    )
    run = successful_run(runs["workflow_runs"], commit, repository)
    with tempfile.TemporaryDirectory(prefix="ppt-release-") as temporary:
        directory = Path(temporary)
        github.run(
            "run",
            "download",
            str(run["id"]),
            "--repo",
            repository,
            "--name",
            f"package-{commit}",
            "--dir",
            str(directory),
        )
        version, files = validate_artifacts(directory, commit)
        tag = f"v{version}"
        target = tag_commit(github, repository, tag)
        if target is not None and target != commit:
            raise ValueError("The existing release tag points to another commit")
        existing = github.read(f"repos/{repository}/releases/tags/{tag}", optional=True)
        if existing is not None and target is None:
            raise ValueError("An existing release has no matching tag")
        if existing is not None and existing["prerelease"]:
            raise ValueError(
                "An existing prerelease requires an explicit release decision"
            )
        missing = list(files)
        if existing is not None:
            names = {asset["name"] for asset in existing["assets"]}
            existing_dir = directory / "existing"
            existing_dir.mkdir()
            missing = []
            for path in files:
                if path.name not in names:
                    missing.append(path)
                    continue
                github.run(
                    "release",
                    "download",
                    tag,
                    "--repo",
                    repository,
                    "--pattern",
                    path.name,
                    "--dir",
                    str(existing_dir),
                )
                if digest(existing_dir / path.name) != digest(path):
                    raise ValueError(f"Existing release asset differs: {path.name}")
        plan = {
            "version": version,
            "tag": tag,
            "commit": commit,
            "ci_run": run["id"],
            "assets": [path.name for path in missing],
            "dry_run": dry_run,
        }
        if dry_run:
            return plan
        if target is None:
            github.run(
                "api",
                f"repos/{repository}/git/refs",
                "--method",
                "POST",
                "-f",
                f"ref=refs/tags/{tag}",
                "-f",
                f"sha={commit}",
            )
        if existing is None:
            github.run(
                "release",
                "create",
                tag,
                *map(str, files),
                "--repo",
                repository,
                "--verify-tag",
                "--target",
                commit,
                "--title",
                tag,
                "--notes-file",
                str(notes.resolve()),
            )
        else:
            if missing:
                github.run(
                    "release", "upload", tag, *map(str, missing), "--repo", repository
                )
            if existing["draft"]:
                github.run(
                    "release", "edit", tag, "--repo", repository, "--draft=false"
                )
        released = github.read(f"repos/{repository}/releases/tags/{tag}")
        if (
            tag_commit(github, repository, tag) != commit
            or released["draft"]
            or released["prerelease"]
        ):
            raise ValueError(
                "Published release state does not match the verified commit"
            )
        if not {path.name for path in files} <= {
            asset["name"] for asset in released["assets"]
        }:
            raise ValueError("Published release is missing verified assets")
        return {**plan, "url": released["html_url"]}


def main() -> int:
    """버전 준비와 게시를 별도 명령으로 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("version")
    release = commands.add_parser("publish")
    release.add_argument("--commit", required=True)
    release.add_argument("--notes-file", required=True, type=Path)
    release.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = (
            {"version": prepare_version(ROOT, args.version)}
            if args.command == "prepare"
            else publish(
                GitHub(ROOT), args.commit, args.notes_file, dry_run=args.dry_run
            )
        )
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Release failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
