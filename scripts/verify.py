"""로컬과 CI에서 같은 소스·의존성으로 검사하고 검증한 패키지를 보관한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tarfile
import tempfile
import time
import tomllib
import zipfile
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    """파일 내용의 SHA-256을 반환한다."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: Path, *args: str) -> str:
    """현재 저장소에서 읽기 전용 Git 명령을 실행한다."""
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def distribution_version(root: Path) -> str:
    """패키지·잠금 파일·두 플러그인 매니페스트의 버전을 대조한다."""
    project = tomllib.loads((root / "pyproject.toml").read_text())
    lock = tomllib.loads((root / "uv.lock").read_text())
    plugin = json.loads((root / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())
    name = project["project"]["name"]
    packages = [p for p in lock["package"] if p["name"] == name]
    entries = [p for p in marketplace["plugins"] if p["name"] == name]
    if len(packages) != 1 or len(entries) != 1:
        raise ValueError("Expected one package and one matching marketplace entry")
    versions = {
        "project": project["project"]["version"],
        "lock": packages[0]["version"],
        "plugin": plugin["version"],
        "marketplace": marketplace["metadata"]["version"],
        "marketplace_entry": entries[0]["version"],
    }
    if len(set(versions.values())) != 1:
        raise ValueError(f"Distribution versions differ: {versions}")
    return versions["project"]


def source_snapshot(root: Path) -> dict:
    """무시되지 않은 소스의 내용과 실행 비트를 순서에 무관하게 기록한다."""
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
    )
    files = {}
    for raw in sorted(set(listed.split(b"\0")) - {b""}):
        name = os.fsdecode(raw)
        path = root / name
        if path.is_file():
            files[name] = {
                "sha256": digest(path),
                "executable": bool(path.stat().st_mode & 0o111),
            }
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "commit": git(root, "rev-parse", "HEAD"),
        "source_sha256": hashlib.sha256(encoded).hexdigest(),
        "clean": not git(root, "status", "--porcelain"),
        "files": files,
    }


class Runner:
    """단계별 로그와 종료 결과를 보존하고 실패한 단계에서 중단한다."""

    def __init__(self, root: Path, output: Path, env: dict[str, str]) -> None:
        self.root, self.output, self.env = root, output, env
        self.steps: list[dict] = []
        (output / "logs").mkdir(parents=True)

    def run(self, name: str, command: list[str], *, timeout: int = 600) -> None:
        started = time.monotonic()
        log = self.output / "logs" / f"{name}.log"
        print(f"[{name}] {' '.join(command)}", flush=True)
        code = None
        try:
            with log.open("w", encoding="utf-8") as stream:
                result = subprocess.run(
                    command,
                    cwd=self.root,
                    env=self.env,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                )
                code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
            raise
        except OSError:
            code = 127
            raise
        finally:
            self.steps.append(
                {
                    "name": name,
                    "command": command,
                    "exit_code": code,
                    "seconds": round(time.monotonic() - started, 3),
                    "log": str(log.relative_to(self.output)),
                }
            )
        if code:
            raise RuntimeError(f"{name} failed ({code}); see {log}")
        print(f"[{name}] passed ({self.steps[-1]['seconds']:.2f}s)", flush=True)


def verify_wheel_sources(wheel: Path, snapshot: dict) -> None:
    """검사한 패키지 소스와 wheel에 담긴 실제 파일이 같은지 대조한다."""
    with zipfile.ZipFile(wheel) as archive:
        for name, value in snapshot["files"].items():
            if not name.startswith("src/ppt_generator/"):
                continue
            member = name.removeprefix("src/")
            actual = hashlib.sha256(archive.read(member)).hexdigest()
            if actual != value["sha256"]:
                raise ValueError(f"Wheel differs from verified source: {member}")


def verify_sdist_sources(sdist: Path, version: str, snapshot: dict) -> None:
    """검사하지 않은 로컬 산출물이 소스 배포본에 섞이지 않았는지 확인한다."""
    prefix = f"ppt_generator-{version}/"
    seen = set()
    with tarfile.open(sdist, "r|gz") as archive:
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile() or not member.name.startswith(prefix):
                raise ValueError(f"Unexpected source archive member: {member.name}")
            name = member.name.removeprefix(prefix)
            if name == "PKG-INFO":
                continue
            if name not in snapshot["files"]:
                raise ValueError(f"Unverified file in source archive: {name}")
            stream = archive.extractfile(member)
            actual = hashlib.sha256(stream.read()).hexdigest()
            if actual != snapshot["files"][name]["sha256"]:
                raise ValueError(f"Source archive differs from verified input: {name}")
            seen.add(name)
    required = {
        name
        for name in snapshot["files"]
        if name.startswith(
            ("src/ppt_generator/", "skills/", "scripts/", ".claude-plugin/")
        )
    }
    required |= {"pyproject.toml", "uv.lock", ".python-version", ".uv-version"}
    if missing := required - seen:
        raise ValueError(f"Source archive is missing required files: {sorted(missing)}")


@contextmanager
def staged_sources(root: Path, snapshot: dict) -> Iterator[Path]:
    """검사한 파일만 별도 빌드 입력으로 고정한다."""
    with tempfile.TemporaryDirectory(prefix="ppt-build-") as directory:
        staging = Path(directory)
        for name, expected in snapshot["files"].items():
            data = (root / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise ValueError(f"Source changed before packaging: {name}")
            path = staging / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if expected["executable"] else 0o644)
        yield staging


