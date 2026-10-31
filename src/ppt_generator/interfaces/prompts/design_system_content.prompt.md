<content_contract>
Content slides require grid_layout, cell_assignment and a non-empty design_doc.
These describe the final composition; they do not prescribe your reasoning order.

- grid_layout names the used regions and content columns/rows. The schema allows
  1..4 columns and positive rows. A grid column is not a limit on diagram node count:
  several nodes may share one cell, or cells may span rows/columns.
- Declare every referenced cell in cell_assignment. Cell row/column values are 1-based.
- design_doc provides topic, layout_summary and a flat layout list with parent_id links.
  Root nodes are sections; optional groups express meaningful substructures; components
  are leaves. Use groups when they clarify the subject or later editing, without a fixed
  component-count or depth quota. Parents precede children; ids are unique.
- Every meaningful textbox/shape has a grid_cell and a component_id referencing a
  declared cell and exactly one component leaf. Each leaf maps to exactly one element.
  Decorative-only connectors/background fills may omit those links.
- Do not put coordinates on layout nodes. The server derives each leaf bbox from its
  element and each parent bbox from its children. A parent bbox is a derived result,
  not a second independent set of coordinates to maintain.
</content_contract>

<quality_guidance>
Choose hierarchy and density for this message and the supplied design intent.
Intentional asymmetric emphasis is allowed.

- A header at left=64, top=72, width=1152, height=48 is one default, not a fixed recipe.
- Card titles around 18–24pt, card bodies around 16–20pt and labels around 14–18pt
  are useful starting points. Adjust for role and viewing conditions, keeping text
  legible; inspect the font-size review findings rather than shrinking to fit blindly.
- Start with roughly 16px between independent elements and suitable interior padding.
  Keep intentional overlays, nesting and decorative flush edges when they aid meaning.
- Repeated peers often benefit from consistent type, insets and spacing. Compare only
  elements with the same role and emphasis; do not normalize a focal element away.
- Use whitespace intentionally. Element counts and occupied-area percentages are
  inspection signals, not quotas or reasons to add decoration or remove required content.
- When a footer is used, leave it clear of the body. Region bands come from design_summary;
  card heights and composition should follow actual text and relationships.
</quality_guidance>

<composition_choices>
component_hint is a starting category; layout_plan and DESIGN.md carry the actual intent.
A plain list is appropriate for independent points. A diagram is useful when relationships
or a sequence need explaining. Comparisons may use aligned text, rows, cards or another
readable structure. A pipeline need not always run left-to-right; a concept explanation
need not always use two columns. Use custom when the provided hints do not describe the plan.
Agenda slides summarize body sections rather than listing every slide.
</composition_choices>

<diagram_guidance>
- Apply the shared signed-endpoint contract for every direction. The arrowhead identifies
  the destination, including a return edge. Avoid unrelated cards and readable labels.
- In a real cycle, mark the containing layout group with role="cycle_diagram"; its direct
  children identify participating nodes. Preserve the source's order and relationships.
- Fan-out/fan-in can use a bus when separate diagonals become cluttered. Do not invent
  connections merely to justify a diagram or force a bus when another route is clearer.
- Place labels where their relationship is apparent. A status badge need not annotate
  an arrow; do not create one unless the content describes a connection.
</diagram_guidance>

<final_response>
Return only the JSON required by response_schema. Check role/cell links, units, arrow
endpoints and content preservation. Use lint and rendered evidence to resolve remaining
visual uncertainty; do not replace a valid intentional layout merely to eliminate warnings.
</final_response>
