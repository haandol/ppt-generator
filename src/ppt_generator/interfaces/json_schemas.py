"""Structured Output용 JSON 스키마 정의."""

from ppt_generator.interfaces.output_models.outline import OutlineOutput

OUTLINE_JSON_SCHEMA = OutlineOutput.model_json_schema()
