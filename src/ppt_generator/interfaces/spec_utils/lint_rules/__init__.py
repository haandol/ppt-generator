"""Lint 규칙 모음. 각 규칙은 (spec, result) → None 시그니처의 함수.

결정 13a — `ALL_RULES` 는 layer 그룹으로 정렬되어 있다 (layout →
section → cross → content). lint_slide_spec(stop_on_layer_error=True) 가
layer 별 단계적 검증을 수행할 수 있도록 `RULES_BY_LAYER` 도 함께 노출한다.
"""

from ppt_generator.interfaces.spec_utils.lint_rules.arrow_endpoint_attachment import (
    check_arrow_endpoint_attachment,
)
from ppt_generator.interfaces.spec_utils.lint_rules.canvas_overflow import (
    check_canvas_overflow,
)
from ppt_generator.interfaces.spec_utils.lint_rules.component_id_link import (
    check_component_id_link,
)
from ppt_generator.interfaces.spec_utils.lint_rules.decoration_shape_overlap import (
    check_decoration_shape_overlap,
)
from ppt_generator.interfaces.spec_utils.lint_rules.edge_alignment import (
    check_edge_alignment,
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
from ppt_generator.interfaces.spec_utils.lint_rules.grid_section_link import (
    check_grid_section_link,
)
from ppt_generator.interfaces.spec_utils.lint_rules.hidden_decorative_strip import (
    check_hidden_decorative_strip,
)
from ppt_generator.interfaces.spec_utils.lint_rules.label_orphan import (
    check_label_orphan,
)
from ppt_generator.interfaces.spec_utils.lint_rules.layout_tree_bbox import (
    check_layout_tree_bbox,
)
from ppt_generator.interfaces.spec_utils.lint_rules.nowrap_overflow import (
    check_nowrap_overflow,
)
from ppt_generator.interfaces.spec_utils.lint_rules.region_stacking import (
    check_region_stacking,
)
from ppt_generator.interfaces.spec_utils.lint_rules.row_autofit_consistency import (
    check_row_autofit_consistency,
)
from ppt_generator.interfaces.spec_utils.lint_rules.section_element_bbox import (
    check_section_element_bbox,
)
from ppt_generator.interfaces.spec_utils.lint_rules.section_grid_containment import (
    check_section_grid_containment,
)
from ppt_generator.interfaces.spec_utils.lint_rules.sibling_gap import (
    check_sibling_gap,
)
from ppt_generator.interfaces.spec_utils.lint_rules.spacer_paragraph import (
    check_spacer_paragraph,
)
from ppt_generator.interfaces.spec_utils.lint_rules.sibling_grid import (
    check_sibling_grid,
)
from ppt_generator.interfaces.spec_utils.lint_rules.text_overflow import (
    check_text_overflow,
)
from ppt_generator.interfaces.spec_utils.lint_rules.textbox_shape_intrusion import (
    check_textbox_shape_intrusion,
)
from ppt_generator.interfaces.spec_utils.lint_rules.textbox_textbox_overlap import (
    check_textbox_textbox_overlap,
)
from ppt_generator.interfaces.spec_utils.lint_rules.title_font import (
    check_title_font,
)
from ppt_generator.interfaces.spec_utils.lint_rules.zero_size_shape import (
    check_zero_size_shape,
)

# 결정 13a — layer 그룹 순서로 정렬. layer 별 단계적 lint 호출 시
# fail-stop 가 의미 있도록 layout(거시) → section → cross → content(미시) 순.
RULES_BY_LAYER: dict[str, list] = {
    "layout": [
        check_grid_plan_required,
        check_grid_cell_coverage,
        check_region_stacking,
    ],
    "section": [
        check_layout_tree_bbox,
    ],
    "cross": [
        check_grid_section_link,
        check_component_id_link,
        check_section_element_bbox,
        check_section_grid_containment,
        check_arrow_endpoint_attachment,
        check_label_orphan,
        check_textbox_shape_intrusion,
        check_textbox_textbox_overlap,
        check_decoration_shape_overlap,
        check_sibling_gap,
        check_sibling_grid,
    ],
    "content": [
        check_title_font,
        check_font_range,
        check_canvas_overflow,
        check_text_overflow,
        check_nowrap_overflow,
        check_expand_height_collision,
        check_zero_size_shape,
        check_decorative_no_rounding,
        check_hidden_decorative_strip,
        check_row_autofit_consistency,
        check_spacer_paragraph,
        check_edge_alignment,
    ],
}

# 평탄화된 전체 규칙 — 기존 호출자(`for rule in ALL_RULES`) 호환.
ALL_RULES = [
    rule
    for layer in ("layout", "section", "cross", "content")
    for rule in RULES_BY_LAYER[layer]
]

__all__ = ["ALL_RULES", "RULES_BY_LAYER"]
