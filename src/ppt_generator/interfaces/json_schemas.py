"""Structured Output용 JSON 스키마 정의."""

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
                    "slide_type": {
                        "type": "string",
                        "enum": ["title", "closing", "content"],
                    },
                    "layout_plan": {"type": "string"},
                    "speaker_notes": {"type": "string"},
                },
                "required": [
                    "title",
                    "content_summary",
                    "component_hint",
                    "slide_type",
                    "layout_plan",
                    "speaker_notes",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["slides"],
    "additionalProperties": False,
}
