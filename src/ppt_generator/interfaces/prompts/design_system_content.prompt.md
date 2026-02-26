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
  - Card/banner/button shapes (with text or paragraphs): "middle"
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

<slide_type_agenda>
Agenda slide (slide_type: "content", component_hint: "agenda") design rules:

- The second slide of the presentation. Introduces the main sections/flow of the entire presentation
- Agenda items should not list every individual slide, but rather abstract related slides into larger topic units (sections), keeping it concise with 3-6 items
- Layout: Must use single-column layout only
  · Title: left=64, top=72, width=1152, height=48
  · Body: Single textbox below the title listing numbered items vertically (left=64, top=148, width=1152, height=adjust to content)
- Each item should be in numbered + section title format, written concisely
- Applying accent color to numbers is recommended for visual distinction
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
  quote_code: Left quote/description textbox + right code shape
  concept_list: Left concept description text + right diagram (shapes)

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
          {"runs": [{"text": "01", "font_size_pt": 28, "color": "#FFC000", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
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
          {"runs": [{"text": "02", "font_size_pt": 28, "color": "#FFC000", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
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
          {"runs": [{"text": "03", "font_size_pt": 28, "color": "#FFC000", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"},
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
- Slide title: font_size_pt 28~36, bold
- Subtitle/label: font_size_pt 14~18
- Body/description: font_size_pt 20~28
- Card title: font_size_pt 18~24, bold
- Card body: font_size_pt 16~20
- Secondary text: font_size_pt 12~16
- Code: font_family: "monospace", font_size_pt 14~16
- Recommended line_spacing_pt: body text 24~28pt, bullet lists 26~32pt, card interior 20~24pt
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
   - Diagram connection lines allowed: line shapes (arrows, connectors) may overlap with block shapes.
   - Container-child pattern example: In arch_diagram, place small rounded_rectangles (blocks) inside a large rounded_rectangle (background panel) and connect with lines (arrows).
   - **No placing textboxes as labels overlapping shapes**: Shape labels/titles must be included as the first item in the shape's paragraphs. Placing a separate textbox at the same coordinates as a shape will cause text to be hidden. Container shape area labels should also be placed in paragraphs or in a separate non-overlapping area above the container.
   Reason: Same-level overlap degrades text readability, while container-child nesting is essential for diagrams and structural layouts.

6. Margin enforcement (numeric criteria): All content elements must satisfy left_px >= 64, top_px >= 64, left_px + width_px <= 1216, top_px + height_px <= 688. Maintain 64px margins on left/right/top and 32px margin on bottom.

7. vertical_alignment required: Always specify vertical_alignment for all textboxes and shapes (null not allowed).

8. Title position: Title must be placed at left=64, top=72, width=1152, height=48.

9. Same-row element coordinate consistency: Elements arranged horizontally (cards, color bars, blocks, bottom info badges, etc.)
   must use **the same top_px and height_px**.
   - Example: 3 horizontally arranged cards → all 3 use top_px=521, height_px=69
   - Example: 3 color bars above cards → all 3 use top_px=493, height_px=10
   - Example: 3 bottom info badges → all 3 use top_px=626, height_px=30
   - Do not calculate each element's top_px individually. **First determine one top_px for the row**, then apply it uniformly to all elements in that row.
   Reason: Even a 1px difference in top_px breaks visual alignment, significantly degrading design quality.

10. No bottom auxiliary element overlap: When placing 2+ independent shapes/textboxes at the bottom of the slide (top_px >= 540),
    bounding boxes must not overlap vertically. Always apply vertical separation (upper element bottom + 16 <= lower element top) or
    horizontal separation (non-overlapping x ranges). Refer to "Bottom auxiliary element layout rules" in <slide_type_content>.
    Reason: The bottom area has limited space, and overlapping elements hide content, causing critical information to be lost.
</constraints>

<content_vertical_balance>
Vertical placement strategy based on content amount:

- **Adjust body height to match content.** Do not always fix height_px at 540 — calculate the height appropriate for the actual text amount (max 540px = 688 - 148). Note: Well-designed presentations have an average body height around 300px; fixing at 540px creates excessive empty space.
- If the body textbox's actual content is less than 65% of height_px, set vertical_alignment to "middle". This prevents content from clustering at the top and creates a visually balanced layout.
- Card layouts (step_cards, info_cards, etc.) should be positioned around the canvas vertical center.
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
