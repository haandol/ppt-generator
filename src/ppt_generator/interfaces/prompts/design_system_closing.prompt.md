<slide_type_closing>
Thank You slide (slide_type: "closing") design rules:

- The last slide of the presentation. Contains thank you message, contact information, Q&A guidance
- Set background_color to null (background image will be auto-inserted)
- Do not place elements in the bottom-right area (left_px > 1080, top_px > 600) (logo auto-insertion area)
- Place main text at the vertical center of the canvas. The vertical center of the thank you text and supplementary information should be near the canvas center (y=360).
- Layout (must use these exact coordinates):
  · Thank you message: left=64, top=240, width=1152, height=80, font_size_pt 40~44, bold, vertical_alignment "middle", alignment "center"
  · Subtitle/Q&A: left=64, top=340, width=1152, height=60, font_size_pt 16~20, vertical_alignment "middle", alignment "center"
  · Contact/summary (optional): left=64, top=420, width=1000, height=120, font_size_pt 14~16, vertical_alignment "top", alignment "center"
</slide_type_closing>

<examples>
  <layout_example id="closing-1" hint="closing — Thank You slide (thank you message centered, subtitle and contact info below)">
  {
    "background_color": null,
    "speaker_notes": "Questions and feedback are welcome.",
    "textboxes": [
      {
        "left_px": 64, "top_px": 240, "width_px": 1152, "height_px": 80,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Thank You", "font_size_pt": 40, "color": "#FFFFFF", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "center"}
        ]
      },
      {
        "left_px": 64, "top_px": 340, "width_px": 1152, "height_px": 60,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Questions & Feedback", "font_size_pt": 20, "color": "#FFC000", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "center"}
        ]
      },
      {
        "left_px": 64, "top_px": 420, "width_px": 1000, "height_px": 120,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "References  ", "font_size_pt": 14, "color": "#FF9900", "bold": true, "italic": false}, {"text": "Official Documentation  |  Guide Link", "font_size_pt": 14, "color": "#D5DBDB", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "center"}
        ]
      }
    ],
    "shapes": []
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
8. Thank you position: Thank you message must be placed at left=64, top=240, width=1152, height=80.
9. Thank you font size: The thank you message text font_size_pt must be in the 40~44 range. Below 40pt is not allowed.
</constraints>
