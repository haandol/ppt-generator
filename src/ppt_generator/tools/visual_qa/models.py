"""Visual QA 결과 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SlideQAResult:
    """단일 슬라이드의 QA 결과."""

    slide_index: int
    status: str  # "pass", "fixed", "unfixed", "error"
    issues_found: list[str] = field(default_factory=list)
    iterations: int = 0


@dataclass
class VisualQAResult:
    """전체 Visual QA 실행 결과."""

    slides_analyzed: int = 0
    slides_with_issues: int = 0
    slides_fixed: int = 0
    iterations_used: int = 0
    screenshots_dir: str = ""
    per_slide: list[SlideQAResult] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0
