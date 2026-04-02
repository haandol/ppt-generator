<layout_grid>
A 48-column × 20-row grid for coordinate calculation reference.
Output must be in px values, but first determine the "logical position" using column/row numbers before converting to reduce errors.

■ Horizontal 48-column grid (content area 1152px = 48 × 24px, cell 24×24px square)
  Formula: left_px = 64 + (col - 1) × 24

  | col |  1  |  2  |  3  |  4  |  5  |  6  |  7  |  8  |  9  | 10  | 11  | 12  | 13  | 14  | 15  | 16  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  |  64 |  88 | 112 | 136 | 160 | 184 | 208 | 232 | 256 | 280 | 304 | 328 | 352 | 376 | 400 | 424 |

  | col | 17  | 18  | 19  | 20  | 21  | 22  | 23  | 24  | 25  | 26  | 27  | 28  | 29  | 30  | 31  | 32  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 448 | 472 | 496 | 520 | 544 | 568 | 592 | 616 | 640 | 664 | 688 | 712 | 736 | 760 | 784 | 808 |

  | col | 33  | 34  | 35  | 36  | 37  | 38  | 39  | 40  | 41  | 42  | 43  | 44  | 45  | 46  | 47  | 48  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 832 | 856 | 880 | 904 | 928 | 952 | 976 |1000 |1024 |1048 |1072 |1096 |1120 |1144 |1168 |1192 |

  Key span → width conversions: span 48 = 1152px, span 24 = 576px, span 16 = 384px, span 12 = 288px

■ Vertical 20-row grid (body area 148~623, 500px = 20 × 25px)
  Formula: top_px = 148 + (row - 1) × 25

  | row |  1  |  2  |  3  |  4  |  5  |  6  |  7  |  8  |  9  | 10  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 148 | 173 | 198 | 223 | 248 | 273 | 298 | 323 | 348 | 373 |

  | row | 11  | 12  | 13  | 14  | 15  | 16  | 17  | 18  | 19  | 20  |
  |-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
  | px  | 398 | 423 | 448 | 473 | 498 | 523 | 548 | 573 | 598 | 623 |
</layout_grid>

<diagram_grid>
Pre-calculated coordinate table for diagrams (arch_diagram, pipeline, process_flow, etc.).
Use these table values directly for evenly distributing blocks to prevent calculation errors.

■ Horizontal N-column even distribution (content area 1152px, gap = 32px)
  Formula: width = (1152 - (N-1) × 32) / N  (truncate decimals)
           left[i] = 64 + i × (width + 32)   (i = 0, 1, …, N-1)
  **All elements in the same row must use the same top_px and height_px.**

  | N | width | left positions                 |
  |---|-------|-------------------------------|
  | 2 |  560  | 64, 656                       |
  | 3 |  362  | 64, 458, 852                  |
  | 4 |  264  | 64, 360, 656, 952             |
  | 5 |  206  | 64, 302, 540, 778, 1016       |

■ Vertical M-row even distribution (body area 508px, gap = 28px)
  Formula: height = (508 - (M-1) × 28) / M  (truncate decimals)
           top[j] = 148 + j × (height + 28)  (j = 0, 1, …, M-1)

  | M | height | top positions                 |
  |---|--------|------------------------------|
  | 1 |  508   | 148                          |
  | 2 |  240   | 148, 416                     |
  | 3 |  150   | 148, 326, 504                |
  | 4 |  106   | 148, 282, 416, 550           |

■ Arrow (line shape) coordinate calculation
  Connections between blocks are represented with shape_type: "line".
  A line shape renders as a straight connector from start point (left_px, top_px) to end point (left_px+width_px, top_px+height_px).

  - Horizontal arrow (left→right, same row):
      left_px  = blockA.left + blockA.width              (right edge of A)
      top_px   = blockA.top + blockA.height / 2          (vertical center of A)
      width_px = blockB.left - (blockA.left + blockA.width)  (= gap)
      height_px = 0
  - Vertical arrow (top→bottom, same column):
      left_px  = blockA.left + blockA.width / 2          (horizontal center of A)
      top_px   = blockA.top + blockA.height               (bottom edge of A)
      width_px = 0
      height_px = blockB.top - (blockA.top + blockA.height)  (= gap)

