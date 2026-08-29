<quality_guidance>
The response schema and the cross-layer contracts in the base prompt are mandatory.
The following values are quality guidance: departures are allowed when they are
intentional, fit the outline, and keep the final result readable and lint-safe.

- Readable type usually means card titles >=18pt, card bodies >=16pt, section labels
  >=14pt, and other visible text between 10pt and 44pt.
- Prefer preserving readable type and placing genuinely excluded content in `overflow`
  instead of compressing every detail onto one slide.
- Prevent accidental same-level overlap. A 16px peer gap is a useful default, while
  intentional container-child nesting remains valid when children stay within the parent.
- Keep ordinary content inside the 1280x720 canvas and the design_summary regions.
  Decorative exceptions may cross a safe-area boundary when the renderer and lint permit it.
- Size text containers for likely wrapping and padding; use the font-metric lint result as
  feedback rather than treating a rough formula as an exact layout law.
- Choose `vertical_alignment` to support the composition. Repeated peer cards commonly use
  `top`; standalone banners often use `middle`.
- The default title bbox is left=64, top=72, width=1152, height=48, but DESIGN.md or an
  intentional composition may choose another bbox within the header region.
- Repeated rows and columns often benefit from consistent dimensions, typography, and
  padding. Intentional asymmetric emphasis is allowed.
</quality_guidance>

<typography_rules>
Recommended font size ranges:
- Slide title: 32~36pt, bold
- Subtitle/label: 14~18pt
- Body/description: 20~28pt
- Card title: 18~24pt, bold
- Card body: 16~20pt
- Secondary text (footnotes, source): 12~16pt
- Diagram flow label (text near arrows/lines): 12~14pt
- Code: font_family "monospace", 14~16pt
- Line spacing: body 24~28pt, bullet lists 26~32pt, card interior 20~24pt

Section label width: width_px >= char_count x font_size_pt x 1.2 (Korean) or x 0.73 (Latin).
</typography_rules>

<text_size_estimation>
- Korean char width ~ font_size_pt x 1.2px, Latin/number ~ font_size_pt x 0.73px
- Actual text width = width_px - padding_left - padding_right
- Required height = (lines x font_size_pt x 2.0) + padding_top + padding_bottom
- If estimated height exceeds available space, consider shortening text, enlarging the
  container, changing the layout, or putting genuinely excluded detail into overflow.
</text_size_estimation>

<padding_and_spacing>
Padding (shapes containing text):
- Useful starting point: left/right >= 16px, top/bottom >= 14px
- Recommended for cards: 20~28px horizontal, 16~24px vertical
- `height_px` should accommodate text, padding, and suitable breathing room

Spacing:
- Box-to-box gap: >= 16px
- Text-to-text gap (stacked blocks): >= 12px
- Title-to-body: >= 28px

Content density target: 40~75% of body area (148~688). If > 7 elements compete for space, simplify and put excess into overflow.
</padding_and_spacing>

<shapes_text_usage>
Two ways to add text to shapes:
1. Simple: text, text_color, text_size_pt, text_bold (single-line, auto center-aligned)
2. Structured: paragraphs array (multi-line, bullets, mixed formatting). Use font_family "monospace" for code.
If both are present, paragraphs takes priority. Use paragraphs for card-type shapes.
</shapes_text_usage>

<slide_type_agenda>
Agenda slide (component_hint: "agenda"):
- Commonly the second slide, listing major topic sections rather than every slide.
- A single column at left=64, top=148, width=1152 is a reliable default. Use two columns
  when the item count or hierarchy benefits from it.
</slide_type_agenda>

