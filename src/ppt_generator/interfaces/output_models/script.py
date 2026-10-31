"""발표 대본 응답과 슬라이드 식별자 검증."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SpeakerScriptSlideOutput(BaseModel):
    """클라이언트가 작성한 슬라이드별 낭독 대본."""

    model_config = ConfigDict(extra="forbid", strict=True)

    slide_index: int = Field(ge=1)
    speaker_notes: str


class SpeakerScriptOutput(BaseModel):
    """화면 구성과 분리된 덱 전체 대본."""

    model_config = ConfigDict(extra="forbid", strict=True)

    scripts: list[SpeakerScriptSlideOutput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_slides(self) -> "SpeakerScriptOutput":
        """중복 번호로 다른 슬라이드의 노트를 덮어쓰지 않는다."""
        indices = [script.slide_index for script in self.scripts]
        if len(indices) != len(set(indices)):
            raise ValueError("speaker script slide indices must be unique")
        return self
