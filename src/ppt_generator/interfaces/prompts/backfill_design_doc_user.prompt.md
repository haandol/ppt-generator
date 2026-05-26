<task>
Build a `design_doc` tree for this imported slide. Do not modify any element —
only group them into sections/components.
</task>

<context>
Canvas: 1280 x 720 px (origin top-left).
Slide index: {slide_index}
</context>

<elements>
{elements_json}
</elements>

<reminders>
- Output `nodes` (flat list, parent_id references). No coordinates.
- Every non-decorative textbox/shape index must be referenced exactly once via
  `element_ref` from a component leaf.
- Keep ids stable, lower_snake_case, semantic.
- Use depth 2 by default; depth 3 only when a section has many components or a
  clear sub-system.
</reminders>
