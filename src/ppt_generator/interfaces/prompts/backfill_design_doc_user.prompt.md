<task>
Recover the existing slide's semantic tree without changing any element.
Describe an optional grid only when the source layout supports it; do not reshape the
slide to manufacture one. Use the returned response_schema for fields and types.
</task>
<context>
Canvas: 1280 x 720 px (origin top-left).
Slide index: {slide_index}
</context>
<elements>
{elements_json}
</elements>
<output_requirements>
Use unique nodes and valid parent_id/element_ref links. Every textbox and non-decorative
shape maps exactly once to a component leaf. Keep descriptions and ids meaningful.
Do not emit node coordinates; the server derives them from the original element bboxes.
</output_requirements>
