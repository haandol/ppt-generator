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
