<slide_type_closing>
Thank You slide (slide_type: "closing") design rules:

- The last slide of the presentation. Contains thank you message, contact information, Q&A guidance
- Set background_color to null (background image will be auto-inserted)
- Do not place elements in the bottom-right area (left_px > 1080, top_px > 600) (logo auto-insertion area)
- Place main text at the vertical center of the canvas. The vertical center of the entire text group should be near the canvas center (y=360).
- Layout follows the same left-aligned pattern as the title slide (must use these exact coordinates):
  · Thank you message: left=64, top=260, width=1152, height=80, font_size_pt 40~44, bold, vertical_alignment "middle", alignment "left"
  · Divider: shape (rectangle), left=64, top=350, width=80, height=4, fill_color accent color (#3B82F6), vertical_alignment "top"
  · Subtitle/Q&A: left=64, top=370, width=1152, height=60, font_size_pt 16~20, vertical_alignment "top", alignment "left"
  · Contact/summary (optional): left=64, top=450, width=1000, height=120, font_size_pt 14~16, vertical_alignment "top", alignment "left"
</slide_type_closing>

<examples>
  <layout_example id="closing-1" hint="closing — Thank You slide (left-aligned, same layout pattern as title slide)">
  {
    "background_color": null,
    "speaker_notes": "Questions and feedback are welcome.",
    "textboxes": [
      {
        "left_px": 64, "top_px": 260, "width_px": 1152, "height_px": 80,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Thank You", "font_size_pt": 40, "color": "#FFFFFF", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 64, "top_px": 370, "width_px": 1152, "height_px": 60,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "Questions & Feedback", "font_size_pt": 20, "color": "#10B981", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "left_px": 64, "top_px": 450, "width_px": 1000, "height_px": 120,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "References  ", "font_size_pt": 14, "color": "#3B82F6", "bold": true, "italic": false}, {"text": "Official Documentation  |  Guide Link", "font_size_pt": 14, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {
        "left_px": 64, "top_px": 350, "width_px": 80, "height_px": 4,
        "shape_type": "rectangle", "fill_color": "#3B82F6",
        "vertical_alignment": "top"
      }
    ]
  }
  </layout_example>
</examples>

<typography_rules>
- Thank you message: font_size_pt 40~44, bold
- Subtitle/label: font_size_pt 16~20
- Secondary text: font_size_pt 12~16
</typography_rules>

<constraints>
Hard constraints (rendering will fail if violated):

1. Font size range: All font_size_pt must be within 10~44pt range.
2. Coordinate bounds: left_px >= 0, top_px >= 0, left_px + width_px <= 1280, top_px + height_px <= 720.
3. Sufficient height: height_px must be at least lines (including wrapping) × font_size_pt × 2.0.
4. Content completeness: Include all key content from content_summary in textboxes or shapes.
5. No element overlap: Same-level elements must not have overlapping bounding boxes. **Never overlay a textbox on top of a shape as a label** — if a shape needs text, put it in that shape's paragraphs (not in a separate textbox at the same coordinates). A textbox has no padding, so text will overflow the shape boundary.
6. Margin enforcement: All content elements must satisfy left_px >= 64, top_px >= 64, left_px + width_px <= 1216, top_px + height_px <= 656.
7. vertical_alignment required: Always specify vertical_alignment for all textboxes and shapes (null not allowed).
8. Thank you position: Thank you message must be placed at left=64, top=260, width=1152, height=80.
9. Thank you font size: The thank you message text font_size_pt must be in the 40~44 range. Below 40pt is not allowed.
</constraints>
