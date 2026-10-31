"""덱 전체 디자인 의도와 테마 응답."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DesignRegionOutput(BaseModel):
    """덱 전체가 공유하는 세로 영역."""

    model_config = ConfigDict(extra="forbid")

    top_px: float = Field(ge=0)
    height_px: float = Field(gt=0)


class DesignThemeOutput(BaseModel):
    """DESIGN.md 초안의 수치 디자인 시스템."""

    model_config = ConfigDict(extra="forbid")

    background_color: str
    background_image: Literal["gradient", "none"] = "gradient"
    text_colors: list[str]
    title_font_pt: int = Field(ge=28, le=36)
    body_font_pt: int = Field(ge=16, le=22)
    card_fills: list[str]
    card_borders: list[str]
    header_region: DesignRegionOutput
    content_region: DesignRegionOutput
    footer_region: DesignRegionOutput

    @model_validator(mode="after")
    def validate_region_order(self) -> "DesignThemeOutput":
        header_bottom = self.header_region.top_px + self.header_region.height_px
        content_bottom = self.content_region.top_px + self.content_region.height_px
        footer_bottom = self.footer_region.top_px + self.footer_region.height_px
        if header_bottom > self.content_region.top_px:
            raise ValueError("header_region overlaps content_region")
        if content_bottom > self.footer_region.top_px:
            raise ValueError("content_region overlaps footer_region")
        if footer_bottom > 688:
            raise ValueError("footer_region exceeds the 688px safe area")
        return self


class DesignPageRequestOutput(BaseModel):
    """특정 슬라이드에만 적용할 디자인 요청."""

    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    title: str = Field(min_length=1)
    request: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_nonblank_request(self) -> "DesignPageRequestOutput":
        """빈 요청은 거부하되 바인딩 키인 원본 제목을 변경하지 않는다."""
        if not self.title.strip() or not self.request.strip():
            raise ValueError("page request title and request must not be blank")
        return self


class AntiSlopGuardrailsOutput(BaseModel):
    """DESIGN.md에 저장되는 덱별 AI Slop 방지 기준."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject_specificity: str = Field(min_length=1)
    visual_hierarchy: str = Field(min_length=1)
    layout_rhythm: str = Field(min_length=1)
    decoration_policy: str = Field(min_length=1)
    content_grounding: str = Field(min_length=1)
    max_consecutive_same_archetype: Literal[2] = Field(
        default=2,
        description="Legacy client field. Repetition is reviewed for purpose, not prohibited.",
    )


class DesignDocDraftOutput(BaseModel):
    """DESIGN.md 초안 생성 단계의 전체 출력."""

    model_config = ConfigDict(extra="forbid")

    theme: DesignThemeOutput
    tone: str
    anti_slop: AntiSlopGuardrailsOutput
    page_requests: list[DesignPageRequestOutput]
