"""Structured Output용 JSON 스키마 정의."""

from ppt_generator.interfaces.llm_output_models import OutlineOutput

OUTLINE_JSON_SCHEMA = OutlineOutput.model_json_schema()
