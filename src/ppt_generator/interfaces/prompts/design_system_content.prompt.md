<constraints>
Hard constraints (rendering will fail if violated):

1. Font size — ABSOLUTE PRIORITY (override all other constraints):
   - Card title (first bold run in a shape with fill_color): >= 18pt
   - Card body (non-title runs in a shape with fill_color): >= 16pt
   - Section label (short textbox, category heading): >= 14pt
   - Any text element: >= 10pt, max 44pt
   - Slide title: 32~36pt (use design_summary.title_font_pt if provided)
   - **If content does not fit at these minimums, keep only essential keywords on the slide and put the excluded content into the overflow array. NEVER shrink fonts below the floor.**
   - Peer shapes in the same row must use IDENTICAL font_size_pt at each paragraph index.
   - Left vs right regions: equivalent roles must have font size difference <= 4pt.

2. No same-level overlap (container-child nesting allowed):
   - Same-level elements must not have overlapping bounding boxes. Gap >= 16px between adjacent elements.
   - Container-child nesting allowed: children must be fully contained within the parent bounds.
   - Container-child vertical stacking: compute each child's top_px from the previous child's bottom + gap. Never estimate by eye.
     Example (3 children, gap=8): A top=168 h=50 bottom=218 → B top=226 h=28 bottom=254 → C top=262
   - Line/arrow shapes may overlap block shapes. Textbox labels must NOT overlap shapes — put labels in the shape's paragraphs.

3. Coordinate bounds: left_px >= 0, top_px >= 0, left_px + width_px <= 1280, top_px + height_px <= 720.

4. Margin enforcement: left_px >= 64, top_px >= 64, right edge <= 1216, bottom edge <= 688. (64px margins left/right/top, 32px bottom)

5. Sufficient height: height_px >= lines (including wrapping) x font_size_pt x 2.0.

6. Content completeness — subordinate to constraint 1:
   Include key content from content_summary. **However, if all content cannot fit at the minimum font sizes, prioritize readability: keep only essential keywords/short phrases on the slide and put excluded content into the overflow array so the user can add it as a separate slide.**

7. vertical_alignment required: Always specify for all textboxes and shapes (null not allowed).
   - Title/subtitle: "middle"
   - Body/bullet textboxes: "middle" if content < 65% of box height, "top" otherwise
   - Peer cards in a row: MUST use "top"
   - Standalone card/banner: "middle"
   - Footer/bottom labels: "bottom"

8. Title position: left=64, top=72, width=1152, height=48. Font 32~36pt bold.

9. Same-row consistency: All elements in the same horizontal row must share identical top_px, height_px, paragraph font sizes, and padding values.

10. Vertical stack uniformity: N cards stacked vertically must all have the same height_px with equal gaps.
    Formula: card_i.top_px = first.top_px + i x (card_height + gap).

11. Left-right bottom alignment: In split layouts (two_column, concept_list, process_flow, etc.), both regions must share the same top_px AND bottom edge. Adjust the shorter side's height_px to match.
</constraints>

<typography_rules>
Font size ranges (see constraint 1 for mandatory minimums):
- Slide title: 32~36pt, bold
- Subtitle/label: 14~18pt
- Body/description: 20~28pt
- Card title: 18~24pt, bold
- Card body: 16~20pt
- Secondary text (footnotes, source): 12~16pt
- Code: font_family "monospace", 14~16pt
- Line spacing: body 24~28pt, bullet lists 26~32pt, card interior 20~24pt

Section label width: width_px >= char_count x font_size_pt x 1.2 (Korean) or x 0.73 (Latin).
</typography_rules>

<text_size_estimation>
- Korean char width ~ font_size_pt x 1.2px, Latin/number ~ font_size_pt x 0.73px
- Actual text width = width_px - padding_left - padding_right
- Required height = (lines x font_size_pt x 2.0) + padding_top + padding_bottom
- If estimated height exceeds available space: shorten text and put detail into overflow (constraint 1 priority)
</text_size_estimation>

<padding_and_spacing>
Padding (shapes containing text):
- Minimum: left/right >= 16px, top/bottom >= 14px
- Recommended for cards: 20~28px horizontal, 16~24px vertical
- height_px must accommodate text + padding + 16px breathing room

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
- Second slide. Lists 3-6 topic sections (not individual slides).
- Default: single-column (left=64, top=148, width=1152). Two-column only if 7+ items.
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

  arch_diagram: Blocks (shapes) + arrows (lines) forming a diagram
  pipeline: Left-to-right stage blocks + arrows
  process_flow: Left description + right flow diagram
  code_block / quote / info_cards / feature_list / concept_list / quote_code

Bottom auxiliary elements (top >= 540):
- Single element: left=64, top=612, width=1152, height=44
- Two elements: stack vertically (upper bottom + 16 <= lower top) or arrange horizontally
- If space is limited, reduce main diagram to bottom=540, auxiliary starts at 556
</slide_type_content>

