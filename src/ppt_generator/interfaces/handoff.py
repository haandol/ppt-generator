"""클라이언트 LLM 오프로딩용 prepare/ingest 핸드셰이크 헬퍼.

서버는 LLM 을 직접 호출하지 않는다. 대신 각 생성 단계를 두 도구로 나눈다:

- ``prepare_*`` — 서버가 조립한 system/user 프롬프트와 출력 JSON 스키마를
  반환한다 (부작용 없음, 결정론적 준비만 허용).
- ``ingest_*`` — 클라이언트가 스키마대로 생성해 돌려준 JSON 을 서버가
  검증·후처리·저장한다.

이 모듈은 prepare 응답의 공통 봉투(envelope)를 만드는 헬퍼만 제공한다.
프롬프트 텍스트·스키마·후처리 로직은 각 도구가 그대로 소유한다.
"""

from __future__ import annotations

from typing import Any


def build_llm_task(
    *,
    system_prompt: str,
    user_prompt: str,
    response_schema: dict[str, Any] | None = None,
    images: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """클라이언트가 생성을 수행하는 데 필요한 정보를 담은 dict 를 만든다.

    Args:
        system_prompt: 서버가 조립한 시스템 프롬프트.
        user_prompt: 서버가 조립한 사용자 프롬프트.
        response_schema: 클라이언트가 따라야 할 출력 JSON 스키마
            (Pydantic ``model_json_schema()`` 결과). 자유형 JSON 이면 None.
        images: 비전 태스크용 입력 이미지 파일 경로 목록 (예: 스크린샷).
        **extra: ingest 단계와 상관(correlate)하기 위한 식별자
            (project_id, slide_index, component_id 등).

    Returns:
        prepare 도구가 JSON 으로 직렬화해 반환할 dict.
    """
    task: dict[str, Any] = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }
    if response_schema is not None:
        task["response_schema"] = response_schema
    if images:
        task["images"] = images
    task.update(extra)
    return task
