"""프롬프트 상수 모듈.

.prompt.md 파일에서 프롬프트를 로딩하여 상수로 제공한다.
"""

import json
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    """프롬프트 파일을 읽어 앞뒤 공백을 제거한 문자열로 반환한다."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def _load_content_prompt() -> str:
    """content 프롬프트의 예시 블록을 검증 대상 정식 예시 하나로 교체한다."""
    prompt = _load("design_system_content.prompt.md")
    example = json.loads(
        (_PROMPTS_DIR / "examples" / "two_column_diagram.json").read_text(
            encoding="utf-8"
        )
    )
    example.pop("_comment", None)
    example_json = json.dumps(example, ensure_ascii=False, indent=2)
    examples = (
        '<examples>\n  <layout_example id="two-column-diagram" '
        'hint="two-column diagram with complete hierarchy">\n'
        f"{example_json}\n"
        "  </layout_example>\n</examples>"
    )
    start = prompt.index("<examples>")
    end = prompt.index("</examples>", start) + len("</examples>")
    return prompt[:start] + examples + prompt[end:]


OUTLINE_SYSTEM_PROMPT = _load("outline_system.prompt.md")
OUTLINE_USER_PROMPT_TEMPLATE = _load("outline_user.prompt.md")

# slide_type별 분리된 시스템 프롬프트 (공통 베이스 + 타입별 오버라이드)
_DESIGN_SYSTEM_BASE = _load("design_system_base.prompt.md")

DESIGN_SPEC_SYSTEM_PROMPTS: dict[str, str] = {
    "content": _DESIGN_SYSTEM_BASE + "\n\n" + _load_content_prompt(),
    "title": _DESIGN_SYSTEM_BASE + "\n\n" + _load("design_system_title.prompt.md"),
    "closing": _DESIGN_SYSTEM_BASE + "\n\n" + _load("design_system_closing.prompt.md"),
}

# 하위 호환용 (design_summary 생성 등에서 사용)
DESIGN_SPEC_SYSTEM_PROMPT = DESIGN_SPEC_SYSTEM_PROMPTS["content"]

DESIGN_SPEC_USER_PROMPT_TEMPLATE = _load("design_user.prompt.md")
DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE = _load("design_batch_user.prompt.md")
DESIGN_SUMMARY_USER_PROMPT_TEMPLATE = _load("design_summary_user.prompt.md")
DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE = _load("design_doc_draft_user.prompt.md")

VISUAL_QA_ANALYSIS_SYSTEM_PROMPT = _load("visual_qa_analysis.prompt.md")
VISUAL_QA_FIX_SYSTEM_PROMPT = _load("visual_qa_fix.prompt.md")

DESIGN_REVIEW_SYSTEM_PROMPT = _load("design_review.prompt.md")

# component-level partial modification
COMPONENT_MODIFY_SYSTEM_PROMPT = _load("component_modify_system.prompt.md")
COMPONENT_MODIFY_USER_PROMPT_TEMPLATE = _load("component_modify_user.prompt.md")

# imported slide design_doc lazy backfill
BACKFILL_DESIGN_DOC_SYSTEM_PROMPT = _load("backfill_design_doc_system.prompt.md")
BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE = _load("backfill_design_doc_user.prompt.md")

__all__ = [
    "DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE",
    "DESIGN_SPEC_SYSTEM_PROMPT",
    "DESIGN_SPEC_SYSTEM_PROMPTS",
    "DESIGN_SPEC_USER_PROMPT_TEMPLATE",
    "DESIGN_SUMMARY_USER_PROMPT_TEMPLATE",
    "DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE",
    "OUTLINE_SYSTEM_PROMPT",
    "OUTLINE_USER_PROMPT_TEMPLATE",
    "VISUAL_QA_ANALYSIS_SYSTEM_PROMPT",
    "VISUAL_QA_FIX_SYSTEM_PROMPT",
    "DESIGN_REVIEW_SYSTEM_PROMPT",
    "COMPONENT_MODIFY_SYSTEM_PROMPT",
    "COMPONENT_MODIFY_USER_PROMPT_TEMPLATE",
    "BACKFILL_DESIGN_DOC_SYSTEM_PROMPT",
    "BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE",
]