<examples>
  <layout_example id="bullets-1" hint="bullets">
  {
    "background_color": "#232F3E",
    "speaker_notes": "In this slide...",
    "textboxes": [
      {
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Slide Title", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 64, "top_px": 148, "width_px": 1152, "height_px": 346,
        "vertical_alignment": "middle",
        "line_spacing_pt": 28,
        "paragraphs": [
          {"runs": [{"text": "First item", "font_size_pt": 24, "color": "#F1F3F3", "bold": false, "italic": false}], "bullet_level": 0, "alignment": "left"},
          {"runs": [{"text": "Detailed description", "font_size_pt": 20, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": 1, "alignment": "left"},
          {"runs": [{"text": "Second item", "font_size_pt": 24, "color": "#F1F3F3", "bold": false, "italic": false}], "bullet_level": 0, "alignment": "left"}
        ]
      }
    ],
    "shapes": []
  }
  </layout_example>

  <layout_example id="step-cards-1" hint="step_cards — 3 cards with paragraphs">
  {
    "background_color": "#232F3E",
    "speaker_notes": "",
    "textboxes": [
      {
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Process Steps", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "left_px": 64, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "First Step", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Step description text goes here.", "font_size_pt": 16, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 448, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "Second Step", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Step description text goes here.", "font_size_pt": 16, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 832, "top_px": 148, "width_px": 352, "height_px": 472,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "vertical_alignment": "top",
        "padding_left_px": 16, "padding_right_px": 16, "padding_top_px": 12, "padding_bottom_px": 12,
        "paragraphs": [
          {"runs": [{"text": "Third Step", "font_size_pt": 20, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
          {"runs": [{"text": "Step description text goes here.", "font_size_pt": 16, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ]
  }
  </layout_example>

  <layout_example id="pipeline-1" hint="pipeline — 4 blocks with arrows">
  {
    "background_color": "#232F3E",
    "speaker_notes": "",
    "textboxes": [
      {
        "left_px": 64, "top_px": 72, "width_px": 1152, "height_px": 48,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Processing Pipeline", "font_size_pt": 32, "color": "#ffffff", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "left_px": 64, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "text": "Input", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "left_px": 328, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#FFC000", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "left_px": 360, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#FF9900", "corner_radius_px": 12,
        "text": "Process", "text_color": "#1A2332", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "left_px": 624, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#FFC000", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "left_px": 656, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "text": "Validate", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      },
      {
        "left_px": 920, "top_px": 360, "width_px": 32, "height_px": 0,
        "shape_type": "line", "border_color": "#FFC000", "border_width_pt": 2,
        "end_arrow": true, "vertical_alignment": "top"
      },
      {
        "left_px": 952, "top_px": 300, "width_px": 264, "height_px": 120,
        "shape_type": "rounded_rectangle", "fill_color": "#2E3D50", "corner_radius_px": 12,
        "text": "Output", "text_color": "#FFFFFF", "text_size_pt": 20, "text_bold": true,
        "vertical_alignment": "middle"
      }
    ]
  }
  </layout_example>
</examples>

<diagram_grid>
Pre-calculated coordinates for diagrams. Use these values directly to prevent calculation errors.

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

Arrow coordinates:
- Horizontal (A→B): left=A.left+A.width, top=A.top+A.height/2, width=B.left-A.right, height=0
- Vertical (A→B): left=A.left+A.width/2, top=A.top+A.height, width=0, height=B.top-A.bottom
- All diagram arrows: end_arrow=true. Min gap between blocks: 28px (arrowhead size=14px).
- Endpoints must touch block edges exactly — no gap, no penetration.

Container interior: children must use >= 80% of inner width. All peer children in same row: identical top_px, height_px. All children must fit within container bounds.
</diagram_grid>

<page_design_rules>
- Compose visual elements (flowcharts, diagrams, structure charts) using shapes and lines.
- Keep only essential keywords/short phrases on the slide. Move supplementary text to speaker_notes.
- Use negative space intentionally — do not fill every gap.
- Use border_color, fill_color, corner_radius_px to create visual hierarchy.
- Decorative lines beside cards: match the card's top_px and height_px exactly.
- Use paragraphs in shapes for structured card interior text.
</page_design_rules>

<pre_output_verification>
Before outputting JSON, verify these critical items. Fix ALL violations before output.

1. FONT SIZE (constraint 1 — absolute priority):
   Scan every font_size_pt. Card title >= 18, card body >= 16, label >= 14, any text >= 10.
   Peer shapes in same row: identical font_size_pt at each paragraph position.
   **If any violation: increase font, shorten text, put detail into overflow. NEVER reduce font below floor.**

2. OVERLAP (constraint 2):
   For every pair of same-level elements: gap = B.top - (A.top + A.height) >= 16.
   Container children: all fit within parent bounds.

3. ALIGNMENT (constraints 9, 10, 11):
   Same-row peers: identical top_px, height_px, padding. Stacked cards: uniform height, equal gaps.
   Split layouts: left_bottom == right_bottom.
</pre_output_verification>