■ Arrow properties
  - end_arrow: true → Displays a triangular arrowhead at the end point (right/bottom).
  - start_arrow: true → Displays a triangular arrowhead at the start point (left/top).
  - dash_style: "solid" (default, solid line), "dash" (dashed), "dot" (dotted)
  - **All connection lines in diagrams must specify end_arrow: true to indicate flow direction.**
  - For bidirectional arrows, set both start_arrow: true and end_arrow: true.
  - Only omit (false) both end_arrow/start_arrow for plain connection lines without arrows.

■ Container/wrapper interior utilization (mandatory)
  When placing child elements (blocks, cards, diagram nodes) inside a container/wrapper shape:
  - Child elements must utilize **at least 80% of the container's inner width** (after padding).
  - Do NOT cluster child elements in a narrow sub-region of the container, leaving large empty margins on the sides.
  - Distribute child elements evenly within the container's inner area using the container's own left_px, width_px, and padding values.
  - Formula: child_area_left = container.left_px + container.padding_left_px
             child_area_width = container.width_px - container.padding_left_px - container.padding_right_px
             Then apply the N-column even distribution formula within child_area_width, starting from child_area_left.
  - Same principle applies vertically: child elements should span the container's available inner height, not cluster at the top.
  - **Peer children in the same row must have identical height_px and top_px.** Different heights cause misalignment.
  - **All children must fit entirely within the container bounds.** For each child, verify:
    child.left_px >= container.left_px + container.padding_left_px
    child.top_px >= container.top_px + container.padding_top_px (+ title paragraph height if container has a title)
    child.left_px + child.width_px <= container.left_px + container.width_px - container.padding_right_px
    child.top_px + child.height_px <= container.top_px + container.height_px - container.padding_bottom_px
    If any child overflows, reduce child height/width or increase container size.
  - **Stacking rows inside a container**: When a container has a horizontal row of children AND additional elements below (e.g., info bars), compute positions top-down:
    row_bottom = row_top + row_height
    next_element_top >= row_bottom + gap (at least 12px)
    Verify the last element's bottom does not exceed the container's inner bottom.

■ Arrow endpoint snapping (mandatory)
  Arrow endpoints must precisely touch the edge of the connected block — no gap, no penetration.
  - Start point (left_px, top_px) must lie exactly on the source block's edge.
  - End point (left_px+width_px, top_px+height_px) must lie exactly on the target block's edge.
  - Horizontal arrow: left_px == source.left + source.width, left_px + width_px == target.left
  - Vertical arrow: top_px == source.top + source.height, top_px + height_px == target.top
  - A gap > 0px means the arrow is visually disconnected ("floating").
  - A negative gap means the arrow penetrates the block.
  - Both are visual defects. Always derive arrow coordinates from connected blocks' exact edge values.

■ Minimum arrow gap rule (mandatory)
  Since arrowheads are 14px, **at least 28px gap** must be maintained between blocks when placing arrows.
  - Horizontal arrow: width_px >= 28 (distance between blockA's right and blockB's left >= 28)
  - Vertical arrow: height_px >= 28 (distance between blockA's bottom and blockB's top >= 28)
  - If gap is less than 28px, arrowheads will overlap or clip against blocks, causing visual artifacts.
  - If space between blocks is insufficient, reduce block size to ensure arrow gap.

■ 3×2 diagram example (3 columns × 2 rows, gap_h=32, gap_v=28)
  Block size: width=362, height=240
  Row 1: top=148  → (64,148), (458,148), (852,148)
  Row 2: top=416  → (64,416), (458,416), (852,416)
  Horizontal arrow (row 1, A→B): left=426, top=268, width=32, height=0, end_arrow=true
  Horizontal arrow (row 1, B→C): left=820, top=268, width=32, height=0, end_arrow=true
  Vertical arrow (col 1, R1→R2): left=245, top=388, width=0, height=28, end_arrow=true
</diagram_grid>

<shapes_text_usage>
Two ways to add text to shapes:
1. Simple text: Use text, text_color, text_size_pt, text_bold fields (single-line text, auto center-aligned)
2. Structured text: Use paragraphs array (for multi-line, bullets, mixed formatting). In paragraphs runs, use font_family: "monospace" to specify code font
If both are used, paragraphs takes priority. Actively use paragraphs for card-type shapes.
</shapes_text_usage>

