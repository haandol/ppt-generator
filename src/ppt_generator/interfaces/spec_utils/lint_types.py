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
    # ADR-0049: 5단 계층 (Project / Slide / Layout / Section / Content / Cross).
    # "layout" = 격자 (grid_plan), "section" = design_doc.layout 트리 bbox/구조,
    # "content" = textbox/shape 의 텍스트·스타일·픽셀 충돌, "cross" = 계층 간 link.
    layer: str = "content"


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
        # layer 별 그룹화 — ADR-0049 5단 계층에 맞춰 어느 계층에서 위반이
        # 일어났는지 한 눈에 보이도록 정리.
        by_layer: dict[str, int] = {}
        for v in self.violations:
            by_layer[v.layer] = by_layer.get(v.layer, 0) + 1
        return {
            "slide_index": self.slide_index,
            "status": "fail",
            "violation_count": len(self.violations),
            "by_layer": by_layer,
            "violations": [
                {
                    "layer": v.layer,
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


# ADR-0049: rule → layer 매핑. lint rule 파일 자체는 layer 모르고, 검사 결과를
# 만들 때 이 표를 참조해 LintViolation.layer 를 결정한다.
RULE_LAYER_MAP: dict[str, str] = {
    # Layout layer — grid_plan 격자
    "title-font-min": "content",  # 격자 무관, 콘텐츠
    "grid-plan-required": "layout",
    "grid-cell-uniformity": "layout",
    "grid-cell-coverage": "layout",
    "region-stacking": "layout",
    # Section layer — design_doc.layout 트리 bbox
    "layout-tree-sibling-overlap": "section",
    "layout-tree-containment": "section",
    "layout-tree-bbox-missing": "section",
    "layout-tree-canvas-overflow": "section",
    # Content layer — 모든 픽셀/텍스트 위반
    # (명시 안 된 rule 은 default "content" 로 fallback)
}


def layer_for_rule(rule: str) -> str:
    return RULE_LAYER_MAP.get(rule, "content")


def is_decorative(shape) -> bool:
    """장식 요소 판별: 텍스트 없는 얇은 shape."""
    has_text = bool(shape.text and shape.text.strip())
    if not has_text and shape.paragraphs:
        has_text = any(
            run.text.strip() for para in shape.paragraphs for run in para.runs
        )
    is_thin = abs(shape.height_px) <= 10 or abs(shape.width_px) <= 10
    return not has_text and is_thin
