"""응답 검증이 JSON과 Python 입력의 Pydantic 규칙을 그대로 적용하는지 검사한다."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from ppt_generator.interfaces.handoff import validate_llm_output


class StrictOutput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    day: date
    count: int


@pytest.mark.parametrize(
    "payload",
    [
        '{"day": "2026-10-31", "count": 2}',
        {"day": date(2026, 10, 31), "count": 2},
    ],
)
def test_typed_json_and_python_values_share_the_model(payload: str | dict) -> None:
    assert validate_llm_output(StrictOutput, payload) == StrictOutput(
        day=date(2026, 10, 31), count=2
    )


@pytest.mark.parametrize(
    ("payload", "error_type", "location"),
    [
        ({"day": "2026-10-31", "count": 2}, "date_type", ("day",)),
        ('{"day": "2026-10-31", "count": "2"}', "int_type", ("count",)),
        (
            '{"day": "2026-10-31", "count": 2, "extra": 1}',
            "extra_forbidden",
            ("extra",),
        ),
        ("{broken", "json_invalid", ()),
    ],
)
def test_validation_errors_keep_their_type_and_field_path(
    payload: str | dict, error_type: str, location: tuple[str, ...]
) -> None:
    with pytest.raises(ValidationError) as caught:
        validate_llm_output(StrictOutput, payload)
    error = caught.value.errors()[0]
    assert error["type"] == error_type
    assert error["loc"] == location
