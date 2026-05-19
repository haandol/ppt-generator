<task>
Generate PptxSlideSpec JSON based on the following slide outline.
The outline's layout_plan describes the spatial arrangement — follow it precisely for element count and direction.
{slide_type_instruction}
</task>

<context>
Slide position: {slide_index} of {total_slides}
Color theme: {color_theme}
</context>
{adjacent_context}
<input>
{outline_json}
</input>

<output_requirements>
If this is a content slide, follow the four-stage descent strictly:
1. Output `grid_layout` (regions / content_columns / content_rows) FIRST.
2. Then `cell_assignment.cells` (id / region / row / col / span / role) — declare every cell BEFORE any element.
3. Only then `textboxes` / `shapes`, each referencing a declared cell via `grid_cell`.
The response schema requires `grid_layout` and `cell_assignment` for content slides; omitting either will fail validation.
</output_requirements>
