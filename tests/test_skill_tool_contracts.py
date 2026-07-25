"""스킬 문서(SKILL.md)가 서술하는 MCP 도구 호출이 실제 서버와 맞는지 검증한다.

스킬은 플러그인 사용자가 직접 밟는 경로이므로, 도구명이나 파라미터명이 어긋나면
사용자가 실패하는 호출을 하게 된다. 도구 시그니처가 정본이고 스킬 문서가 따라간다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILLS_DIR = _REPO_ROOT / "skills"
_CONTROLLERS = sorted(
    (_REPO_ROOT / "src" / "ppt_generator" / "tools").glob("*/controller.py")
)

# 도구가 아니라 파이썬/셸 예시나 산문에서 등장하는 이름 — 도구 호출로 보지 않는다.
_TOOL_CALL_RE = re.compile(r"mcp__ppt-generator__(\w+)\(([^)]*)\)")


def _registered_tools() -> dict[str, set[str]]:
    """@mcp.tool() 로 등록된 도구명 → 파라미터 이름 집합."""
    tools: dict[str, set[str]] = {}
    for path in _CONTROLLERS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_tool = any(
                isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") == "tool"
                for dec in node.decorator_list
            )
            if not is_tool:
                continue
            args = node.args
            names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
            names.discard("ctx")
            tools[node.name] = names
    return tools


def _skill_files() -> list[Path]:
    return sorted(_SKILLS_DIR.glob("*/SKILL.md"))


def test_controllers_and_skills_are_discoverable() -> None:
    """탐색 자체가 조용히 0건이 되면 이 파일의 모든 검증이 무력해진다."""
    assert _CONTROLLERS, "controller.py 를 찾지 못했다"
    assert _skill_files(), "SKILL.md 를 찾지 못했다"
    assert _registered_tools(), "@mcp.tool() 등록 도구를 찾지 못했다"


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_tool_names_exist(skill_path: Path) -> None:
    """스킬이 언급하는 mcp__ppt-generator__* 도구가 실제로 등록돼 있어야 한다."""
    tools = _registered_tools()
    referenced = set(_TOOL_CALL_RE.findall(skill_path.read_text(encoding="utf-8")))
    unknown = sorted(name for name, _ in referenced if name not in tools)
    assert not unknown, f"{skill_path.parent.name}: 존재하지 않는 도구 {unknown}"


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_skill_tool_parameter_names_match(skill_path: Path) -> None:
    """스킬이 적은 파라미터명이 실제 시그니처에 있어야 한다.

    `import_pptx(pptx_path, ...)` 처럼 존재하지 않는 이름을 적어두면 사용자가
    named argument 로 호출할 때 실패한다.
    """
    tools = _registered_tools()
    text = skill_path.read_text(encoding="utf-8")
    problems: list[str] = []

    for tool_name, raw_args in _TOOL_CALL_RE.findall(text):
        if tool_name not in tools:
            continue  # 위 테스트가 따로 잡는다
        for chunk in raw_args.split(","):
            token = chunk.strip().split("=")[0].strip()
            # 식별자 형태만 파라미터 후보로 본다 (리터럴·생략기호·산문 제외)
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", token):
                continue
            if token not in tools[tool_name]:
                problems.append(
                    f"{tool_name}(...): '{token}' 없음 → {sorted(tools[tool_name])}"
                )

    assert not problems, f"{skill_path.parent.name}: " + "; ".join(problems)


def test_secondary_harness_docs_reference_skills_instead_of_copying() -> None:
    """Kiro steering·Codex 안내는 스킬을 *가리키고* 절차를 복제하지 않는다.

    절차를 복제하면 한쪽만 갱신돼 지침이 엇갈린다 (실제로 lint 처리 방침이
    스킬과 steering 사이에서 갈렸던 적이 있다). 복제 지표로 도구명 등장 횟수를
    쓴다 — 단계별 도구 호출을 나열하기 시작하면 이 테스트가 걸린다.
    """
    steering = _REPO_ROOT / ".kiro" / "steering" / "ppt-generator.md"
    text = steering.read_text(encoding="utf-8")

    tool_mentions = re.findall(r"\b(?:prepare|ingest)_[a-z_]+", text)
    assert not tool_mentions, (
        f"steering 이 도구 호출을 복제하고 있다: {sorted(set(tool_mentions))}. "
        "절차는 skills/ 를 참조하게 두라"
    )

    # 참조가 실제 스킬을 가리켜야 한다 (경로가 죽으면 안내가 무의미해진다).
    referenced = set(re.findall(r"skills/(ppt-[a-z-]+)/SKILL\.md", text))
    assert referenced, "steering 이 어떤 스킬도 가리키지 않는다"
    existing = {p.parent.name for p in _skill_files()}
    assert referenced <= existing, (
        f"존재하지 않는 스킬 참조: {sorted(referenced - existing)}"
    )


def test_skill_frontmatter_name_matches_directory() -> None:
    """스킬 디렉토리명과 frontmatter name 이 다르면 호출 이름이 헷갈린다."""
    for skill_path in _skill_files():
        head = skill_path.read_text(encoding="utf-8").split("---")[1]
        declared = re.search(r"^name:\s*(\S+)", head, re.M)
        assert declared, f"{skill_path.parent.name}: frontmatter 에 name 이 없다"
        assert declared.group(1) == skill_path.parent.name
