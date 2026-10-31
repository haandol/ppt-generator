"""편집 요청 검증 실패의 공통 로깅."""

from __future__ import annotations

import logging
from typing import NoReturn

logger = logging.getLogger(__name__)


def _raise_validation(tool: str, msg: str, **context: object) -> NoReturn:
    """입력 검증 실패를 로깅하고 ValueError 를 raise."""
    ctx_str = " ".join(f"{k}={v!r}" for k, v in context.items() if v is not None)
    logger.error("%s validation failed: %s | %s", tool, msg, ctx_str)
    raise ValueError(msg)
