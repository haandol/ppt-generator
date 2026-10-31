"""시각 분석 응답과 허용된 수정 필드 검증."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .elements import ShapeOutput, TextBoxOutput
from .slides import ContentSlideSpecOutput, SimpleSlideSpecOutput


class VisualQAIssue(BaseModel):
    """Visual QA 분석에서 발견된 개별 이슈."""

    issue_type: Literal[
        "text_truncation",
        "overlap",
        "overflow",
        "contrast",
        "misalignment",
        "inconsistent_font_size",
        "inconsistent_spacing",
        "wrong_vertical_alignment",
        "arrow_disconnected",
        "zero_gap",
        "small_font",
        "insufficient_padding",
        "content_too_sparse",
        "content_too_dense",
        "unbalanced_spacing",
        "inconsistent_padding",
        "label_intrusion",
        "decoration_overlap",
        "arrow_through_card",
        "orphan_label_no_arrow",
        "label_line_overlap",
        "hidden_decorative_strip",
        "wrong_z_order",
    ]
    severity: Literal["high", "medium", "low"]
    element_type: Literal["textbox", "shape"]
    element_index: int = Field(ge=0)
    related_element_type: Literal["textbox", "shape"] | None = None
    related_element_index: int | None = Field(default=None, ge=0)
    description: str
    suggested_fix: str

    @model_validator(mode="after")
    def validate_related_element(self) -> "VisualQAIssue":
        if (self.related_element_type is None) != (self.related_element_index is None):
            raise ValueError(
                "related_element_type and related_element_index must be set together"
            )
        return self


class VisualQAOutput(BaseModel):
    """Visual QA 스크린샷 분석 결과."""

    has_issues: bool
    issues: list[VisualQAIssue] = Field(default_factory=list)
    overall_quality: Literal["good", "needs_improvement", "poor"]

    @model_validator(mode="after")
    def derive_summary(self) -> "VisualQAOutput":
        """이슈 목록을 정본으로 삼아 요약 필드를 정규화한다."""
        self.has_issues = bool(self.issues)
        if not self.issues:
            self.overall_quality = "good"
        elif any(issue.severity == "high" for issue in self.issues):
            self.overall_quality = "poor"
        else:
            self.overall_quality = "needs_improvement"
        return self


VisualQAPatchField = Literal[
    "left_px",
    "top_px",
    "width_px",
    "height_px",
    "padding_left_px",
    "padding_right_px",
    "padding_top_px",
    "padding_bottom_px",
    "line_spacing_pt",
    "vertical_alignment",
    "autofit",
    "autofit_mode",
    "fill_color",
    "border_color",
    "text_color",
    "text_size_pt",
    "z_index",
    "font_size_pt",
    "color",
    "background_color",
]


class VisualQAPatchOperation(BaseModel):
    """검증된 시각 이슈가 허용한 단일 replace operation."""

    model_config = ConfigDict(extra="forbid")

    element_type: Literal["slide", "textbox", "shape"]
    element_index: int = Field(default=-1, ge=-1)
    field: VisualQAPatchField
    value: str | float | int | bool | None
    paragraph_index: int | None = Field(default=None, ge=0)
    run_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "VisualQAPatchOperation":
        run_field = self.field in {"font_size_pt", "color"}
        if self.element_type == "slide":
            if self.element_index != -1 or self.field != "background_color":
                raise ValueError("slide patch only supports background_color")
            if self.paragraph_index is not None or self.run_index is not None:
                raise ValueError("slide patch cannot target a paragraph run")
        elif self.element_index < 0:
            raise ValueError("element patch requires element_index >= 0")
        if run_field:
            if self.paragraph_index is None or self.run_index is None:
                raise ValueError("run patch requires paragraph_index and run_index")
        elif self.paragraph_index is not None or self.run_index is not None:
            raise ValueError("element field patch cannot target a paragraph run")
        return self


class VisualQAFixPatchOutput(BaseModel):
    """Visual QA 수정 결과 — 전체 spec이 아닌 허용 필드 replace 목록."""

    model_config = ConfigDict(extra="forbid")

    operations: list[VisualQAPatchOperation] = Field(default_factory=list)


class VisualQATextBoxOutput(TextBoxOutput):
    """Visual QA에서만 렌더 순서 수정을 허용하는 텍스트박스."""

    z_index: int | None = None


class VisualQAShapeOutput(ShapeOutput):
    """Visual QA에서만 렌더 순서 수정을 허용하는 도형."""

    z_index: int | None = None


class VisualQAContentSlideSpecOutput(ContentSlideSpecOutput):
    """Visual QA용 content 응답 모델."""

    textboxes: list[VisualQATextBoxOutput] = Field(default_factory=list)
    shapes: list[VisualQAShapeOutput] = Field(default_factory=list)


class VisualQASimpleSlideSpecOutput(SimpleSlideSpecOutput):
    """Visual QA용 title/closing 응답 모델."""

    textboxes: list[VisualQATextBoxOutput] = Field(default_factory=list)
    shapes: list[VisualQAShapeOutput] = Field(default_factory=list)
