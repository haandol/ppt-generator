"""프롬프트 상수 모듈.

.prompt.md 파일에서 프롬프트를 로딩하여 상수로 제공한다.
"""

import json
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    """프롬프트 파일을 읽어 앞뒤 공백을 제거한 문자열로 반환한다."""
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def _load_content_prompt(*, include_example: bool = False) -> str:
    """본문 계약에 현재 구성과 관련된 검증된 예시만 선택적으로 붙인다."""
    prompt = _load("design_system_content.prompt.md")
    if not include_example:
        return prompt
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
    return prompt + "\n\n" + examples


OUTLINE_SYSTEM_PROMPT = _load("outline_system.prompt.md")
OUTLINE_USER_PROMPT_TEMPLATE = _load("outline_user.prompt.md")
SPEAKER_SCRIPT_SYSTEM_PROMPT = _load("speaker_script_system.prompt.md")

# slide_type별 분리된 시스템 프롬프트 (공통 베이스 + 타입별 오버라이드)
_LINE_GEOMETRY = _load("line_geometry.prompt.md")
_LINE_GEOMETRY += (
    "\n\nThese numerical examples illustrate endpoint encoding, not a required layout."
    "\n<line_examples>\n"
    + json.dumps(json.loads(_load("examples/line_directions.json")), indent=2)
    + "\n</line_examples>"
)
_DESIGN_SYSTEM_BASE = _load("design_system_base.prompt.md") + "\n\n" + _LINE_GEOMETRY

DESIGN_SPEC_SYSTEM_PROMPTS: dict[str, str] = {
    "content": _DESIGN_SYSTEM_BASE + "\n\n" + _load_content_prompt(),
    "title": _DESIGN_SYSTEM_BASE + "\n\n" + _load("design_system_title.prompt.md"),
    "closing": _DESIGN_SYSTEM_BASE + "\n\n" + _load("design_system_closing.prompt.md"),
}


def get_design_spec_system_prompt(slide_type: str, component_hint: str = "") -> str:
    """현재 슬라이드에 관련된 guidance와 예시만 조립한다."""
    if slide_type != "content":
        return DESIGN_SPEC_SYSTEM_PROMPTS.get(
            slide_type, DESIGN_SPEC_SYSTEM_PROMPTS["content"]
        )
    needs_example = component_hint == "two_column"
    return (
        _DESIGN_SYSTEM_BASE
        + "\n\n"
        + _load_content_prompt(include_example=needs_example)
    )


# 하위 호환용 (design_summary 생성 등에서 사용)
DESIGN_SPEC_SYSTEM_PROMPT = DESIGN_SPEC_SYSTEM_PROMPTS["content"]

DESIGN_SPEC_USER_PROMPT_TEMPLATE = _load("design_user.prompt.md")
DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE = _load("design_batch_user.prompt.md")
# 기존 import 호환성. 현재 도구는 DESIGN.md 초안 또는 결정론적 요약을 사용한다.
DESIGN_SUMMARY_USER_PROMPT_TEMPLATE = _load("design_summary_user.prompt.md")
DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE = _load("design_doc_draft_user.prompt.md")
DESIGN_DOC_DRAFT_SYSTEM_PROMPT = _load("design_doc_draft_system.prompt.md")

VISUAL_QA_ANALYSIS_SYSTEM_PROMPT = (
    _load("visual_qa_analysis.prompt.md") + "\n\n" + _LINE_GEOMETRY
)
VISUAL_QA_FIX_SYSTEM_PROMPT = _load("visual_qa_fix.prompt.md") + "\n\n" + _LINE_GEOMETRY

DESIGN_REVIEW_SYSTEM_PROMPT = _load("design_review.prompt.md")
DECK_REVIEW_SYSTEM_PROMPT = _load("deck_review.prompt.md")

# component-level partial modification
COMPONENT_MODIFY_SYSTEM_PROMPT = (
    _load("component_modify_system.prompt.md") + "\n\n" + _LINE_GEOMETRY
)
COMPONENT_MODIFY_USER_PROMPT_TEMPLATE = _load("component_modify_user.prompt.md")

# imported slide design_doc lazy backfill
BACKFILL_DESIGN_DOC_SYSTEM_PROMPT = _load("backfill_design_doc_system.prompt.md")
BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE = _load("backfill_design_doc_user.prompt.md")

__all__ = [
    "DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE",
    "DESIGN_SPEC_SYSTEM_PROMPT",
    "DESIGN_SPEC_SYSTEM_PROMPTS",
    "get_design_spec_system_prompt",
    "DESIGN_SPEC_USER_PROMPT_TEMPLATE",
    "DESIGN_SUMMARY_USER_PROMPT_TEMPLATE",
    "DESIGN_DOC_DRAFT_USER_PROMPT_TEMPLATE",
    "DESIGN_DOC_DRAFT_SYSTEM_PROMPT",
    "OUTLINE_SYSTEM_PROMPT",
    "OUTLINE_USER_PROMPT_TEMPLATE",
    "SPEAKER_SCRIPT_SYSTEM_PROMPT",
    "VISUAL_QA_ANALYSIS_SYSTEM_PROMPT",
    "VISUAL_QA_FIX_SYSTEM_PROMPT",
    "DESIGN_REVIEW_SYSTEM_PROMPT",
    "DECK_REVIEW_SYSTEM_PROMPT",
    "COMPONENT_MODIFY_SYSTEM_PROMPT",
    "COMPONENT_MODIFY_USER_PROMPT_TEMPLATE",
    "BACKFILL_DESIGN_DOC_SYSTEM_PROMPT",
    "BACKFILL_DESIGN_DOC_USER_PROMPT_TEMPLATE",
]
