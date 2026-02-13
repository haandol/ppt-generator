from pathlib import Path

PPT_GENERATOR_HOME = Path.home() / ".ppt-generator"

BEDROCK_MODEL_ID = "us.anthropic.claude-opus-4-6-v1"
BEDROCK_OUTLINE_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_REGION = "us-east-1"
BEDROCK_TEMPERATURE = 0.7
BEDROCK_MAX_TOKENS = 32_000
BEDROCK_OUTLINE_MAX_TOKENS = 16_000
BEDROCK_SCRIPT_MAX_TOKENS = 16_000

DEFAULT_NUM_SLIDES = 5
MIN_NUM_SLIDES = 3
MAX_NUM_SLIDES = 20

# --- Bedrock Structured Output JSON Schemas ---

OUTLINE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content_summary": {"type": "string"},
                    "component_hint": {"type": "string"},
                },
                "required": ["title", "content_summary", "component_hint"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["slides"],
    "additionalProperties": False,
}

SCRIPT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "scripts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slide_index": {"type": "integer"},
                    "speaker_notes": {"type": "string"},
                },
                "required": ["slide_index", "speaker_notes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["scripts"],
    "additionalProperties": False,
}

# --- PPTX 수치 상수 ---

PPTX_SLIDE_WIDTH_EMU = 12_192_000   # 13.333" x 914400
PPTX_SLIDE_HEIGHT_EMU = 6_858_000   # 7.5" x 914400
PPTX_FONT_NAME = "맑은 고딕"
PPTX_MONOSPACE_FONT_NAME = "Consolas"
PPTX_BODY_FONT_SIZE_PT = 16
PPTX_TITLE_FONT_SIZE_PT = 28

PPTX_BULLET_CHAR_L0 = "\u2022"
PPTX_BULLET_MARGIN_EMU_L0 = 228600    # ~0.25in
PPTX_BULLET_INDENT_EMU_L0 = -171450
PPTX_BULLET_MARGIN_EMU_L1 = 457200    # ~0.5in
PPTX_BULLET_INDENT_EMU_L1 = -171450

SLIDES_WIDTH_PX = 1280
SLIDES_HEIGHT_PX = 720

PPTX_VALIDATE_FONT_MIN_PT = 10
PPTX_VALIDATE_FONT_MAX_PT = 44
PPTX_VALIDATE_LINE_HEIGHT_FACTOR = 1.5

EXPORT_PX_TO_INCHES_X = 13.333 / 1280  # ~0.01042
EXPORT_PX_TO_INCHES_Y = 7.5 / 720      # ~0.01042

PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU = 45720   # ~0.05 inch
PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU = 22860   # ~0.025 inch
PX_TO_EMU = 9525                            # 914400 / 96

SLIDES_TEMPLATE_PATH = Path(__file__).parent.parent / \
    "templates" / "slides.html"

SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 720
SLIDE_FOOTER_HEIGHT = 48

# --- 프롬프트 상수 (prompts 모듈에서 re-export) ---

from ppt_generator.interfaces.prompts import (  # noqa: E402
    DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE,
    DESIGN_SPEC_DESIGN_SUMMARY_PROMPT,
    DESIGN_SPEC_SYSTEM_PROMPT,
    DESIGN_SPEC_USER_PROMPT_TEMPLATE,
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_USER_PROMPT_TEMPLATE,
    SCRIPT_SYSTEM_PROMPT,
    SCRIPT_USER_PROMPT_TEMPLATE,
)

__all__ = [
    # Model/Bedrock settings
    "BEDROCK_MODEL_ID", "BEDROCK_OUTLINE_MODEL_ID", "BEDROCK_REGION",
    "BEDROCK_TEMPERATURE", "BEDROCK_MAX_TOKENS", "BEDROCK_OUTLINE_MAX_TOKENS",
    "BEDROCK_SCRIPT_MAX_TOKENS",
    # Numeric constants
    "DEFAULT_NUM_SLIDES", "MIN_NUM_SLIDES", "MAX_NUM_SLIDES",
    "PPTX_SLIDE_WIDTH_EMU", "PPTX_SLIDE_HEIGHT_EMU", "PPTX_FONT_NAME", "PPTX_MONOSPACE_FONT_NAME",
    "PPTX_BODY_FONT_SIZE_PT", "PPTX_TITLE_FONT_SIZE_PT",
    "PPTX_BULLET_CHAR_L0", "PPTX_BULLET_MARGIN_EMU_L0", "PPTX_BULLET_INDENT_EMU_L0",
    "PPTX_BULLET_MARGIN_EMU_L1", "PPTX_BULLET_INDENT_EMU_L1",
    "SLIDES_WIDTH_PX", "SLIDES_HEIGHT_PX",
    "PPTX_SHAPE_DEFAULT_MARGIN_LR_EMU", "PPTX_SHAPE_DEFAULT_MARGIN_TB_EMU", "PX_TO_EMU",
    "PPTX_VALIDATE_FONT_MIN_PT", "PPTX_VALIDATE_FONT_MAX_PT", "PPTX_VALIDATE_LINE_HEIGHT_FACTOR",
    "EXPORT_PX_TO_INCHES_X", "EXPORT_PX_TO_INCHES_Y",
    "SLIDES_TEMPLATE_PATH", "SLIDE_WIDTH", "SLIDE_HEIGHT", "SLIDE_FOOTER_HEIGHT",
    # JSON schemas
    "OUTLINE_JSON_SCHEMA", "SCRIPT_JSON_SCHEMA",
    # Prompts (re-exported from prompts module)
    "DESIGN_SPEC_BATCH_USER_PROMPT_TEMPLATE", "DESIGN_SPEC_DESIGN_SUMMARY_PROMPT",
    "DESIGN_SPEC_SYSTEM_PROMPT", "DESIGN_SPEC_USER_PROMPT_TEMPLATE",
    "OUTLINE_SYSTEM_PROMPT", "OUTLINE_USER_PROMPT_TEMPLATE",
    "SCRIPT_SYSTEM_PROMPT", "SCRIPT_USER_PROMPT_TEMPLATE",
    # Paths
    "PPT_GENERATOR_HOME",
]
