"""review_design_spec 핸들러."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from ppt_generator.interfaces.constants import BEDROCK_DESIGN_MODEL_ID
from ppt_generator.interfaces.utils import (
    complexity_to_thinking_effort,
    estimate_cost,
    estimate_slide_complexity,
    format_token_usage,
    parse_outline_json,
)
from ppt_generator.tools.design.review_service import (
    DesignReviewService,
    merge_token_usage,
)

if TYPE_CHECKING:
    from ppt_generator.tools.design.handlers.deps import DesignDeps

logger = logging.getLogger(__name__)


def handle_review(
    deps: DesignDeps,
    *,
    project_id: str,
    slide_indices: str,
    auto_fix: bool,
    color_theme: str,
) -> str:
    """기존 디자인 스펙을 LLM 리뷰하고 선택적으로 재생성한다."""
    if deps.review_service_factory is None:
        raise ValueError("Review service is not configured.")

    project_service = deps.project_service
    _, project_dir = project_service.resolve_project_dir(project_id)
    slide_count = project_service.get_design_spec_slide_count(project_dir)

    # Parse slide_indices
    if slide_indices:
        indices = sorted(set(int(x.strip()) for x in slide_indices.split(",")))
        for idx in indices:
            if idx < 1 or idx > slide_count:
                raise ValueError(
                    f"Invalid slide_index: {idx} (valid range: 1-{slide_count})"
                )
    else:
        indices = list(range(1, slide_count + 1))

    design_summary = project_service.load_design_summary(project_dir)
    results: list[dict] = []
    total_usage: dict[str, int] = {}

    for slide_index in indices:
        idx = slide_index - 1
        spec = project_service.load_design_spec_slide(project_dir, idx)

        # Review
        review_svc = deps.review_service_factory()
        review_result = review_svc.review(spec, slide_index=slide_index)
        review_usage = review_svc.last_token_usage
        slide_usage = review_usage

        regenerated = False
        if auto_fix and review_result.has_high_severity:
            outline_json = project_service.load_outline_slide(project_dir, idx)
            slide_outline = parse_outline_json(outline_json).slides[0]

            feedback = DesignReviewService.format_feedback(review_result)

            complexity = estimate_slide_complexity(slide_outline)
            thinking_effort = complexity_to_thinking_effort(complexity)
            svc_regen = deps.design_service_factory(
                slide_outline.slide_type or "content",
                thinking_effort=thinking_effort,
            )
            new_spec = svc_regen.generate_single_slide(
                slide_outline,
                design_summary,
                color_theme=color_theme,
                review_feedback=feedback,
            )
            regen_usage = svc_regen.last_token_usage
            slide_usage = merge_token_usage(review_usage, regen_usage)

            # Restore images and slide_type from original spec (LLM cannot generate these)
            restore = {}
            if spec.images:
                restore["images"] = spec.images
            if spec.slide_type != "content":
                restore["slide_type"] = spec.slide_type
            if restore:
                new_spec = replace(new_spec, **restore)

            project_service.save_design_spec_slide(project_dir, idx, new_spec)
            project_service.renumber_design_spec_image_srcs(project_dir)
            if deps.slides_service is not None:
                html = deps.slides_service.render_single_slide_html(
                    idx,
                    new_spec,
                    color_theme=color_theme,
                )
                project_service.save_single_slide_html(project_dir, idx, html)
            regenerated = True
            logger.info(
                "slide[%d] review: high-severity issues found, regenerated", slide_index
            )
        else:
            logger.info(
                "slide[%d] review: %d issues (%s high)",
                slide_index,
                len(review_result.issues),
                "has" if review_result.has_high_severity else "no",
            )

        total_usage = (
            merge_token_usage(total_usage, slide_usage) if total_usage else slide_usage
        )

        results.append(
            {
                "slide_index": slide_index,
                "has_high_severity": review_result.has_high_severity,
                "issue_count": len(review_result.issues),
                "issues": [
                    {
                        "severity": i.severity,
                        "rule_id": i.rule_id,
                        "description": i.description,
                    }
                    for i in review_result.issues
                ],
                "regenerated": regenerated,
            }
        )

    resp: dict = {
        "project_id": project_id,
        "reviewed_count": len(results),
        "results": results,
    }
    if total_usage:
        resp["token_usage"] = format_token_usage(total_usage)
        resp["estimated_cost"] = estimate_cost(total_usage, BEDROCK_DESIGN_MODEL_ID)

    return json.dumps(resp, ensure_ascii=False)
