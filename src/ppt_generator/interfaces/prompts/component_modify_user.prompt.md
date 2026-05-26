<task>
Apply a surgical modification to a single component on this slide.
Modify ONLY the element whose `component_id` matches `target_component_id`.
</task>

<context>
Slide index: {slide_index}
Color theme: {color_theme}
Target component_id: {target_component_id}
</context>

<slide_spec>
{slide_spec_json}
</slide_spec>

<instruction>
{instruction}
</instruction>

<reminders>
- Output exactly one element (textbox OR shape) matching `target_component_id`.
- Set `bbox_changed=true` only if you actually changed left/top/width/height.
- Preserve every field on the original element that the instruction did not ask to change.
- Do not output any other slide elements, design_doc nodes, or grid_plan.
</reminders>