def write_provenance(
    directory: Path,
    version: str,
    snapshot: dict,
    *,
    python_version: str,
    uv_version: str,
    lock_sha256: str,
) -> dict:
    """게시 가능한 산출물에 소스·도구 버전과 내용 해시를 결속한다."""
    names = [
        f"ppt_generator-{version}.tar.gz",
        f"ppt_generator-{version}-py3-none-any.whl",
    ]
    artifacts = {name: digest(directory / name) for name in sorted(names)}
    result = {
        "schema_version": 1,
        "version": version,
        "passed": True,
        "full_suite": True,
        "commit": snapshot["commit"],
        "source_sha256": snapshot["source_sha256"],
        "clean": snapshot["clean"],
        "python": python_version,
        "uv": uv_version,
        "lock_sha256": lock_sha256,
        "artifacts": artifacts,
    }
    (directory / "provenance.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    sums = {**artifacts, "provenance.json": digest(directory / "provenance.json")}
    (directory / "SHA256SUMS").write_text(
        "".join(f"{value}  {name}\n" for name, value in sorted(sums.items())),
        encoding="utf-8",
    )
    return result


def verify(root: Path, output: Path, workers: int) -> int:
    """고정된 검사 순서를 실행한다. 실패한 실행에는 성공 증명을 만들지 않는다."""
    env = dict(
        os.environ,
        PYTHONHASHSEED="0",
        PYTHONUTF8="1",
        TZ="UTC",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=str(root / "src"),
        UV_PROJECT_ENVIRONMENT=str(root / ".venv"),
    )
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS"):
        env.pop(name, None)
    runner = Runner(root, output, env)
    result: dict = {"passed": False, "steps": runner.steps}
    try:
        version = distribution_version(root)
        env["SOURCE_DATE_EPOCH"] = git(root, "show", "-s", "--format=%ct", "HEAD")
        before = source_snapshot(root)
        uv_version = subprocess.check_output(["uv", "--version"], text=True).split()[1]
        expected_uv = (root / ".uv-version").read_text().strip()
        expected_python = (root / ".python-version").read_text().strip()
        if uv_version != expected_uv:
            raise ValueError(
                f"Verification requires uv {expected_uv}; found {uv_version}"
            )
        runner.run(
            "sync",
            [
                "uv",
                "sync",
                "--locked",
                "--group",
                "build",
                "--no-install-project",
                "--python",
                expected_python,
            ],
        )
        prefix = ["uv", "run", "--no-sync"]
        runtime = subprocess.check_output(
            [
                *prefix,
                "python",
                "-c",
                "import platform; print(platform.python_version())",
            ],
            cwd=root,
            env=env,
            text=True,
        ).strip()
        if runtime != expected_python:
            raise ValueError(f"Expected Python {expected_python}; found {runtime}")
        runner.run("format", [*prefix, "ruff", "format", "--check", "."])
        runner.run("lint", [*prefix, "ruff", "check", "."])
        pytest_args = [
            *prefix,
            "python",
            "-m",
            "pytest",
            "-q",
            "--durations=10",
            f"--junitxml={output / 'tests.xml'}",
        ]
        if workers > 1:
            pytest_args += [
                "-p",
                "xdist.plugin",
                "-n",
                str(workers),
                "--dist",
                "loadscope",
            ]
        runner.run("tests", pytest_args)
        dist = output / "dist"
        build_python = (
            root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        with staged_sources(root, before) as staging:
            runner.run(
                "build",
                [
                    "uv",
                    "build",
                    str(staging),
                    "--no-build-isolation",
                    "--out-dir",
                    str(dist),
                    "--python",
                    str(build_python),
                ],
            )
        wheel = dist / f"ppt_generator-{version}-py3-none-any.whl"
        verify_sdist_sources(dist / f"ppt_generator-{version}.tar.gz", version, before)
        verify_wheel_sources(wheel, before)
        runner.run(
            "package-smoke",
            [
                *prefix,
                "python",
                "-I",
                str(root / "scripts/package_smoke.py"),
                str(wheel),
            ],
        )
        after = source_snapshot(root)
        if before != after:
            raise ValueError(
                "Source changed during verification; rerun against the current files"
            )
        result["provenance"] = write_provenance(
            dist,
            version,
            before,
            python_version=runtime,
            uv_version=uv_version,
            lock_sha256=digest(root / "uv.lock"),
        )
        result["passed"] = True
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        result["error"] = str(exc)
        print(f"Verification failed: {exc}", flush=True)
    finally:
        result["driver_python"] = platform.python_version()
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"Verification result: {output / 'result.json'}", flush=True)
    return 0 if result["passed"] else 1


def main() -> int:
    """새 출력 디렉토리에 전체 검증을 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    if args.output:
        output = args.output.resolve()
        if output.is_relative_to(ROOT):
            ignored = subprocess.run(
                ["git", "check-ignore", "--quiet", str(output / "verification-output")],
                cwd=ROOT,
                check=False,
            )
            if ignored.returncode:
                parser.error(
                    "An output inside the repository must be ignored; use output/<new-directory>"
                )
        output.mkdir(parents=True, exist_ok=False)
    else:
        (ROOT / "output").mkdir(exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="verification-", dir=ROOT / "output"))
    return verify(ROOT, output, args.workers)


if __name__ == "__main__":
    raise SystemExit(main())
