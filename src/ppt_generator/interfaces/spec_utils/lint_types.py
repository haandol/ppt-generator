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
    # "layout" | "section" | "content" | "cross"
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
#
# 결정 8 (전수 분류): lint_rules/ 의 모든 규칙을 명시적으로 분류한다. 신규 규칙
# 추가 시 이 표에 entry 를 빠뜨리면 test_lint_layer_coverage 가 실패한다.
#
# 분류 가이드:
# - "layout":  grid_plan(regions/columns/rows/cells) 위반
# - "section": design_doc.layout 트리 bbox/구조 위반
# - "content": 단일 textbox/shape 의 텍스트·픽셀·스타일 위반
# - "cross":   계층 간 link 또는 복수 element 간 관계 위반 (component_id↔leaf,
#              label↔arrow 부착 등)
RULE_LAYER_MAP: dict[str, str] = {
    # Layout layer — grid_plan 격자
    "grid-plan-required": "layout",
    "grid-cell-uniformity": "layout",
    "grid-cell-coverage": "layout",
    "region-stacking": "layout",
    # Section layer — design_doc.layout 트리 bbox
    "layout-tree-sibling-overlap": "section",
    "layout-tree-containment": "section",
    "layout-tree-bbox-missing": "section",
    "layout-tree-canvas-overflow": "section",
    # Cross layer — element 간 관계 / 계층 간 link
    "arrow-endpoint-attachment": "cross",  # arrow 끝점 ↔ target shape 부착
    "label-orphan": "cross",  # label textbox ↔ 인접 shape 매칭
    "decoration-shape-overlap": "cross",  # 장식 ↔ 콘텐츠 shape 겹침
    "textbox-shape-intrusion": "cross",  # textbox 가 다른 shape 를 침범
    "textbox-textbox-overlap": "cross",  # textbox ↔ textbox 겹침
    "sibling-gap-minimum": "cross",  # 형제 element 간 간격
    "sibling-grid-uniformity": "cross",  # 형제 element 간 크기 균일성
    # Cross layer — Section ↔ Content link 정합성 (ADR-0049 결정 12)
    "component-id-link-orphan-element": "cross",
    "component-id-link-orphan-leaf": "cross",
    "component-id-link-ambiguous": "cross",
    # Cross layer — Layout ↔ Section / Section ↔ Content (ADR-0049 결정 13)
    "grid-section-link-orphan-cell": "cross",
    "section-element-bbox-mismatch": "cross",
    "element-out-of-section": "cross",  # 결정 13g
    "element-out-of-grid-cell": "cross",  # 결정 13g
    # Content layer — 슬라이드 외곽 정렬 (ADR-0049 결정 13f)
    "slide-edge-alignment-left": "content",
    "slide-edge-alignment-right": "content",
    "slide-edge-alignment-top": "content",
    "slide-edge-alignment-bottom": "content",
    # Content layer — 단일 textbox/shape 의 텍스트·스타일·픽셀 위반
    "title-font-min": "content",
    "font-range": "content",
    "text-overflow": "content",
    "text-width-overflow": "content",
    "nowrap-overflow": "content",
    "expand-height-collision": "content",
    "row-autofit-mismatch": "content",
    "row-expand-height-unsafe": "content",
    "spacer-paragraph": "content",
    "decorative-no-rounding": "content",
    "hidden-decorative-strip": "content",
    "zero-size-shape": "content",
    "canvas-overflow": "content",
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
