<task>
Generate PptxSlideSpec JSON based on the following slide outline.
Use the shared design intent for palette and semantic roles. Refine the proposed
composition while preserving the message and explicit user-fixed constraints.
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
Use the slide-type response_schema. For content, provide a complete grid_layout,
cell_assignment and design_doc with valid links for meaningful elements. Decorative-only
links may be omitted as described in the system contract. The server derives node bboxes.
Copy existing speaker_notes verbatim or use an empty string. Final script writing belongs
to ppt-speaker-script after design; layout descriptions belong in design_doc.
</output_requirements>
