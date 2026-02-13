"""프롬프트 상수 모듈."""

from ppt_generator.interfaces.prompts.design_prompts import (
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_SYSTEM_PROMPT,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.prompts.outline_prompts import (
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_USER_PROMPT_TEMPLATE,
)
from ppt_generator.interfaces.prompts.script_prompts import (
    SCRIPT_SYSTEM_PROMPT,
    SCRIPT_USER_PROMPT_TEMPLATE,
)

__all__ = [
    "DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE",
    "DESIGN_SPEC_SYSTEM_PROMPT",
    "DESIGN_SPEC_USER_PROMPT_TEMPLATE",
    "OUTLINE_SYSTEM_PROMPT",
    "OUTLINE_USER_PROMPT_TEMPLATE",
    "SCRIPT_SYSTEM_PROMPT",
    "SCRIPT_USER_PROMPT_TEMPLATE",
]
