<task>
Generate PptxSlideSpec JSON based on the following slide outline.
The outline's layout_plan describes the spatial arrangement — follow it precisely for element count and direction.
{slide_type_instruction}
</task>

<context>
Slide position: {slide_index} of {total_slides}
Color theme: {color_theme}
</context>

<design_summary>
No presentation-level design summary exists for this deck yet, so use these default
region bands (identical to the draft defaults, so slides stay consistent if a summary
is added later):
- header_region: top_px=64, height_px=64
- content_region: top_px=148, height_px=508
- footer_region: top_px=664, height_px=24
Treat these as the design_summary region values — do NOT invent your own y-axis bands.
</design_summary>
{adjacent_context}
<input>
{outline_json}
</input>

<output_requirements>
If this is a content slide, follow the five-layer hierarchy strictly:
1. **Layout** — output `grid_layout` (regions / content_columns / content_rows) FIRST, then `cell_assignment.cells` (id / region / row / col / span / role). Declare every cell BEFORE any element.
2. **Section** — output `design_doc` with `topic`, `layout_summary`, and `layout` (flat list of LayoutNode with `parent_id` references). Each section/group/component carries its bbox (`left_px`, `top_px`, `width_px`, `height_px`). Sibling bboxes must not overlap; child bboxes must fit inside parent.
3. **Content** — output `textboxes` / `shapes`, each referencing a cell via `grid_cell` AND a leaf component node via `component_id`.

The response schema requires `grid_layout`, `cell_assignment`, and `design_doc` for content slides; omitting any will fail validation.

`speaker_notes` is the actual presenter narrative (1-3 short paragraphs, audience-facing tone). Do NOT describe slide structure here — that belongs in `design_doc`.
</output_requirements>
