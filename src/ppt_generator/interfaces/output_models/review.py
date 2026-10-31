"""슬라이드·덱 검토 응답과 심각도 정합성 검증."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DesignReviewIssue(BaseModel):
    """Design review에서 발견된 개별 이슈."""

    rule_id: Literal[
        "font_size_floor",
        "lr_font_consistency",
        "vstack_overlap",
        "vstack_height_uniformity",
        "vstack_gap_uniformity",
        "lr_bottom_alignment",
        "same_level_overlap",
        "peer_font_consistency",
        "peer_padding_consistency",
    ]
    severity: Literal["high", "medium"]
    description: str

    @model_validator(mode="after")
    def validate_rule_severity(self) -> "DesignReviewIssue":
        allowed: dict[str, set[str]] = {
            "font_size_floor": {"high"},
            "lr_font_consistency": {"high", "medium"},
            "vstack_overlap": {"high"},
            "vstack_height_uniformity": {"medium"},
            "vstack_gap_uniformity": {"medium"},
            "lr_bottom_alignment": {"medium"},
            "same_level_overlap": {"high"},
            "peer_font_consistency": {"high", "medium"},
            "peer_padding_consistency": {"medium"},
        }
        if self.severity not in allowed[self.rule_id]:
            raise ValueError(f"{self.rule_id} does not allow severity {self.severity}")
        return self


class DesignReviewOutput(BaseModel):
    """Design spec 리뷰 결과."""

    has_high_severity: bool
    issues: list[DesignReviewIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_high_severity(self) -> "DesignReviewOutput":
        """검증된 issue 목록에서 high-severity 여부를 계산한다."""
        self.has_high_severity = any(issue.severity == "high" for issue in self.issues)
        return self


class DeckReviewIssue(BaseModel):
    """덱 전체의 근거·서사·반복 문제."""

    issue_type: Literal[
        "unsupported_claim",
        "narrative_gap",
        "duplicate_content",
        "terminology_drift",
        "agenda_mismatch",
        "conclusion_mismatch",
        "time_density",
    ]
    severity: Literal["high", "medium"]
    slide_indices: list[int] = Field(min_length=1)
    description: str
    suggested_action: str

    @model_validator(mode="after")
    def validate_slide_indices(self) -> "DeckReviewIssue":
        if any(index < 1 for index in self.slide_indices):
            raise ValueError("deck review slide_indices must be 1-based")
        if len(set(self.slide_indices)) != len(self.slide_indices):
            raise ValueError("deck review slide_indices must be unique")
        return self


class DeckReviewOutput(BaseModel):
    """덱 전체 read-only review 응답."""

    has_high_severity: bool
    issues: list[DeckReviewIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def derive_high_severity(self) -> "DeckReviewOutput":
        self.has_high_severity = any(issue.severity == "high" for issue in self.issues)
        return self
