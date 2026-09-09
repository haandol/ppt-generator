<task>
Generate PptxSlideSpec JSON based on the following slide outline.
Use the outline's layout_plan as the default intent. Preserve its message and essential
relationships; exact element counts and directions are binding only when explicitly fixed by the user.
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
Use these design_summary region values as consistent starting bands.
</design_summary>
{adjacent_context}
<input>
{outline_json}
</input>

<output_requirements>
If this is a content slide, follow the five-layer hierarchy strictly:
1. **Layout** — include `grid_layout` and `cell_assignment.cells` (id / region / row / col / span / role), declaring every referenced cell in the final response.
2. **Section** — output `design_doc` with non-empty `topic`, `layout_summary`, and semantic `layout` nodes with `parent_id` references. Do not output node coordinates; the server derives them from linked Content elements.
3. **Content** — output `textboxes` / `shapes`, each referencing a cell via `grid_cell` AND a leaf component node via `component_id`.

The response schema requires `grid_layout`, `cell_assignment`, and `design_doc` for content slides; omitting any will fail validation.

`speaker_notes` is the actual presenter narrative (1-3 short paragraphs, audience-facing tone). Do NOT describe slide structure here — that belongs in `design_doc`. Layout node coordinates are server-derived from the linked elements.
</output_requirements>
