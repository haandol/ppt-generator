"""region-stacking: footer 사용 시 content 영역 침범 검사.

footer region 이 grid_plan.regions 에 포함된 슬라이드에서, content
cell 에 매핑된 element 의 bottom 이 footer region top 을 침범하면 안 된다.

design_summary 의 region 픽셀 범위는 dict 로 관리되어 lint 시점에 직접 접근이
어렵기 때문에, 의 기본값(footer top=664)을 기준으로 검사한다. 향후
lint 호출 측에서 design_summary 의 footer_region 을 주입하면 그 값을 우선
사용하도록 확장 가능.
"""

from __future__ import annotations

from ppt_generator.interfaces.schemas import PptxSlideSpec
from ppt_generator.interfaces.spec_utils.lint_types import (
    LintViolation,
    SlideLintResult,
)

# design_summary 가 정의하지 않은 경우의 기본값. design_summary_user.prompt.md 와 일치.
_DEFAULT_FOOTER_TOP_PX = 664.0
_REQUIRED_GAP_PX = 16.0


def check_region_stacking(spec: PptxSlideSpec, result: SlideLintResult) -> None:
    plan = spec.grid_plan
    if plan is None:
        return
    if "footer" not in plan.regions:
        return

    footer_top = _DEFAULT_FOOTER_TOP_PX
    content_max = footer_top - _REQUIRED_GAP_PX

    content_cell_ids = {c.id for c in plan.cells if c.region == "content"}
    if not content_cell_ids:
        return

    for idx, tb in enumerate(spec.textboxes):
        if tb.grid_cell not in content_cell_ids:
            continue
        bottom = tb.top_px + abs(tb.height_px)
        if bottom > content_max + 0.5:
            result.violations.append(
                LintViolation(
                    rule="region-stacking",
                    severity="error",
                    message=(
                        f"textbox[{idx}] (cell '{tb.grid_cell}') 의 bottom={bottom:.0f} "
                        f"이 footer 영역(top={footer_top:.0f}) 을 침범 "
                        f"(허용 한계 {content_max:.0f})."
                    ),
                    element_index=idx,
                    element_type="textbox",
                    current_value={"bottom": bottom, "footer_top": footer_top},
                    expected=(
                        f"content cell bottom <= {content_max:.0f} "
                        f"(footer top - {_REQUIRED_GAP_PX:.0f}px)"
                    ),
                )
            )

    for idx, sh in enumerate(spec.shapes):
        if sh.grid_cell not in content_cell_ids:
            continue
        bottom = sh.top_px + abs(sh.height_px)
        if bottom > content_max + 0.5:
            result.violations.append(
                LintViolation(
                    rule="region-stacking",
                    severity="error",
                    message=(
                        f"shape[{idx}] (cell '{sh.grid_cell}') 의 bottom={bottom:.0f} "
                        f"이 footer 영역(top={footer_top:.0f}) 을 침범 "
                        f"(허용 한계 {content_max:.0f})."
                    ),
                    element_index=idx,
                    element_type="shape",
                    current_value={"bottom": bottom, "footer_top": footer_top},
                    expected=(
                        f"content cell bottom <= {content_max:.0f} "
                        f"(footer top - {_REQUIRED_GAP_PX:.0f}px)"
                    ),
                )
            )
