"""grid-plan-required: content 슬라이드의 grid_plan 필수성 검사.

ADR-0044: design 단계 산출물은 element 좌표를 채우기 전에 grid_plan 을 먼저
결정해야 한다. content slide_type 슬라이드에서 grid_plan 누락, content region
누락, content_columns 가 1~4 범위 밖이면 error 로 보고한다.

title/closing 슬라이드는 fixed special layout 이므로 grid_plan 부재가 정상이며
검사를 skip 한다.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

_MIN_COLUMNS = 1
_MAX_COLUMNS = 4


def check_grid_plan_required(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    if spec.slide_type != "content":
        return

    plan = spec.grid_plan
    if plan is None:
        result.violations.append(
            LintViolation(
                rule="grid-plan-required",
                severity="error",
                message=(
                    "content 슬라이드에 grid_plan 이 누락됨. "
                    "designer 가 textbox/shape 좌표를 채우기 전에 "
                    "grid_plan(regions/content_columns/cells) 을 먼저 출력해야 한다."
                ),
                element_index=-1,
                element_type="slide",
                current_value=None,
                expected="grid_plan 필수 (regions 에 'content' 포함)",
            )
        )
        return

    if "content" not in plan.regions:
        result.violations.append(
            LintViolation(
                rule="grid-plan-required",
                severity="error",
                message=(
                    "grid_plan.regions 에 'content' 가 없음. content 영역은 "
                    "모든 슬라이드의 필수 구획이다."
                ),
                element_index=-1,
                element_type="slide",
                current_value={"regions": list(plan.regions)},
                expected="regions 에 'content' 포함",
            )
        )

    if not (_MIN_COLUMNS <= plan.content_columns <= _MAX_COLUMNS):
        result.violations.append(
            LintViolation(
                rule="grid-plan-required",
                severity="error",
                message=(
                    f"content_columns={plan.content_columns} 는 허용 범위 밖 (1~4)."
                ),
                element_index=-1,
                element_type="slide",
                current_value={"content_columns": plan.content_columns},
                expected="content_columns 는 1~4 범위",
            )
        )

    if plan.content_rows < 1:
        result.violations.append(
            LintViolation(
                rule="grid-plan-required",
                severity="error",
                message=f"content_rows={plan.content_rows} 는 1 이상이어야 한다.",
                element_index=-1,
                element_type="slide",
                current_value={"content_rows": plan.content_rows},
                expected="content_rows >= 1",
            )
        )

    valid_regions = {"header", "content", "footer"}
    bad_regions = [r for r in plan.regions if r not in valid_regions]
    if bad_regions:
        result.violations.append(
            LintViolation(
                rule="grid-plan-required",
                severity="error",
                message=(
                    f"grid_plan.regions 에 알 수 없는 항목 {bad_regions}. "
                    f"허용 값: header/content/footer."
                ),
                element_index=-1,
                element_type="slide",
                current_value={"regions": list(plan.regions)},
                expected="regions 항목은 header/content/footer 중 하나",
            )
        )

    declared_regions = set(plan.regions)
    bad_cell_regions = [c.id for c in plan.cells if c.region not in declared_regions]
    if bad_cell_regions:
        result.violations.append(
            LintViolation(
                rule="grid-plan-required",
                severity="error",
                message=(
                    f"grid_plan.cells 중 {bad_cell_regions} 의 region 이 "
                    f"regions 목록에 선언되지 않음."
                ),
                element_index=-1,
                element_type="slide",
                current_value={
                    "cells": [{"id": c.id, "region": c.region} for c in plan.cells]
                },
                expected="모든 cell.region 은 regions 목록에 포함되어야 한다",
            )
        )
