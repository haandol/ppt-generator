"""캡처·변환 결과가 없는 검사를 성공으로 보고하지 않는지 검사한다."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from ppt_generator.tools.visual_qa.service import VisualQAService


def helper(name: str):
    path = (
        Path(__file__).resolve().parents[1]
        / "skills/ppt-import-verify/scripts"
        / f"{name}.py"
    )
    spec = importlib.util.spec_from_file_location(f"test_helper_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mode", ["complete", "partial", "empty", "missing-file"])
def test_capture_requires_all_requested_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    (tmp_path / "slides").mkdir()
    (tmp_path / "slides.html").write_text("container")
    for index in (1, 2):
        (tmp_path / f"slides/slide_{index:02d}.html").write_text("slide")

    def capture(self, project_dir, indices, iteration):
        output = {}
        for index in indices:
            if mode == "empty" or (mode == "partial" and index == 1):
                continue
            path = tmp_path / f"shot-{index}.png"
            if mode != "missing-file":
                path.write_bytes(b"fixture")
            output[index] = path
        return output

    monkeypatch.setattr(VisualQAService, "capture_screenshots", capture)
    monkeypatch.setattr(
        sys, "argv", ["capture_import", str(tmp_path), "--slides", "1,2"]
    )
    assert helper("capture_import").main() == (0 if mode == "complete" else 1)


@pytest.mark.parametrize("selection", ["0", "-1", "3", "bad"])
def test_invalid_capture_indices_do_not_start_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: str
) -> None:
    (tmp_path / "slides").mkdir()
    (tmp_path / "slides.html").write_text("container")
    (tmp_path / "slides/slide_01.html").write_text("slide")

    def forbidden(*args, **kwargs):
        pytest.fail("invalid input reached screenshot capture")

    monkeypatch.setattr(VisualQAService, "capture_screenshots", forbidden)
    monkeypatch.setattr(
        sys, "argv", ["capture_import", str(tmp_path), "--slides", selection]
    )
    assert helper("capture_import").main() == 2


def test_empty_original_render_is_not_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = helper("render_original")
    source = tmp_path / "deck.pptx"
    source.write_bytes(b"fixture")
    output = tmp_path / "rendered"
    output.mkdir()

    def convert(command, **kwargs):
        if "--convert-to" in command:
            (output / "deck.pdf").write_bytes(b"fixture")

    monkeypatch.setattr(module, "_find_soffice", lambda: "soffice")
    monkeypatch.setattr(module.shutil, "which", lambda name: name)
    monkeypatch.setattr(module.subprocess, "run", convert)
    monkeypatch.setattr(sys, "argv", ["render_original", str(source), str(output)])
    assert module.main() == 1