<slide_type_content>
Body slide (slide_type: "content"):
- Body area: top 148 ~ bottom 688 (540px max). Adjust height to content — do not always use 540px.
- Layout by component_hint:

  bullets: Title + body bullet textbox (bullet_level 0/1)
    Body: left=64, top=148, width=1152

  two_column: Title + two textboxes (width ~552px, gap 48px)
    Left: left=64, top=148, width=552 / Right: left=664, top=148, width=552

  vs_comparison: Left card (left=64, w=508) + VS label (left=596, w=88) + Right card (left=708, w=508)

  step_cards: 3-4 horizontal cards
    3 cards: width=352, gap=32 → left: 64, 448, 832
    4 cards: width=260, gap=24 → left: 64, 348, 632, 916

  summary_grid: 2x2 card grid
    TL: left=64, top=148, w=552, h=236 / TR: left=664, top=148
    BL: left=64, top=412 / BR: left=664, top=412

  arch_diagram: Blocks (shapes) + arrows (lines) forming a diagram. Minimize decorative divider lines — the diagram itself provides visual structure.
  pipeline: Left-to-right stage blocks + arrows. Minimize decorative divider lines — arrows and blocks provide visual structure.
  process_flow: Left description + right flow diagram. Minimize decorative divider lines — the flow provides visual structure.
  code_block / quote / info_cards / feature_list / concept_list / quote_code

Bottom auxiliary elements (top >= 540):
- Single element: left=64, top=612, width=1152, height=44
- Two elements: stack vertically (upper bottom + 16 <= lower top) or arrange horizontally
- If space is limited, reduce main diagram to bottom=540, auxiliary starts at 556
- Footer text is usually most readable on one line. Shorten or restructure it when it
  competes with the main content.
</slide_type_content>