<vertical_alignment_guide>
Always explicitly specify vertical_alignment for both textboxes and shapes. null is not allowed.
- "top": Top-aligned, "middle": Vertically centered, "bottom": Bottom-aligned
- Recommended values by use case:
  - Title/subtitle textboxes: "middle"
  - Body/bullet textboxes: "middle" recommended if content is less than 65% of box height, "top" if 65% or more
  - **Peer cards/shapes in a row (step_cards, info_cards, summary_grid, etc.): MUST use "top".**
    Reason: When multiple cards of the same height are arranged in a row but contain different amounts of text, "middle" alignment causes each card's content to start at a different vertical position. This makes titles and descriptions misaligned across cards. Using "top" ensures all peer cards start content at the same vertical position, maintaining visual consistency.
  - Standalone card/banner/button shapes (single element, not part of a peer row): "middle"
  - Footer/bottom labels: "bottom"
  - Decorative shapes (no text): "top"
</vertical_alignment_guide>

<padding_guide>
Both shapes and textboxes support padding_*_px fields to control the margin between text and boundaries.
Reason: Without proper padding, text sticks to boundaries, reducing readability.

- Default when unspecified: padding is 0 (no padding)
- Recommended for card-type shapes and textboxes with background: padding_left_px: 16~20, padding_right_px: 16~20, padding_top_px: 12~16, padding_bottom_px: 12~16
- Wide banner/header shapes: padding_left_px: 16~24 recommended
- Standalone textboxes (no background shape behind): padding is usually unnecessary

**Always consider padding when calculating coordinate placement.**
The bounding box (left_px/top_px/width_px/height_px) of shapes and textboxes represents the total area including padding.
The actual visible text area is the inner region after subtracting padding from the bounding box.
- shape: Inset by the specified padding_*_px (card-type default 16~18px)
- textbox: Inset by the specified padding_*_px (default 0 if unspecified)

Therefore, when placing decorative lines or label textboxes above/below a shape:
- The decorative line's bottom must be above the shape's top_px to prevent overlap with the shape's **text start point** (top_px + padding_top).
- Maintain **at least 16px spacing** so the label textbox's bottom (top_px + height_px + 16px visual padding) does not exceed the shape below's top_px.
</padding_guide>

<spacing_and_density_balance>
■ Minimum spacing rules (mandatory):
  Maintain adequate spacing between elements to ensure visual clarity and readability.
  - **Text-to-box boundary**: Card/shape inner text must have at least 12px padding from each edge. Never set all padding to 0 for shapes containing text.
  - **Box-to-box gap**: Adjacent independent shapes/textboxes must have at least 16px gap. Below 16px, elements appear cramped and difficult to distinguish.
  - **Text-to-text gap**: When multiple text blocks are stacked vertically (not inside the same textbox), maintain at least 12px gap between the bottom of one and the top of the next.
  - **Title-to-body**: Already enforced at minimum 28px (constraint from slide_type_content). Always respect this.

■ Content density balance (avoiding too sparse or too dense):
  Slide content should be neither too packed nor too spread out.

  **Too dense (avoid)**:
  - More than 7 distinct text blocks or shapes competing for attention on one slide.
  - Body font size squeezed below 16pt to fit excessive content.
  - Padding reduced below recommended minimums to save space.
  - Fix: Move excess content to speaker_notes, split into multiple slides, or simplify.

  **Too sparse (avoid)**:
  - Content occupies less than 30% of the available body area (148~656 vertical range), leaving large empty margins on top and bottom.
  - Only 1-2 short text lines placed in the center with no visual elements, leaving over 70% whitespace.
  - Fix: Use vertical_alignment "middle" to center content, adjust body height_px to match actual content, or add supporting visual elements (icons, dividers, shapes) to create balance.

  **Balanced target**:
  - Content fills 40~75% of the available body area.
  - Consistent spacing between elements (not cramped, not overly spread).
  - Font sizes within recommended ranges for their hierarchy level.
  - Adequate padding on all shapes containing text.
</spacing_and_density_balance>

<slide_type_agenda>
Agenda slide (slide_type: "content", component_hint: "agenda") design rules:

