"""Lint 데이터 클래스 및 공유 헬퍼."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ppt_generator.interfaces.schemas import PptxSlideSpec


@dataclass(frozen=True)
class LintViolation:
    rule: str
    severity: str  # "error" | "warning"
    message: str
    element_index: int  # -1 일 때 슬라이드 전체 위반
    element_type: str  # "textbox" | "shape" | "slide"
    current_value: Any = None
    expected: str = ""


@dataclass
class SlideLintResult:
    slide_index: int  # 1-based
    violations: list[LintViolation] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    def to_dict(self) -> dict:
        if not self.violations:
            return {"slide_index": self.slide_index, "status": "pass"}
        return {
            "slide_index": self.slide_index,
            "status": "fail",
            "violation_count": len(self.violations),
            "violations": [
                {
                    "rule": v.rule,
                    "severity": v.severity,
                    "message": v.message,
                    "element_type": v.element_type,
                    "element_index": v.element_index,
                }
                for v in self.violations
            ],
        }


@dataclass
class LintResult:
    slides: list[SlideLintResult] = field(default_factory=list)
    cleaned_specs: list[PptxSlideSpec] = field(default_factory=list)

    @property
    def total_violations(self) -> int:
        return sum(len(s.violations) for s in self.slides)

    @property
    def has_violations(self) -> bool:
        return self.total_violations > 0

    def to_dict(self) -> dict:
        failed = [s for s in self.slides if s.has_violations]
        return {
            "total_slides": len(self.slides),
            "total_violations": self.total_violations,
            "failed_slides": len(failed),
            "passed_slides": len(self.slides) - len(failed),
            "per_slide": [s.to_dict() for s in self.slides if s.has_violations],
        }


def is_decorative(shape) -> bool:
    """장식 요소 판별: 텍스트 없는 얇은 shape."""
    has_text = bool(shape.text and shape.text.strip())
    if not has_text and shape.paragraphs:
        has_text = any(
            run.text.strip() for para in shape.paragraphs for run in para.runs
        )
    is_thin = abs(shape.height_px) <= 10 or abs(shape.width_px) <= 10
    return not has_text and is_thin