<examples>
  <layout_example id="bullets-1" hint="bullets">
  {
    "grid_layout": {
      "regions": ["header", "content"],
      "content_columns": 1,
      "content_rows": 1
    },
    "cell_assignment": {
      "cells": [
        {"id": "h1", "region": "header", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "role": "title"},
        {"id": "c1", "region": "content", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "role": "bullet_list"}
      ]
    },
    "background_color": "#0F172A",
    "speaker_notes": "In this slide...",
    "textboxes": [
      {
        "grid_cell": "h1",
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Slide Title", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "grid_cell": "c1",
        "left_px": 64, "top_px": 148, "width_px": 1152, "height_px": 346,
        "vertical_alignment": "middle",
        "line_spacing_pt": 28,
        "paragraphs": [
          {"runs": [{"text": "First item", "font_size_pt": 24, "color": "#E2E8F0", "bold": false, "italic": false}], "bullet_level": 0, "alignment": "left"},
          {"runs": [{"text": "Detailed description", "font_size_pt": 20, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": 1, "alignment": "left"},
          {"runs": [{"text": "Second item", "font_size_pt": 24, "color": "#E2E8F0", "bold": false, "italic": false}], "bullet_level": 0, "alignment": "left"}
        ]
      }
    ],
    "shapes": []
  }
  </layout_example>

  <layout_example id="step-cards-1" hint="step_cards — 3 cards with paragraphs">
  {
    "grid_layout": {
      "regions": ["header", "content"],
      "content_columns": 3,
      "content_rows": 1
    },
    "cell_assignment": {
      "cells": [
        {"id": "h1", "region": "header", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "role": "title"},
        {"id": "c1", "region": "content", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "role": "step1_card"},
        {"id": "c2", "region": "content", "row": 1, "col": 2, "row_span": 1, "col_span": 1, "role": "step2_card"},
        {"id": "c3", "region": "content", "row": 1, "col": 3, "row_span": 1, "col_span": 1, "role": "step3_card"}
      ]
    },
    "background_color": "#0F172A",
    "speaker_notes": "",
    "textboxes": [
      {
        "grid_cell": "h1",
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Process Steps", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "grid_cell": "c1",
        "left_px": 64, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#334155", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "First Step", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Step description text goes here.", "font_size_pt": 16, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "grid_cell": "c2",
        "left_px": 448, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#334155", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "Second Step", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Step description text goes here.", "font_size_pt": 16, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "grid_cell": "c3",
        "left_px": 832, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#334155", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "Third Step", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Step description text goes here.", "font_size_pt": 16, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ]
  }
  </layout_example>

  <layout_example id="pipeline-1" hint="pipeline — 4 blocks with arrows">
  {
    "grid_layout": {
      "regions": ["header", "content"],
      "content_columns": 4,
      "content_rows": 1
    },
    "cell_assignment": {
      "cells": [
        {"id": "h1", "region": "header", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "role": "title"},
        {"id": "c1", "region": "content", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "role": "stage_input"},
        {"id": "c2", "region": "content", "row": 1, "col": 2, "row_span": 1, "col_span": 1, "role": "stage_process"},
        {"id": "c3", "region": "content", "row": 1, "col": 3, "row_span": 1, "col_span": 1, "role": "stage_validate"},
        {"id": "c4", "region": "content", "row": 1, "col": 4, "row_span": 1, "col_span": 1, "role": "stage_output"}
      ]
    },
    "background_color": "#0F172A",
    "speaker_notes": "",
    "textboxes": [
      {
        "grid_cell": "h1",
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Processing Pipeline", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "grid_cell": "c1",
        "left_px": 64, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#334155", "corner_radius_px": 12,
        "text": "Input", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "grid_cell": null,
        "left_px": 328, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#3B82F6", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "grid_cell": "c2",
        "left_px": 360, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#3B82F6", "corner_radius_px": 12,
        "text": "Process", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "grid_cell": null,
        "left_px": 624, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#3B82F6", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "grid_cell": "c3",
        "left_px": 656, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#334155", "corner_radius_px": 12,
        "text": "Validate", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "grid_cell": null,
        "left_px": 920, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#3B82F6", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "grid_cell": "c4",
        "left_px": 952, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#334155", "corner_radius_px": 12,
        "text": "Output", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      }
    ]
  }
  </layout_example>
</examples>

<diagram_grid>
Reference coordinates for common diagrams. Use them as reliable starting points, then
adapt them when the outline or intentional composition benefits from another valid layout.

Horizontal N-column even distribution (content area 1152px, gap=32px):
  | N | width | left positions                 |
  |---|-------|-------------------------------|
  | 2 |  560  | 64, 656                       |
  | 3 |  362  | 64, 458, 852                  |
  | 4 |  264  | 64, 360, 656, 952             |
  | 5 |  206  | 64, 302, 540, 778, 1016       |

Vertical M-row even distribution (safe area 508px = 148~656, gap=28px):
  | M | height | top positions                 |
  |---|--------|------------------------------|
  | 1 |  508   | 148                          |
  | 2 |  240   | 148, 416                     |
  | 3 |  150   | 148, 326, 504                |
  | 4 |  106   | 148, 282, 416, 550           |

Arrow coordinates (in addition to the shared line geometry contract):
- Horizontal (A→B, A left of B): left=A.right, top=A.top+A.height/2, width=B.left-A.right, height=0
- Vertical (A→B, A above B): left=A.left+A.width/2, top=A.bottom, width=0, height=B.top-A.bottom
- Vertical (A→B, A BELOW B, i.e. arrow goes up): left=A.left+A.width/2, top=B.bottom (the higher node's bottom = minimum y), width=0, height=-(A.top-B.bottom). `top` is B's edge, NOT A's.
- The arrowhead marks the flow DESTINATION (the target node), not a fixed coordinate corner. Use end_arrow=true when the destination is at the max corner, start_arrow=true when the destination is at the min corner. Min gap between blocks: 28px (arrowhead size=14px).
- Arrowhead penetration is invalid and ingest rejects it. Prefer endpoints on block
  edges; a floating gap remains a lint warning for review.

Cyclic / loop diagrams (ReAct loops, feedback loops, A→B→C→A):
  The arrowhead must sit on the edge of the TARGET node (the next node in the flow), regardless of coordinate direction.
  A back-edge (e.g. the return arrow C→A that goes from a lower/right node up to an earlier node) may run high→low coordinates. Use a negative width/height bbox so its endpoints land on the right edges, and place the arrowhead (start_arrow OR end_arrow) on the target node's edge.
  Mark the cycle: give the layout-tree group node that holds the cycle nodes role="cycle_diagram" in design_doc.layout. Its direct children are the cycle's participating nodes. This lets the cycle be validated for single-direction consistency.
  Example — 3-node triangle ReAct loop (Think top-center, Act bottom-right, Observe bottom-left), flow Think→Act→Observe→Think:
    · Think→Act: from Think bottom-right toward Act top-left, end_arrow=true (head on Act).
    · Act→Observe: horizontal from Act left edge to Observe right edge, head on Observe.
    · Observe→Think: back-edge from Observe top going up to Think bottom-left, head on Think.
  Every arrowhead points to the node that comes NEXT in the loop — so the three arrows circulate consistently in one rotational direction.

Fan-out / Fan-in arrows (one block → multiple targets, or vice versa):
  Prefer a bus-line pattern when separate center-to-center diagonals would become cluttered:
  1. Vertical stub: from source bottom center downward (height = half the vertical gap).
  2. Horizontal bus: a horizontal line spanning from the leftmost target center_x to the rightmost target center_x, at the stub's bottom y.
  3. Vertical drops: from the bus line down to each target's top center.
  This keeps all connections visually clean and aligned. For fan-in (many → one), reverse the direction.

Container interior: use the available space intentionally. Regular peer rows commonly share
top and height, while deliberate asymmetry is allowed. Children linked to a container must
remain within its bounds.
</diagram_grid>

<page_design_rules>
- Compose visual elements (flowcharts, diagrams, structure charts) using shapes and lines.
- Keep only essential keywords/short phrases on the slide. Report supplementary content
  in the structured overflow array rather than using speaker_notes as overflow storage.
- Use negative space intentionally — do not fill every gap.
- Use border_color, fill_color, corner_radius_px to create visual hierarchy.
- Decorative lines beside cards often align with the card height and usually use no rounding.
- Prefer whitespace over a routine title underline; use a divider only when it communicates
  meaningful hierarchy.
- **Diagram pages** (arch_diagram, pipeline, process_flow): Avoid decorative divider lines unless absolutely necessary — the diagram elements themselves provide sufficient visual structure.
- Use paragraphs in shapes for structured card interior text.
- For visual diagrams and tables, prefer actual shape objects over ASCII or box-drawing
  characters. Preserve such characters when they are literal code, terminal output, or
  content the slide is intentionally quoting.
</page_design_rules>

<pre_output_verification>
Before outputting JSON, verify the mandatory schema/link contracts and review these quality
signals. Keep an intentional alternative when it is valid; otherwise improve it or let lint
report the remaining risk.

1. FONT SIZE:
   Scan every font_size_pt. Card title >= 18, card body >= 16, label >= 14, any text >= 10.
   Repeated peer shapes usually use a consistent type scale. If text is too small, consider
   increasing the container, simplifying the copy, adjusting the composition, or using overflow.

2. OVERLAP (constraint 2):
   For every pair of same-level elements, check BOTH axes:
   - Vertical adjacency: gap = B.top - (A.top + A.height) >= 16
   - Horizontal adjacency: gap = B.left - (A.left + A.width) >= 16
   Two elements overlap when their bounding boxes intersect on BOTH axes simultaneously.
   Container children: all fit within parent bounds.

3. ALIGNMENT:
   Check whether repeated peers appear intentionally aligned and balanced. For a regular split
   layout, comparing the bottom edges is a useful diagnostic:
     left_bottom = max(top_px + height_px) for all elements with left_px < 620
     right_bottom = max(top_px + height_px) for all elements with left_px >= 620
   A larger difference may be intentional; otherwise adjust the composition.

4. DIAGRAM REPRESENTATION:
   Scan every text/run field for box-drawing or ASCII art characters: ┌ ─ ┐ │ └ ┘ ┬ ┴ ├ ┤ ╔ ═ ╗ ║ ╚ ╝ + - | (used as borders).
   When they substitute for a visual diagram, replace them with shapes. Preserve them when they
   are literal source content such as code or terminal output.
</pre_output_verification>
