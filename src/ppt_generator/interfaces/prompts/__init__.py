"""프롬프트 상수 모듈.

.prompt.md 파일에서 프롬프트를 로딩하여 상수로 제공한다.
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    """프롬프트 파일을 읽어 앞뒤 공백을 제거한 문자열로 반환한다."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


OUTLINE_SYSTEM_PROMPT = _load("outline_system.prompt.md")
OUTLINE_USER_PROMPT_TEMPLATE = _load("outline_user.prompt.md")

SCRIPT_SYSTEM_PROMPT = _load("script_system.prompt.md")
SCRIPT_USER_PROMPT_TEMPLATE = _load("script_user.prompt.md")

DESIGN_SPEC_SYSTEM_PROMPT = _load("design_system.prompt.md")
DESIGN_SPEC_USER_PROMPT_TEMPLATE = _load("design_user.prompt.md")
DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE = _load("design_batch_user.prompt.md")
DESIGN_SUMMARY_USER_PROMPT_TEMPLATE = _load("design_summary_user.prompt.md")

__all__ = [
    "DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE",
    "DESIGN_SPEC_SYSTEM_PROMPT",
    "DESIGN_SPEC_USER_PROMPT_TEMPLATE",
    "DESIGN_SUMMARY_USER_PROMPT_TEMPLATE",
    "OUTLINE_SYSTEM_PROMPT",
    "OUTLINE_USER_PROMPT_TEMPLATE",
    "SCRIPT_SYSTEM_PROMPT",
    "SCRIPT_USER_PROMPT_TEMPLATE",
]