- The second slide of the presentation. Introduces the main sections/flow of the entire presentation
- Agenda items should not list every individual slide, but rather abstract related slides into larger topic units (sections), keeping it concise with 3-6 items
- Layout: **Default is single-column layout.** Only use two-column layout when the number of items exceeds 6 and a single column would waste excessive vertical space.
  · Single-column (default, 6 items or fewer):
    - Title: left=64, top=72, width=1152, height=48
    - Body: Single textbox below the title listing items vertically (left=64, top=148, width=1152, height=adjust to content)
  · Two-column (7+ items only, as a last resort):
    - Title: left=64, top=72, width=1152, height=48
    - Left: left=64, top=148, width=552, height=adjust to content
    - Right: left=664, top=148, width=552, height=adjust to content
- Each item should be written concisely as a section title
</slide_type_agenda>

<slide_type_content>
Body slide (slide_type: "content") design rules:

- Main body slide of the presentation. Covers the core content of the topic
- Canvas safe area: left 64~1216, top 64~688 (64px margin left/right/top, 32px margin bottom)
- Title-to-body spacing: Maintain minimum **28px** (between title bottom and body top)
- Minimum **16px** spacing between adjacent elements (vertical direction)
- Body height: Not fixed at 540px — **adjust to content amount** (estimate required height and set height_px)
- Layout guide by component_hint:

  bullets: Title textbox on top + body bullet textbox (bullet_level 0/1)
    · Title: left=64, top=72, width=1152, height=48
    · Body: left=64, top=148, width=1152, height=adjust to content (max 480)

  two_column: Title + two side-by-side textboxes (each width ~552px, gap 48px)
    · Title: left=64, top=72, width=1152, height=48
    · Left: left=64, top=148, width=552, height=adjust to content
    · Right: left=664, top=148, width=552, height=adjust to content
    · **Both sides must have the same top_px AND the same bottom edge (top_px + height_px).**

  vs_comparison: Title + two side cards (shape) + center VS label
    · Left: left=64, width=508 / VS: left=596, width=88 / Right: left=708, width=508

  step_cards: Title + 3-4 horizontally arranged cards (shape), each with number+title+description
    · 3 cards: width=352, gap=32px → left: 64, 448, 832
    · 4 cards: width=260, gap=24px → left: 64, 348, 632, 916

  code_block: Title + code area (shape, dark background, monospace font)
  arch_diagram: Title + blocks (shapes) connected by arrows (line shapes) forming a diagram
  pipeline: Title + left-to-right stage blocks (shapes) + arrows
  quote: Large quotation mark + quote textbox + source

  summary_grid: Title + 2x2 card (shape) grid
    · Top-left: left=64, top=148, width=552, height=236
    · Top-right: left=664, top=148, width=552, height=236
    · Bottom-left: left=64, top=412, width=552, height=236
    · Bottom-right: left=664, top=412, width=552, height=236

  info_cards: Title + 3-4 information cards (shapes) horizontally arranged
  feature_list: Title + icon/bullet + feature description text
  process_flow: Title + left description textbox + right flow diagram (shapes+lines)
    · **Left and right regions must share the same top_px AND bottom edge.**
  quote_code: Left quote/description textbox + right code shape
    · **Left and right regions must share the same top_px AND bottom edge.**
  concept_list: Left concept description text + right diagram (shapes)
    · **Left and right regions must share the same top_px AND bottom edge.**

■ Left-right split layout Y-axis alignment rules (mandatory):
  When a slide has two content regions side by side (e.g., two_column, concept_list, process_flow, or any custom left/right split):
  - **Top alignment**: Both the left and right content regions must start at the **same top_px**.
  - **Bottom alignment**: Both regions must end at the **same bottom_px** (top_px + height_px).
    · If the left side has multiple stacked cards (e.g., 4 cards), the right side graph/diagram box's bottom must match the bottom of the left side's lowest card.
    · Formula: right_region.height_px = left_lowest_card.top_px + left_lowest_card.height_px - right_region.top_px
  - **Internal element alignment**: When the right region contains a chart/graph with axes:
    · The chart's X-axis line top_px must align with or be above the right region's bottom boundary.
    · Labels, legends, and annotations below the X-axis must fit within the right region's bounding box.
    · Axis labels (e.g., "자율성 →"), legend items, and data point labels must be positioned relative to the X-axis, not estimated independently.
  - This rule applies to ALL split layouts, regardless of component_hint. Whenever left and right content regions coexist, their vertical extent must be visually aligned.

