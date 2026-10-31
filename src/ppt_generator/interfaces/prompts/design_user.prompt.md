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
Use the slide-type response_schema. For content, provide a complete grid_layout,
cell_assignment and design_doc with valid links for meaningful elements. Decorative-only
links may be omitted as described in the system contract. The server derives node bboxes.
Copy existing speaker_notes verbatim or use an empty string. Final script writing belongs
to ppt-speaker-script after design; layout descriptions belong in design_doc.
</output_requirements>
