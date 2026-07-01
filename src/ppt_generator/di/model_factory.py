"""LLM 모델 생성 팩토리.

Bedrock/Anthropic 프로바이더별 모델 인스턴스 생성 로직을 담당한다.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from botocore.config import Config as BotocoreConfig
from strands.models.bedrock import BedrockModel

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
)


# ---- Static helpers ----


def build_client_config() -> BotocoreConfig:
    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        return BotocoreConfig(
            auth_scheme_preference="httpBearerAuth,sigv4",
            read_timeout=300,
            connect_timeout=60,
        )
    return BotocoreConfig(read_timeout=300, connect_timeout=60)


def build_anthropic_client_args() -> dict[str, Any]:
    return {"timeout": httpx.Timeout(connect=5.0, read=300.0, write=300.0, pool=300.0)}


# ---- Bedrock model creators ----


def create_bedrock_design_model(effort: str = "medium") -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_DESIGN_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        max_tokens=BEDROCK_DESIGN_MAX_TOKENS,
        additional_request_fields={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        },
    )


def create_bedrock_outline_model(
    max_tokens: int,
    effort: str = "medium",
) -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_OUTLINE_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        max_tokens=max_tokens,
        additional_request_fields={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        },
    )


# ---- Anthropic model creators ----


def create_anthropic_design_model(effort: str = "medium") -> Any:
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_DESIGN_MODEL_ID,
        max_tokens=BEDROCK_DESIGN_MAX_TOKENS,
        params={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        },
    )


def create_anthropic_outline_model(
    max_tokens: int,
    effort: str = "medium",
) -> Any:
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_OUTLINE_MODEL_ID,
        max_tokens=max_tokens,
        params={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        },
    )


# ---- Design review model creators (no extended thinking) ----


def create_bedrock_review_model() -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_DESIGN_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        max_tokens=BEDROCK_REVIEW_MAX_TOKENS,
        additional_request_fields={
            "thinking": {"type": "disabled"},
        },
    )


def create_anthropic_review_model() -> Any:
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_DESIGN_MODEL_ID,
        max_tokens=BEDROCK_REVIEW_MAX_TOKENS,
        params={"thinking": {"type": "disabled"}},
    )


# ---- Visual QA model creators ----


def create_bedrock_visual_qa_model() -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_DESIGN_MODEL_ID,
        region_name=BEDROCK_REGION,
        boto_client_config=build_client_config(),
        max_tokens=BEDROCK_VISUAL_QA_FIX_MAX_TOKENS,
        additional_request_fields={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "low"},
        },
    )


def create_anthropic_visual_qa_model() -> Any:
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_DESIGN_MODEL_ID,
        max_tokens=BEDROCK_VISUAL_QA_FIX_MAX_TOKENS,
        params={
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "low"},
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
    )


def create_anthropic_visual_qa_analysis_model() -> Any:
    """Haiku 기반 Visual QA 분석 모델 (이슈 감지 전용)."""
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args=build_anthropic_client_args(),
        model_id=ANTHROPIC_VISUAL_QA_ANALYSIS_MODEL_ID,
        max_tokens=BEDROCK_VISUAL_QA_ANALYSIS_MAX_TOKENS,
        params={"temperature": 1.0},
    )
