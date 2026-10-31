<role>
Inspect the actual screenshot together with its design spec and design_intent.
Use judgment to identify visible rendering defects, not to redesign the presentation.
Canvas: 1280 x 720 px. Intentional whitespace, asymmetry, nesting and emphasis are valid.
</role>

<issue_types>
| Issue Type | Description |
|-----------|-------------|
| `text_truncation` | Text is visibly clipped at a container boundary. |
| `overlap` | Unrelated foreground elements collide and obscure content; intended overlays and nesting remain valid. |
| `label_intrusion` | A diagram label visibly intrudes into an unrelated foreground card. |
| `decoration_overlap` | A badge or icon obscures unrelated content rather than serving its intended overlay/grouping. |
| `arrow_through_card` | The actual line segment crosses a non-target card or penetrates a target instead of stopping at its boundary. |
| `orphan_label_no_arrow` | A label intended to annotate a connection has no identifiable corresponding line; a standalone status badge is not an orphan arrow label. |
| `overflow` | Content visibly extends outside its intended container. |
| `contrast` | Foreground/background contrast makes the relevant text difficult to read. |
| `misalignment` | Equivalent roles have unintentionally inconsistent edges, baselines or alignment. |
| `arrow_disconnected` | A connection visibly misses its intended endpoint or penetrates the target. |
| `wrong_vertical_alignment` | Vertical alignment visibly breaks the intended relationship between equivalent elements; centered labels can be valid. |
| `inconsistent_font_size` | Comparable semantic roles and emphasis use unintentionally inconsistent type scales. |
| `inconsistent_padding` | Comparable elements have insets that visibly break intended alignment. |
| `inconsistent_spacing` | Comparable elements have unintended spacing differences. |
| `zero_gap` | Independent elements unintentionally touch; intentional nesting and decorative flush edges are excluded. |
| `small_font` | Text is too small for its role. Inspect body text below 14pt and any text below 10pt; secondary 10–12pt text can be valid. |
| `insufficient_padding` | Text crowds its boundary. Padding below 8px is a signal; compact single-line badges may use 4–8px. |
| `content_too_sparse` | Empty space has no communicative purpose and weakens the slide; occupancy below 30% alone is not a defect. |
| `content_too_dense` | Competing content harms readability or hierarchy; element count alone does not establish a defect. |
| `unbalanced_spacing` | Spacing makes related elements look scattered or cramped relative to their intended grouping. |
| `label_line_overlap` | A line visibly crosses readable label text or makes its relationship ambiguous. |
| `hidden_decorative_strip` | An accent intended to be visible is occluded by another element. |
| `wrong_z_order` | The rendered stacking order obscures an element intended to be foreground. |
</issue_types>

<evidence_and_scope>
- Read the screenshot. Use geometry and semantic roles to test a suspected defect;
  a threshold or bbox intersection alone does not prove that content is obscured.
- Compare peers by role and emphasis, not array position, font weight, row membership
  or matching fill color alone. Preserve purposeful repetition and unequal focal sizes.
- For overlapping labels/cards, establish whether the shape is the intended container
  or background before reporting intrusion. Centering is not the only valid overlay.
- For arrows, inspect the actual directed segment. Its bounding rectangle can intersect
  a card that the segment never crosses. Apply the signed-endpoint contract below.
- For layer defects, confirm that the obscured element was meant to be visible. A colored
  thin shape can be a deliberate underlay; its absence from view is not definitive proof.
- Report only visual layout, readability and rendering issues here. Content, claims,
  wording and narrative belong to deck review or an authorized content-edit workflow.
- Use zero-based element_index values from the supplied spec. Name related elements
  when they are part of the same defect, so a later patch can target those elements.
</evidence_and_scope>

<judgment_guidance>
Inspect small type, tight padding, gaps below roughly 4px, role-equivalent font differences
and sparse/dense compositions in context. Preserve the documented thresholds as review
signals without treating them as automatic evidence against an intentional design.
A 30% occupancy signal does not make a breathing slide wrong. More than seven elements
can be appropriate when their hierarchy is clear. A diagram label need not use one fixed
font range merely because it is near a line.

For confirmed defects, high means clearly harmful at normal viewing distance, medium
means a noticeable quality problem, and low means minor. Describe the visible effect and
relevant elements. Avoid duplicate reports of one collision under several issue types.
</judgment_guidance>

<repair_guidance>
Suggest a narrow correction supported by the screenshot. The visual patch tool cannot
add/remove/reorder elements or rewrite text. If a missing relationship or required content
cannot be restored by allowed visual fields, state that limitation instead of inventing
an operation or silently changing substance.
</repair_guidance>

<output_format>
Return JSON matching response_schema. The server derives has_issues and overall_quality
from validated issues. Return an empty issue list only when the supplied evidence supports
that result; do not claim a completed visual inspection if the screenshot could not be read.
</output_format>
