<slide_type_closing>
Thank You slide (slide_type: "closing") design rules:

- Closing slides may omit `grid_layout`, `cell_assignment`, and `design_doc`.
- The last slide is mandatory and must contain exactly one non-empty textbox with
  `component_id: "closing.message"`.
- Optional action/Q&A and contact textboxes use `closing.action` and `closing.contact`.
- `background_color` may be null or a deliberate DESIGN.md color.
- Reserve the bottom-right area (left_px > 1080, top_px > 600) for the auto-inserted logo.
- Choose composition, coordinates and typography from DESIGN.md and keep every element
  inside the canvas.
</slide_type_closing>

<examples>
  <layout_example id="closing-1" hint="closing — Thank You slide (left-aligned, same layout pattern as title slide)">
  {
    "background_color": null,
    "speaker_notes": "Questions and feedback are welcome.",
    "textboxes": [
      {
        "component_id": "closing.message",
        "left_px": 96, "top_px": 230, "width_px": 1000, "height_px": 120,
        "vertical_alignment": "middle",
        "paragraphs": [
          {"runs": [{"text": "Thank You", "font_size_pt": 40, "color": "#FFFFFF", "bold": true, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "component_id": "closing.action",
        "left_px": 96, "top_px": 390, "width_px": 900, "height_px": 70,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "Questions & Feedback", "font_size_pt": 20, "color": "#10B981", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      },
      {
        "component_id": "closing.contact",
        "left_px": 96, "top_px": 500, "width_px": 820, "height_px": 100,
        "vertical_alignment": "top",
        "paragraphs": [
          {"runs": [{"text": "References ", "font_size_pt": 14, "color": "#3B82F6", "bold": true, "italic": false}, {"text": "Official Documentation | Guide Link", "font_size_pt": 14, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
        ]
      }
    ],
    "shapes": [
      {"left_px": 96, "top_px": 365, "width_px": 180, "height_px": 4,
       "shape_type": "rectangle", "fill_color": "#3B82F6"}
    ]
  }
  </layout_example>
</examples>

<typography_rules>
- Thank you message: font_size_pt 40~44, bold
- Subtitle/label: font_size_pt 16~20
- Secondary text: font_size_pt 12~16
</typography_rules>

<special_layout_contract>
- Exactly one `closing.message` textbox is required.
- `closing.action` and `closing.contact` are optional and unique.
- Array order and pixel coordinates do not define semantic roles.
</special_layout_contract>

<closing_quality_guidance>
- Keep ordinary content within the canvas and reserve the bottom-right logo area.
- Size each textbox for likely wrapping and avoid accidental same-level overlap.
- Prefer text inside a shape's paragraphs when that text labels the shape.
- Keep the key content from content_summary while preserving readable spacing.
- Use the deck accent color for the divider.
- Specify vertical alignment explicitly when it helps communicate intent.
</closing_quality_guidance>
