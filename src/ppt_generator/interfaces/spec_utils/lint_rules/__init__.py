"""Lint 규칙 모음. 각 규칙은 (spec, result) → None 시그니처의 함수."""

from ppt_generator.interfaces.spec_utils.lint_rules.canvas_overflow import (
    check_canvas_overflow,
)
from ppt_generator.interfaces.spec_utils.lint_rules.decorative_no_rounding import (
    check_decorative_no_rounding,
)
from ppt_generator.interfaces.spec_utils.lint_rules.expand_height_collision import (
    check_expand_height_collision,
)
from ppt_generator.interfaces.spec_utils.lint_rules.font_range import (
    check_font_range,
)
from ppt_generator.interfaces.spec_utils.lint_rules.grid_cell_coverage import (
    check_grid_cell_coverage,
)
from ppt_generator.interfaces.spec_utils.lint_rules.grid_plan_required import (
    check_grid_plan_required,
)
from ppt_generator.interfaces.spec_utils.lint_rules.region_stacking import (
    check_region_stacking,
)
from ppt_generator.interfaces.spec_utils.lint_rules.sibling_gap import (
    check_sibling_gap,
)
from ppt_generator.interfaces.spec_utils.lint_rules.sibling_grid import (
    check_sibling_grid,
)
from ppt_generator.interfaces.spec_utils.lint_rules.text_overflow import (
    check_text_overflow,
)
from ppt_generator.interfaces.spec_utils.lint_rules.title_font import (
    check_title_font,
)
from ppt_generator.interfaces.spec_utils.lint_rules.zero_size_shape import (
    check_zero_size_shape,
)

ALL_RULES = [
    check_title_font,
    check_font_range,
    check_canvas_overflow,
    check_text_overflow,
    check_expand_height_collision,
    check_sibling_gap,
    check_sibling_grid,
    check_zero_size_shape,
    check_decorative_no_rounding,
    check_grid_plan_required,
    check_grid_cell_coverage,
    check_region_stacking,
]

__all__ = ["ALL_RULES"]
