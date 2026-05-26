<task>
Generate PptxSlideSpec JSON based on the following slide outline.
You must maintain the same design theme as the previous slides.
{slide_type_instruction}
</task>

<context>
Slide position: {slide_index} of {total_slides}
Color theme: {color_theme}
</context>

<design_summary>
{design_summary}
</design_summary>
{adjacent_context}
<input>
{outline_json}
</input>

<output_requirements>
If this is a content slide, follow the five-layer hierarchy strictly (ADR-0049):
1. **Layout** — output `grid_layout` (regions / content_columns / content_rows) FIRST, then `cell_assignment.cells` (id / region / row / col / span / role). Declare every cell BEFORE any element.
2. **Section** — output `design_doc` with `topic`, `layout_summary`, and `layout` (flat list of LayoutNode with `parent_id` references). Each section/group/component carries its bbox (`left_px`, `top_px`, `width_px`, `height_px`). Sibling bboxes must not overlap; child bboxes must fit inside parent.
3. **Content** — output `textboxes` / `shapes`, each referencing a cell via `grid_cell` AND a leaf component node via `component_id`.

The response schema requires `grid_layout`, `cell_assignment`, and `design_doc` for content slides; omitting any will fail validation.

`speaker_notes` is the actual presenter narrative (1-3 short paragraphs, audience-facing tone). Do NOT describe slide structure here — that belongs in `design_doc`.
</output_requirements>
