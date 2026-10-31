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
If this is a content slide, follow the five-layer hierarchy strictly:
1. **Layout** — include `grid_layout` and `cell_assignment.cells` (id / region / row / col / span / role), declaring every referenced cell in the final response.
2. **Section** — output `design_doc` with non-empty `topic`, `layout_summary`, and
   semantic `layout` nodes. Do not output node coordinates; the server derives them from
   linked Content elements.
3. **Content** — output `textboxes` / `shapes`, each referencing a cell via `grid_cell` AND a leaf component node via `component_id`.

The response schema requires `grid_layout`, `cell_assignment`, and `design_doc` for content slides; omitting any will fail validation.

Copy existing `speaker_notes` verbatim, or use an empty string. Do not generate or refine the script here; the `ppt-speaker-script` skill writes it after design. Layout descriptions belong in `design_doc`.
</output_requirements>
