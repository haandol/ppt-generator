"""LLM 모델 생성 팩토리.

Bedrock/Anthropic 프로바이더별 모델 인스턴스 생성 로직을 담당한다.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx
from botocore.config import Config as BotocoreConfig
from strands.models.bedrock import BedrockModel, CacheConfig
from strands.types.content import Messages
from strands.types.tools import ToolChoice, ToolSpec

from ppt_generator.interfaces.constants import (
    ANTHROPIC_DESIGN_MODEL_ID,
    ANTHROPIC_OUTLINE_MODEL_ID,
    ANTHROPIC_VISUAL_QA_ANALYSIS_MODEL_ID,
    BEDROCK_DESIGN_MAX_TOKENS,
    BEDROCK_DESIGN_MODEL_ID,
    BEDROCK_OUTLINE_MODEL_ID,
    BEDROCK_REGION,
    BEDROCK_REVIEW_MAX_TOKENS,
    BEDROCK_VISUAL_QA_ANALYSIS_MAX_TOKENS,
    BEDROCK_VISUAL_QA_ANALYSIS_MODEL_ID,
    BEDROCK_VISUAL_QA_FIX_MAX_TOKENS,
    VISUAL_QA_ANALYSIS_SYSTEM_PROMPT,
    VISUAL_QA_FIX_SYSTEM_PROMPT,
)


class CachingAnthropicModel:
    """AnthropicModel 서브클래스: system_prompt에 cache_control을 적용.

    Anthropic API는 system 필드를 content block 리스트로 받을 때
    cache_control: {"type": "ephemeral"}을 지정하면 prompt caching이 활성화된다.
    """

    def __new__(cls, **kwargs: Any) -> Any:
        from strands.models.anthropic import AnthropicModel

        class _CachingAnthropicModel(AnthropicModel):
            def format_request(
                self,
                messages: Messages,
                tool_specs: Optional[list[ToolSpec]] = None,
                system_prompt: Optional[str] = None,
                tool_choice: ToolChoice | None = None,
            ) -> dict[str, Any]:
                request = super().format_request(
                    messages, tool_specs, system_prompt, tool_choice
                )
                if system_prompt and "system" in request:
                    request["system"] = [
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        },
                    ]
                return request

        return _CachingAnthropicModel(**kwargs)


# ---- Static helpers ----


def build_client_config() -> BotocoreConfig:
    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        return BotocoreConfig(
            auth_scheme_preference="httpBearerAuth,sigv4",
            read_timeout=300,
            connect_timeout=60,
        )
    return BotocoreConfig(read_timeout=300, connect_timeout=60)


def build_json_schema_args(schema: dict, name: str) -> dict:
    return {
        "outputConfig": {
            "textFormat": {
                "type": "json_schema",
                "structure": {
                    "jsonSchema": {
                        "schema": json.dumps(schema),
                        "name": name,
                    },
                },
            },
        },
    }


def build_anthropic_client_args() -> dict[str, Any]:
    return {"timeout": httpx.Timeout(connect=5.0, read=300.0, write=300.0, pool=300.0)}


# ---- Bedrock model creators ----


def create_bedrock_design_model() -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_DESIGN_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        temperature=1.0,
        max_tokens=BEDROCK_DESIGN_MAX_TOKENS,
        cache_config=CacheConfig(strategy="auto"),
        additional_request_fields={
            "thinking": {"type": "adaptive"},
        },
    )


def create_bedrock_outline_model(
    max_tokens: int,
    json_schema: dict | None = None,
    json_schema_name: str | None = None,
) -> BedrockModel:
    additional_args: dict[str, Any] = {}
    if json_schema and json_schema_name:
        additional_args = build_json_schema_args(json_schema, json_schema_name)
    return BedrockModel(
        model_id=BEDROCK_OUTLINE_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        temperature=1.0,
        max_tokens=max_tokens,
        cache_config=CacheConfig(strategy="auto"),
        additional_args=additional_args,
        additional_request_fields={
            "thinking": {"type": "adaptive"},
        },
    )


# ---- Anthropic model creators ----


def create_anthropic_design_model() -> Any:
    return CachingAnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_DESIGN_MODEL_ID,
        max_tokens=BEDROCK_DESIGN_MAX_TOKENS,
        params={
            "temperature": 1.0,
            "thinking": {"type": "adaptive"},
        },
    )


def create_anthropic_outline_model(
    max_tokens: int,
    json_schema: dict | None = None,
    json_schema_name: str | None = None,
) -> Any:
    from strands.models.anthropic import AnthropicModel

    params: dict[str, Any] = {
        "temperature": 1.0,
        "thinking": {"type": "adaptive"},
    }
    if json_schema and json_schema_name:
        params.setdefault("output_config", {})["format"] = {
            "type": "json_schema",
            "schema": json_schema,
            "name": json_schema_name,
        }
    return AnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_OUTLINE_MODEL_ID,
        max_tokens=max_tokens,
        params=params,
    )


# ---- Design review model creators (no extended thinking) ----


def create_bedrock_review_model() -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_DESIGN_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        temperature=1.0,
        max_tokens=BEDROCK_REVIEW_MAX_TOKENS,
        cache_config=CacheConfig(strategy="auto"),
    )


def create_anthropic_review_model() -> Any:
    return CachingAnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_DESIGN_MODEL_ID,
        max_tokens=BEDROCK_REVIEW_MAX_TOKENS,
        params={"temperature": 1.0},
    )


# ---- Visual QA model creators ----


def create_bedrock_visual_qa_model() -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_DESIGN_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        temperature=1.0,
        max_tokens=BEDROCK_VISUAL_QA_FIX_MAX_TOKENS,
        cache_config=CacheConfig(strategy="auto"),
        additional_request_fields={
            "thinking": {"type": "adaptive"},
        },
    )


def create_anthropic_visual_qa_model() -> Any:
    return CachingAnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_DESIGN_MODEL_ID,
        max_tokens=BEDROCK_VISUAL_QA_FIX_MAX_TOKENS,
        params={
            "temperature": 1.0,
            "thinking": {"type": "adaptive"},
        },
    )


# ---- Visual QA analysis model creators (Haiku — lightweight classification) ----


def create_bedrock_visual_qa_analysis_model() -> BedrockModel:
    """Haiku 기반 Visual QA 분석 모델 (이슈 감지 전용)."""
    return BedrockModel(
        model_id=BEDROCK_VISUAL_QA_ANALYSIS_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        temperature=1.0,
        max_tokens=BEDROCK_VISUAL_QA_ANALYSIS_MAX_TOKENS,
        cache_config=CacheConfig(strategy="auto"),
    )


def create_anthropic_visual_qa_analysis_model() -> Any:
    """Haiku 기반 Visual QA 분석 모델 (이슈 감지 전용)."""
    return CachingAnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_VISUAL_QA_ANALYSIS_MODEL_ID,
        max_tokens=BEDROCK_VISUAL_QA_ANALYSIS_MAX_TOKENS,
        params={"temperature": 1.0},
    )
