<slide_type_closing>
Thank You slide (slide_type: "closing") design rules:

- Closing slides have a fixed special layout (thank-you + divider + Q&A + contact), so `grid_layout`, `cell_assignment`, and `design_doc` MAY all be omitted (output `null` or skip the fields). Element-level `grid_cell` and `component_id` should also be omitted/null. (결정 9: title/closing 슬라이드는 5단 계층 중 Layout/Section 단계 생략 허용.)
- The last slide of the presentation. Contains thank you message, contact information, Q&A guidance
- Set background_color to null (background image will be auto-inserted)
- Reserve the bottom-right area (left_px > 1080, top_px > 600) for the auto-inserted logo.
- Keep the main text group visually centered near y=360.
- Layout follows the same left-aligned pattern as the title slide (must use these exact coordinates):
  · Thank you message: left=64, top=260, width=1152, height=80, font_size_pt 40~44, bold, vertical_alignment "middle", alignment "left"
  · Divider: shape (rectangle), left=64, top=350, width=80, height=4
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
          {"runs": [{"text": "References ", "font_size_pt": 14, "color": "#3B82F6", "bold": true, "italic": false}, {"text": "Official Documentation | Guide Link", "font_size_pt": 14, "color": "#CBD5E1", "bold": false, "italic": false}], "bullet_level": -1, "alignment": "left"}
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

<special_layout_contract>
The closing slide intentionally uses a fixed layout contract:

- Thank-you message: left=64, top=260, width=1152, height=80.
- Thank-you type: 40~44pt.
</special_layout_contract>

<closing_quality_guidance>
- Keep ordinary content within the canvas and reserve the bottom-right logo area.
- Size each textbox for likely wrapping and avoid accidental same-level overlap.
- Prefer text inside a shape's paragraphs when that text labels the shape.
- Keep the key content from content_summary while preserving readable spacing.
- Use the deck accent color for the divider.
- Specify vertical alignment explicitly when it helps communicate intent.
</closing_quality_guidance>