■ Bottom auxiliary element layout rules:
  When placing auxiliary elements at the bottom of a slide such as info badges, insight banners, or context boxes:

  1. **Single independent element at the bottom** (insight banner or info badge row):
     - Insight banner: left=64, top=612, width=1152, height=44, full width
     - Info badge row (2-3): Same top_px=612, height_px=44, arranged horizontally (refer to diagram_grid N-column even distribution)

  2. **Two independent elements at the bottom** (e.g., context box + insight banner):
     - Place both elements without vertical overlap. **Never overlap them in the same y range.**
     - Method A (vertical separation): Place context box above, insight banner below
       · Context box: top=540, height=68 (bottom=608)
       · Insight banner: top=624, height=32 (bottom=656)
     - Method B (horizontal separation): Place context box on left, insight banner on right side by side
       · Context box: left=64, width=500 / Insight banner: left=596, width=620
     - Method C (merge): Consolidate all content into a single shape using paragraphs

  3. **When space is limited**: Reduce the main diagram area height to make room for the bottom auxiliary area. Main diagram bottom should be at most 540px, bottom auxiliary area starts from 556px.
</slide_type_content>

<examples>
  <layout_example id="bullets-1" hint="bullets — Title + bullet point list (bullet_level 0/1 hierarchy, full-width textbox)">
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

  <layout_example id="step-cards-1" hint="step_cards — 3 horizontally arranged cards (number + title + description, using paragraphs, even gap=32px)">
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

  <layout_example id="pipeline-1" hint="pipeline — 4 blocks connected left-to-right with arrows (end_arrow) in a horizontal pipeline diagram">
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

<typography_rules>
- Slide title: font_size_pt 32~36, bold. **Must use design_summary.title_font_pt if provided.** Below 32pt is not allowed.
- Subtitle/label: font_size_pt 14~18
- Body/description: font_size_pt 20~28
- Card title: font_size_pt 18~24, bold
- Card body: font_size_pt 16~20
- Secondary text: font_size_pt 12~16
- Code: font_family: "monospace", font_size_pt 14~16
- Recommended line_spacing_pt: body text 24~28pt, bullet lists 26~32pt, card interior 20~24pt

■ Minimum font size for readability:
  - **Body text and card body must be at least 14pt.** Below 14pt, text becomes difficult to read at normal viewing distance.
  - Secondary/auxiliary text (footnotes, source labels) may go down to 12pt, but never below 10pt.
  - If content does not fit at the minimum font size, reduce the text amount or simplify — do NOT shrink font below the minimums.
</typography_rules>

<text_size_estimation>
Estimate the required height to prevent text overflow from boxes using the following guidelines.
Reason: Text overflow leads to clipping during rendering, causing critical information to be lost.

- Korean character width ≈ font_size_pt × 1.2px, Latin/number character width ≈ font_size_pt × 0.73px
- Example: width_px=500, font_size_pt=18, Korean → ~23 chars per line (500 / (18×1.2) = 23)
- Always subtract shape padding to calculate the actual text area width and height
  · Actual text width = width_px - padding_left_px - padding_right_px
  · Actual text height = height_px - padding_top_px - padding_bottom_px
  · Required height = (lines × font_size_pt × 2.0) + padding_top_px + padding_bottom_px
- Lines = total text width / actual text area width (round up)
</text_size_estimation>

<constraints>
Hard constraints (rendering will fail if violated):

1. Font size range: All font_size_pt must be within 10~44pt range.

2. Coordinate bounds: left_px >= 0, top_px >= 0, left_px + width_px <= 1280, top_px + height_px <= 720.

3. Sufficient height: height_px must be at least lines (including wrapping) × font_size_pt × 2.0. Always calculate the number of times text wraps within the box width.

4. Content completeness: Include all key content from content_summary in textboxes or shapes.
   Reason: Missing content mentioned in the outline reduces the presentation's completeness.

