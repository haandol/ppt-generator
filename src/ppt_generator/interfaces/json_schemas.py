"""Bedrock Structured Output용 JSON 스키마 정의."""

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
                    "slide_type": {"type": "string", "enum": ["title", "closing", "content"]},
                },
                "required": ["title", "content_summary", "component_hint", "slide_type"],
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