5. Element separation (no same-level overlap, container-child nesting allowed):
   - No overlap between same-level elements: Elements with the same role (e.g., card and card, textbox and textbox) must not have overlapping bounding boxes. If overlap exists, adjust the lower element's top_px to at least (upper element's top_px + height_px + 16).
   - **No overlap between elements with different roles either**: For example, shapes with different roles like "context detail box" and "insight summary banner" must not have overlapping bounding boxes. When placing 2+ independent elements at the bottom, always stack vertically (lower element starts at upper element's bottom + 16 or more) or arrange horizontally (non-overlapping x ranges).
   - Container-child nesting allowed: A large shape serving as a background/container with smaller shapes or textboxes placed inside it is allowed. In this case, child element bounding boxes must be completely contained within the parent shape's bounding box (child's left >= parent's left, child's top >= parent's top, child's right <= parent's right, child's bottom <= parent's bottom).
   - **Container-child vertical stacking**: When placing multiple child elements vertically inside a container, calculate coordinates top-down sequentially. Each child's top_px must be >= previous child's (top_px + height_px + gap). Never estimate positions by eye — always compute from the previous element's bottom edge.
     · Example (3 children stacked vertically inside a container, gap=8):
       Container: top=148, height=444 → inner area top=148+padding_top, bottom=148+444-padding_bottom
       Child A: top=168, height=50 → bottom=218
       Child B: top=218+8=226, height=28 → bottom=254
       Child C: top=254+8=262, height=112 → bottom=374
       ✓ All children fit within container and do not overlap each other
     · Common mistake: Setting child C's top=250 when child B's bottom=254 → 4px overlap causing visual corruption
   - Diagram connection lines allowed: line shapes (arrows, connectors) may overlap with block shapes.
   - Container-child pattern example: In arch_diagram, place small rounded_rectangles (blocks) inside a large rounded_rectangle (background panel) and connect with lines (arrows).
   - **No placing textboxes as labels overlapping shapes**: Shape labels/titles must be included as the first item in the shape's paragraphs. Placing a separate textbox at the same coordinates as a shape will cause text to be hidden. Container shape area labels should also be placed in paragraphs or in a separate non-overlapping area above the container.
   Reason: Same-level overlap degrades text readability, while container-child nesting is essential for diagrams and structural layouts.

6. Margin enforcement (numeric criteria): All content elements must satisfy left_px >= 64, top_px >= 64, left_px + width_px <= 1216, top_px + height_px <= 688. Maintain 64px margins on left/right/top and 32px margin on bottom.

7. vertical_alignment required: Always specify vertical_alignment for all textboxes and shapes (null not allowed).

8. Title position and font: Title must be placed at left=64, top=72, width=1152, height=48. Title font_size_pt must be 32~36 (use design_summary.title_font_pt if provided). Below 32pt is not allowed.

9. Same-row element coordinate consistency: Elements arranged horizontally (cards, color bars, blocks, bottom info badges, etc.)
   must use **the same top_px and height_px**.
   - Example: 3 horizontally arranged cards → all 3 use top_px=521, height_px=69
   - Example: 3 color bars above cards → all 3 use top_px=493, height_px=10
   - Example: 3 bottom info badges → all 3 use top_px=626, height_px=30
   - Do not calculate each element's top_px individually. **First determine one top_px for the row**, then apply it uniformly to all elements in that row.
   - **Internal paragraph consistency**: When peer cards/shapes contain paragraphs (e.g., title + description), all peer shapes must use **identical paragraph structure, font sizes, and line spacing**. This ensures titles and descriptions are rendered at the same vertical position across all cards.
   - **Separate label elements**: If number labels or icons are placed as separate textboxes/shapes above cards, all labels in the same row must share the exact same top_px, height_px, and font_size_pt.
   Reason: Even a 1px difference in top_px breaks visual alignment, significantly degrading design quality.

10. No bottom auxiliary element overlap: When placing 2+ independent shapes/textboxes at the bottom of the slide (top_px >= 540),
    bounding boxes must not overlap vertically. Always apply vertical separation (upper element bottom + 16 <= lower element top) or
    horizontal separation (non-overlapping x ranges). Refer to "Bottom auxiliary element layout rules" in <slide_type_content>.
    Reason: The bottom area has limited space, and overlapping elements hide content, causing critical information to be lost.

11. Left-right split vertical alignment: When a slide uses a left-right split layout (two_column, concept_list, process_flow, or any layout with distinct left and right content regions):
    - Both regions must share the **same top_px** (start of body content, typically 148px).
    - Both regions must share the **same bottom edge** (top_px + height_px must be equal for both sides).
    - If the left side consists of multiple vertically stacked elements (e.g., 4 cards), compute the bottom as: last_card.top_px + last_card.height_px. The right region's height_px must be adjusted so its bottom matches this value exactly.
    - **Chart/graph internal elements**: When the right region contains axes, all elements (axis lines, data points, labels, legends) must be positioned relative to the region's boundaries, not independently estimated. The X-axis line must sit at or above the region's bottom edge. Legend and axis labels must not extend beyond the region's bounding box.
    Reason: Misaligned top or bottom edges between left and right regions create an unbalanced, unprofessional appearance. This is one of the most common layout defects in split layouts.

**Pre-output overlap verification (mandatory)**:
Before outputting the final JSON, verify every pair of vertically adjacent elements:
  1. For each element, compute bottom = top_px + height_px
  2. For the element below it, check: its top_px >= previous bottom + 16 (minimum gap)
  3. For container-child patterns, verify all children fit within the container bounds
  4. **For left-right split layouts**: verify left_bottom == right_bottom (both regions end at the same Y coordinate). If they differ, adjust the shorter region's height_px so both bottoms match.
  5. If any violation is found, recalculate the offending element's top_px before output
This verification is critical because coordinate arithmetic errors (even off-by-1) cause visible overlap in the rendered slide.
</constraints>

<content_vertical_balance>
Vertical placement strategy based on content amount:

- **Adjust body height to match content.** Do not always fix height_px at 540 — calculate the height appropriate for the actual text amount (max 540px = 688 - 148). Note: Well-designed presentations have an average body height around 300px; fixing at 540px creates excessive empty space.
- If the body textbox's actual content is less than 65% of height_px, set vertical_alignment to "middle". This prevents content from clustering at the top and creates a visually balanced layout.
- Card layouts (step_cards, info_cards, etc.) should be positioned around the canvas vertical center.

■ Content area utilization with optical density balance (mandatory):
  When placing repeating elements (chart rows, card stacks, list items, etc.) inside a container or the body area:
  - **Utilize at least 60% of the parent area's available height.** Do not cluster elements in the top portion leaving large empty space below.
  - **Maintain consistent inter-element spacing** that preserves visual cohesion. Elements should feel grouped, not scattered.
  - Recommended approach: Calculate total content height (N items × item_height + (N-1) × gap), then center the content block vertically within the parent area. Adjust gap so total content height is 60~85% of available height.
  - **Avoid excessive spacing**: If the gap between adjacent items exceeds 2× the item height, the layout feels disconnected and sparse. Keep gap ≤ 1.5× item height.
  - **Avoid insufficient spacing**: If the gap is less than 8px, items feel cramped. Keep gap ≥ 12px for readability.
  - Formula for balanced gap: gap = (available_height - N × item_height) / (N + 1), then clamp to [12px, 1.5 × item_height].
</content_vertical_balance>

<page_design_rules>
- Always add diagrams or infographics that help understand each topic. Actively compose visual elements such as flowcharts, relationship diagrams, and structure diagrams by combining shapes (rectangle, rounded_rectangle, ellipse, line).
- Additionally, maximize the inclusion of images or infographics wherever possible on each page.
- Each page should contain only essential text — avoid excessive text. Focus on key keywords and short sentences.
- Place supplementary explanations in speaker_notes rather than in the slide body.
- Intentionally use negative space to emphasize core content. Do not try to fill empty spaces — visual breathing room guides the audience's attention to what matters.
- Combine existing shape properties (border_color, border_width_pt, fill_color, corner_radius_px) to enhance visual hierarchy. Examples: accent-color borders on key cards, brightness differences between background panels and foreground cards, thin divider lines for section separation.
- When placing thin decorative lines (horizontal: height≤10px, vertical: width≤10px) beside cards, always match the **same top_px and height_px as the card**. Position so the line's left_px + width_px equals the card's left_px, placing it flush against the card.
- **Corner radius consistency with decorative lines**: When a vertical decorative line is flush against a card's left edge, set the card's corner_radius_px to 0 or use shape_type "rectangle". A straight line touching a rounded card creates a visual mismatch.
</page_design_rules>

<content_output_rules>
- Actively use paragraphs in shapes to structure card interior text.
</content_output_rules>
